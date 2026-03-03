"""Dashboard CRUD routes and streaming report generation"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from bson import ObjectId

from app.database import get_database
from app.routes.auth import get_current_user
from app.models.user import User
from app.models.dashboard import DashboardItem
from app.services.langchain_agent import stream_generate_report
from app.services.report_renderer import render_report_html, render_pdf_from_html

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

print("[DashboardRoute] Router initialized")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SaveTableRequest(BaseModel):
    name: str
    table_data: list
    table_columns: list
    source_question: Optional[str] = ""
    source_prompt: Optional[str] = ""
    source_response: Optional[str] = ""


class SaveGraphRequest(BaseModel):
    name: str
    graph_type: str
    graph_config: dict          # {xKey, yKey, data, colors, ...}
    table_data: Optional[list] = []
    table_columns: Optional[list] = []
    source_question: Optional[str] = ""
    source_prompt: Optional[str] = ""
    source_response: Optional[str] = ""


class GenerateReportRequest(BaseModel):
    name: str
    item_ids: list[str]         # DashboardItem IDs to include
    template: str               # e.g. 'executive', 'technical', 'summary'
    prompt: str


class DashboardItemOut(BaseModel):
    id: str
    item_type: str
    name: str
    table_data: list
    table_columns: list
    graph_type: Optional[str]
    graph_config: Optional[dict]
    report_content: Optional[str]
    report_template: Optional[str]
    source_question: Optional[str]
    source_prompt: Optional[str]
    source_response: Optional[str]
    created_at: str
    metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_item(doc: dict) -> DashboardItemOut:
    created = doc.get("created_at", datetime.utcnow())
    return DashboardItemOut(
        id=str(doc["_id"]),
        item_type=doc.get("item_type", "table"),
        name=doc.get("name", ""),
        table_data=doc.get("table_data", []),
        table_columns=doc.get("table_columns", []),
        graph_type=doc.get("graph_type"),
        graph_config=doc.get("graph_config"),
        report_content=doc.get("report_content"),
        report_template=doc.get("report_template"),
        source_question=doc.get("source_question"),
        source_prompt=doc.get("source_prompt"),
        source_response=doc.get("source_response"),
        created_at=created.isoformat() if isinstance(created, datetime) else str(created),
        metadata=doc.get("metadata"),
    )


async def _collect_report_items_and_context(
    db,
    user_id: str,
    item_ids: list[str],
) -> Tuple[str, List[Dict]]:
    """
    Build both the markdown context string for the LLM and a structured list
    of items for downstream HTML/PDF rendering.
    """
    context_parts: list[str] = []
    items_for_report: list[dict] = []

    for item_id in item_ids:
        try:
            oid = ObjectId(item_id)
            doc = await db.dashboard_items.find_one({"_id": oid, "user_id": user_id})
            if not doc:
                continue

            item_type = doc.get("item_type", "")
            name = doc.get("name", "")
            created = doc.get("created_at", datetime.utcnow())
            created_str = created.isoformat() if isinstance(created, datetime) else str(created)

            base_item: dict = {
                "id": str(doc.get("_id")),
                "name": name,
                "item_type": item_type,
                "created_at_str": created_str,
                "source_question": doc.get("source_question", ""),
                "source_prompt": doc.get("source_prompt", ""),
                "source_response": doc.get("source_response", ""),
            }

            if item_type == "table":
                columns = doc.get("table_columns", [])
                rows = doc.get("table_data", [])
                # Format as markdown table for LLM context
                header = " | ".join(columns)
                sep = " | ".join(["---"] * len(columns))
                data_rows = "\n".join(
                    " | ".join(str(row.get(c, "")) for c in columns) for row in rows[:50]
                )
                context_parts.append(
                    f"### {name} (table)\n| {header} |\n| {sep} |\n{data_rows}"
                )
                base_item["table_columns"] = columns
                base_item["table_data"] = rows
            elif item_type == "graph":
                cfg = doc.get("graph_config", {})
                context_parts.append(
                    f"### {name} (graph: {doc.get('graph_type', '')})\n"
                    f"X-axis: {cfg.get('xKey', '')}, Y-axis: {cfg.get('yKey', '')}"
                )
                base_item["graph_type"] = doc.get("graph_type")
                base_item["graph_config"] = cfg

            items_for_report.append(base_item)
        except Exception as e:
            print(f"[DashboardRoute] Error loading item {item_id}: {e}")

    items_context = "\n\n".join(context_parts) if context_parts else "No specific data items selected."
    print(f"[DashboardRoute] Built context from {len(context_parts)} items")
    return items_context, items_for_report


# ---------------------------------------------------------------------------
# Item routes (tables & graphs)
# ---------------------------------------------------------------------------

@router.get("/items")
async def get_dashboard_items(
    item_type: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """List all saved tables and graphs for the current user."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] GET /items | user={user_id} | filter_type={item_type}")

    db = get_database()
    query: dict = {"user_id": user_id, "item_type": {"$in": ["table", "graph"]}}
    if item_type:
        query["item_type"] = item_type

    cursor = db.dashboard_items.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    print(f"[DashboardRoute] Found {len(docs)} items")

    return {"items": [_serialize_item(d) for d in docs], "total": len(docs)}


@router.post("/items/table", status_code=status.HTTP_201_CREATED)
async def save_table(
    request: SaveTableRequest,
    current_user: User = Depends(get_current_user),
):
    """Save a query result table to the dashboard."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] POST /items/table | user={user_id} | name={request.name}")

    db = get_database()
    item = DashboardItem(
        user_id=user_id,
        item_type="table",
        name=request.name,
        table_data=request.table_data,
        table_columns=request.table_columns,
        source_question=request.source_question,
        source_prompt=request.source_prompt,
        source_response=request.source_response,
    )
    result = await db.dashboard_items.insert_one(item.to_dict())
    print(f"[DashboardRoute] Table saved: {result.inserted_id}")

    return {"id": str(result.inserted_id), "message": "Table saved to dashboard"}


@router.post("/items/graph", status_code=status.HTTP_201_CREATED)
async def save_graph(
    request: SaveGraphRequest,
    current_user: User = Depends(get_current_user),
):
    """Save a chart/graph to the dashboard."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] POST /items/graph | user={user_id} | name={request.name} | type={request.graph_type}")

    db = get_database()
    item = DashboardItem(
        user_id=user_id,
        item_type="graph",
        name=request.name,
        graph_type=request.graph_type,
        graph_config=request.graph_config,
        table_data=request.table_data,
        table_columns=request.table_columns,
        source_question=request.source_question,
        source_prompt=request.source_prompt,
        source_response=request.source_response,
    )
    result = await db.dashboard_items.insert_one(item.to_dict())
    print(f"[DashboardRoute] Graph saved: {result.inserted_id}")

    return {"id": str(result.inserted_id), "message": "Graph saved to dashboard"}


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a saved table or graph."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] DELETE /items/{item_id} | user={user_id}")

    try:
        oid = ObjectId(item_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid item ID")

    db = get_database()
    doc = await db.dashboard_items.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Item not found")
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.dashboard_items.delete_one({"_id": oid})
    print(f"[DashboardRoute] Deleted item {item_id}")
    return None


# ---------------------------------------------------------------------------
# Report routes
# ---------------------------------------------------------------------------

@router.get("/reports")
async def get_reports(current_user: User = Depends(get_current_user)):
    """List all generated reports for the current user."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] GET /reports | user={user_id}")

    db = get_database()
    cursor = db.dashboard_items.find(
        {"user_id": user_id, "item_type": "report"}
    ).sort("created_at", -1)
    docs = await cursor.to_list(length=100)
    print(f"[DashboardRoute] Found {len(docs)} reports")

    return {"reports": [_serialize_item(d) for d in docs], "total": len(docs)}


@router.post("/reports/generate")
async def generate_report(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    SSE streaming report generation based on selected dashboard items.
    Streams markdown as it is generated.
    The caller must call POST /reports/save after confirming to persist.
    """
    user_id = str(current_user._id)
    print(f"[DashboardRoute] POST /reports/generate | user={user_id} | name={request.name} | items={request.item_ids}")

    db = get_database()

    # Build context from selected items (also returns structured items, which
    # can be used by HTML/PDF renderers and other endpoints).
    items_context, _items_for_report = await _collect_report_items_and_context(
        db=db,
        user_id=user_id,
        item_ids=request.item_ids,
    )

    async def event_generator():
        full_report = ""
        try:
            async for chunk in stream_generate_report(
                prompt=request.prompt,
                items_context=items_context,
                template=request.template,
            ):
                yield chunk
                # Track full report
                try:
                    raw = chunk.strip()
                    if raw.startswith("data: "):
                        payload = json.loads(raw[6:])
                        if payload.get("type") == "done":
                            full_report = payload.get("full_report", "")
                except Exception:
                    pass
        except Exception as e:
            print(f"[DashboardRoute] event_generator error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/reports/save", status_code=status.HTTP_201_CREATED)
async def save_report(
    request: dict,
    current_user: User = Depends(get_current_user),
):
    """Save a generated report to the user's dashboard."""
    user_id = str(current_user._id)
    name = request.get("name", "Report")
    content = request.get("content", "")
    template = request.get("template", "")
    item_ids = request.get("item_ids", [])
    print(f"[DashboardRoute] POST /reports/save | user={user_id} | name={name}")

    db = get_database()
    metadata = {"item_ids": item_ids} if item_ids else {}
    item = DashboardItem(
        user_id=user_id,
        item_type="report",
        name=name,
        report_content=content,
        report_template=template,
        metadata=metadata,
    )
    result = await db.dashboard_items.insert_one(item.to_dict())
    print(f"[DashboardRoute] Report saved: {result.inserted_id}")

    return {"id": str(result.inserted_id), "message": "Report saved to dashboard"}


@router.post("/reports/generate-pdf")
async def generate_report_pdf(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a detailed PDF report for the selected dashboard items.

    This endpoint runs the same LLM report generation logic as the streaming
    endpoint, but instead of streaming tokens to the client it aggregates the
    full markdown report server-side, renders HTML (including visual sections
    for the selected items), converts it to PDF, and returns the PDF bytes.
    """
    user_id = str(current_user._id)
    print(f"[DashboardRoute] POST /reports/generate-pdf | user={user_id} | name={request.name}")

    db = get_database()

    items_context, items_for_report = await _collect_report_items_and_context(
        db=db,
        user_id=user_id,
        item_ids=request.item_ids,
    )

    # Run the same streaming generator but aggregate full_report server-side.
    full_report = ""
    async for chunk in stream_generate_report(
        prompt=request.prompt,
        items_context=items_context,
        template=request.template,
    ):
        try:
            raw = chunk.strip()
            if raw.startswith("data: "):
                payload = json.loads(raw[6:])
                if payload.get("type") == "done":
                    full_report = payload.get("full_report", full_report)
                elif payload.get("type") == "token" and not full_report:
                    full_report += payload.get("content", "")
        except Exception:
            continue

    if not full_report:
        raise HTTPException(status_code=500, detail="Failed to generate report content")

    generated_at_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    html = render_report_html(
        full_report_markdown=full_report,
        items_for_report=items_for_report,
        title=request.name,
        author=current_user.full_name,
        generated_at=generated_at_str,
    )
    pdf_bytes = render_pdf_from_html(html)

    safe_name = request.name.replace("\\", "_").replace("/", "_").strip() or "datalens-report"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.pdf"',
        },
    )


@router.get("/reports/{report_id}/pdf")
async def download_saved_report_pdf(
    report_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download a previously saved dashboard report as a PDF."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] GET /reports/{report_id}/pdf | user={user_id}")

    try:
        oid = ObjectId(report_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID")

    db = get_database()
    doc = await db.dashboard_items.find_one({"_id": oid})
    if not doc or doc.get("user_id") != user_id or doc.get("item_type") != "report":
        raise HTTPException(status_code=404, detail="Report not found")

    full_report = doc.get("report_content", "") or ""
    metadata = doc.get("metadata") or {}
    item_ids = metadata.get("item_ids") or []

    items_for_report: List[Dict] = []
    if item_ids:
        _ctx, items_for_report = await _collect_report_items_and_context(
            db=db,
            user_id=user_id,
            item_ids=item_ids,
        )

    created = doc.get("created_at", datetime.utcnow())
    created_str = created.isoformat() if isinstance(created, datetime) else str(created)

    html = render_report_html(
        full_report_markdown=full_report,
        items_for_report=items_for_report,
        title=doc.get("name", "DataLens Report"),
        author=current_user.full_name,
        generated_at=created_str,
    )
    pdf_bytes = render_pdf_from_html(html)

    safe_name = (doc.get("name") or "datalens-report").replace("\\", "_").replace("/", "_").strip()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.pdf"',
        },
    )


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a report."""
    user_id = str(current_user._id)
    print(f"[DashboardRoute] DELETE /reports/{report_id} | user={user_id}")

    try:
        oid = ObjectId(report_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID")

    db = get_database()
    doc = await db.dashboard_items.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Report not found")
    if doc.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.dashboard_items.delete_one({"_id": oid})
    print(f"[DashboardRoute] Deleted report {report_id}")
    return None
