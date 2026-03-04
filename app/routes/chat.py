"""Chat with Database routes — SSE streaming via LangChain SQL agent"""
import json
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from bson import ObjectId

from app.config import settings
from app.database import get_database
from app.routes.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.services.report_renderer import render_simple_report_html, render_pdf_from_html

router = APIRouter(prefix="/chat", tags=["chat"])

print("[ChatRoute] Router initialized")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


class ChatHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    has_table: bool
    table_data: list
    table_columns: list
    tables: list = []
    sql_query: str = ""
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryItem]
    session_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_session(db, user_id: str) -> str:
    """Get existing chat session or create one for the user."""
    session_doc = await db.chat_sessions.find_one({"user_id": user_id})
    if session_doc:
        print(f"[ChatRoute] Found existing session for user {user_id}: {session_doc['_id']}")
        return str(session_doc["_id"])

    session = ChatSession(user_id=user_id)
    result = await db.chat_sessions.insert_one(session.to_dict())
    session_id = str(result.inserted_id)
    print(f"[ChatRoute] Created new session for user {user_id}: {session_id}")
    return session_id


async def _get_last_n_pairs(db, user_id: str, session_id: str, n: int = 5) -> list[dict]:
    """Retrieve the last n Q/A pairs for context injection."""
    cursor = db.chat_messages.find(
        {"user_id": user_id, "session_id": session_id}
    ).sort("created_at", -1).limit(n * 2)

    messages = await cursor.to_list(length=n * 2)
    messages.reverse()  # oldest first

    print(f"[ChatRoute] Loaded {len(messages)} history messages for context")
    return [
        {"role": m["role"], "content": m["content"]}
        for m in messages
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    SSE streaming endpoint for chat with SQL Server database.
    Streams LangChain agent tokens, then saves the Q/A pair to MongoDB.
    """
    user_id = str(current_user._id)
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty")

    print(f"[ChatRoute] /stream called | user={user_id} | question='{question[:100]}'")

    db = get_database()
    session_id = await _get_or_create_session(db, user_id)
    history = await _get_last_n_pairs(db, user_id, session_id, n=5)

    async def event_generator():
        full_response = ""
        has_table = False
        table_data = []
        table_columns = []
        all_tables: list = []
        sql_query = ""
        error_occurred = False

        if settings.USE_VANNA_AI:
            from app.services.vanna_agent import stream_chat_with_database_vanna
            stream_fn = stream_chat_with_database_vanna
            print("[ChatRoute] Using Vanna AI agent")
        else:
            from app.services.intent_classifier import classify_intent
            from app.services.langchain_agent import stream_chat_with_database, stream_simple_chat
            loop = asyncio.get_event_loop()
            intent = await loop.run_in_executor(
                None,
                lambda: classify_intent(question, history),
            )
            print(f"[ChatRoute] Intent classified: {intent!r}")
            if intent == "sql":
                stream_fn = stream_chat_with_database
                print("[ChatRoute] Routing to LangChain SQL agent")
            else:
                stream_fn = stream_simple_chat
                print("[ChatRoute] Routing to simple LLM (no SQL)")

        try:
            # Save user message first
            user_msg = ChatMessage(
                session_id=session_id,
                user_id=user_id,
                role="user",
                content=question,
            )
            await db.chat_messages.insert_one(user_msg.to_dict())
            print(f"[ChatRoute] Saved user message to MongoDB")

            async for chunk in stream_fn(question, history):
                yield chunk

                # Parse chunk to track state
                try:
                    raw = chunk.strip()
                    if raw.startswith("data: "):
                        payload = json.loads(raw[6:])
                        if payload.get("type") == "done":
                            full_response = payload.get("full_response", "")
                            has_table = payload.get("has_table", False)
                            table_data = payload.get("table_data", [])
                            table_columns = payload.get("table_columns", [])
                            all_tables = payload.get("tables", [])
                            sql_query = payload.get("sql_query", "") or ""
                        elif payload.get("type") == "error":
                            error_occurred = True
                except Exception:
                    pass

        except Exception as e:
            print(f"[ChatRoute] event_generator error: {e}")
            import traceback
            traceback.print_exc()
            error_event = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_event}\n\n"
            error_occurred = True
        finally:
            # Save assistant response to MongoDB
            if full_response and not error_occurred:
                assistant_msg = ChatMessage(
                    session_id=session_id,
                    user_id=user_id,
                    role="assistant",
                    content=full_response,
                    has_table=has_table,
                    table_data=table_data,
                    table_columns=table_columns,
                    tables=all_tables,
                    sql_query=sql_query or "",
                )
                await db.chat_messages.insert_one(assistant_msg.to_dict())
                print(f"[ChatRoute] Saved assistant message to MongoDB | has_table={has_table} | tables={len(all_tables)} | sql_query={bool(sql_query)}")
            else:
                print(f"[ChatRoute] Skipping assistant message save | full_response empty={not full_response} | error={error_occurred}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """
    Return chat history for the current user, newest last.
    Used on page load to restore previous conversation.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /history called | user={user_id} | limit={limit}")

    db = get_database()
    session_id = await _get_or_create_session(db, user_id)

    cursor = db.chat_messages.find(
        {"user_id": user_id, "session_id": session_id}
    ).sort("created_at", 1).limit(limit)

    messages = await cursor.to_list(length=limit)
    print(f"[ChatRoute] Returning {len(messages)} history messages")

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            ChatHistoryItem(
                id=str(m["_id"]),
                role=m["role"],
                content=m["content"],
                has_table=m.get("has_table", False),
                table_data=m.get("table_data", []),
                table_columns=m.get("table_columns", []),
                tables=m.get("tables", []),
                sql_query=m.get("sql_query", "") or "",
                created_at=m["created_at"].isoformat() if isinstance(m["created_at"], datetime) else str(m["created_at"]),
            )
            for m in messages
        ],
    )


@router.get("/db/overview")
async def get_db_overview(current_user: User = Depends(get_current_user)):
    """
    Return persisted db_summary, db_questions, and db_report for this user.
    Frontend calls this on mount to restore previously generated content.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/overview GET called | user={user_id}")

    db = get_database()
    session_doc = await db.chat_sessions.find_one({"user_id": user_id})
    if not session_doc:
        return {"summary": "", "questions": [], "report": ""}

    return {
        "summary": session_doc.get("db_summary", ""),
        "questions": session_doc.get("db_questions", []),
        "report": session_doc.get("db_report", ""),
    }


@router.post("/db/summary")
async def stream_db_summary(current_user: User = Depends(get_current_user)):
    """
    Stream an AI-generated summary for top management.
    Uses table row counts as context (no KPI SQL). Presents what data exists in business terms.
    Saves the full result to the user's chat_session document after streaming.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/summary called | user={user_id}")

    from app.services.langchain_agent import stream_generate_report, get_table_row_counts

    prompt = (
        "Using the Data Context below (table list and row counts), write a one-page summary for top management. "
        "Describe at a high level what business data the organization has: e.g. customers, products, sales, purchases, "
        "inventory, vendors — and the scale of that data (use the row counts from the context). "
        "Use markdown (##, ###). Keep language business-focused for leadership; avoid technical terms like schema or column names. "
        "Use only the numbers from the Data Context; do not invent values. "
        "Do NOT mention data gaps, missing data, or that any area has no records — we do not have that information."
    )

    _summary_system = (
        "You are an executive report writer for C-level readers. Answer ONLY what is asked. "
        "Do NOT prepend a document title or 'Executive Summary'. Start with the first section header (e.g. ## Overview of Business Data). "
        "Format as clean markdown. Do NOT wrap output in code fences. "
        "Keep the tone suitable for leadership; use the row counts from the Data Context where relevant. "
        "Do NOT include any section or sentence about data gaps, missing data, or unavailable areas — omit that entirely."
    )

    db = get_database()

    try:
        row_counts_context = get_table_row_counts()
    except Exception as e:
        print(f"[ChatRoute] get_table_row_counts failed: {e}")
        row_counts_context = ""

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context=row_counts_context,
                template="summary",
                custom_system_prompt=_summary_system,
            ):
                yield chunk
                # Track the full_report from the done event
                try:
                    raw = chunk.strip()
                    if raw.startswith("data: "):
                        payload = json.loads(raw[6:])
                        if payload.get("type") == "done":
                            full_content = payload.get("full_report", full_content)
                        elif payload.get("type") == "token":
                            full_content += payload.get("content", "")
                except Exception:
                    pass
        finally:
            if full_content:
                await db.chat_sessions.update_one(
                    {"user_id": user_id},
                    {"$set": {"db_summary": full_content, "updated_at": datetime.utcnow()}},
                    upsert=True,
                )
                print(f"[ChatRoute] Saved db_summary to session | user={user_id} | len={len(full_content)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/db/questions")
async def stream_db_questions(current_user: User = Depends(get_current_user)):
    """
    Stream AI-generated suggested questions for top management (revenue, profit, growth, etc.).
    Questions are answerable with business data; no technical or schema questions.
    Parses the numbered list and saves it to the user's chat_session document.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/questions called | user={user_id}")

    from app.services.langchain_agent import stream_generate_report

    _questions_context = (
        "Available data: Total Revenue, Total Purchases, Total Profit, Net Profit Margin, "
        "Inventory Value, Active Customers, Active Vendors, "
        "Total Invoices, Total Quantity Sold, Items Below Reorder Level, Purchase Orders On-Time Rate (all global/all-time metrics)."
    )

    prompt = (
        "Generate exactly 10 questions that a CEO or top management would ask about business performance. "
        "Base them on the following available metrics only. Questions must be answerable with our business data. "
        "Do NOT suggest technical or database-structure questions. Return only a numbered list: 1. ... 2. ... 10. ..."
    )

    _questions_system = (
        "You are an analyst helping leadership. Return ONLY a numbered list of 10 questions, "
        "nothing else — no title, no preamble, no explanation, no closing remarks. "
        "Format exactly as:\n1. <question>\n2. <question>\n...\n10. <question>"
    )

    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context=_questions_context,
                template="summary",
                custom_system_prompt=_questions_system,
            ):
                yield chunk
                try:
                    raw = chunk.strip()
                    if raw.startswith("data: "):
                        payload = json.loads(raw[6:])
                        if payload.get("type") == "done":
                            full_content = payload.get("full_report", full_content)
                        elif payload.get("type") == "token":
                            full_content += payload.get("content", "")
                except Exception:
                    pass
        finally:
            if full_content:
                # Parse numbered list into a clean list of strings
                questions = [
                    line.strip().lstrip("0123456789.)- ").strip()
                    for line in full_content.split("\n")
                    if line.strip() and len(line.strip()) > 10
                ]
                questions = [q for q in questions if q][:10]
                await db.chat_sessions.update_one(
                    {"user_id": user_id},
                    {"$set": {"db_questions": questions, "updated_at": datetime.utcnow()}},
                    upsert=True,
                )
                print(f"[ChatRoute] Saved {len(questions)} db_questions to session | user={user_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/db/report")
async def stream_db_report(current_user: User = Depends(get_current_user)):
    """
    Stream an AI-generated report for top management.
    No SQL KPI queries; describes what the organization's data supports at a high level for leadership.
    Saves the full result to the user's chat_session document after streaming.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/report called | user={user_id}")

    from app.services.langchain_agent import stream_generate_report

    prompt = (
        "Generate a high-level report for the leadership team about what business data the organization has and what it can be used for. "
        "Sections (in business language): Overview; Sales & revenue data; Purchases & procurement; Inventory; Customers & vendors; "
        "and a short note on how this data supports decision-making. Use markdown (##, ###). "
        "Keep the tone suitable for C-level; do not use technical or schema jargon. "
        "Do NOT mention data gaps, missing data, or that any area has no records — omit any such content entirely."
    )

    _report_system = (
        "You are a report writer for top management. Generate a clear markdown report. "
        "Do NOT add a document title — start with the first section (e.g. ## Overview). "
        "Use markdown headers (##, ###), bullet points, and blank lines. Do NOT wrap the output in code fences. "
        "Audience is C-level and leadership; avoid database or technical terminology. "
        "Do NOT include any section or sentence about data gaps, missing data, or unavailable areas — omit that entirely."
    )

    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context="",
                template="technical",
                custom_system_prompt=_report_system,
            ):
                yield chunk
                try:
                    raw = chunk.strip()
                    if raw.startswith("data: "):
                        payload = json.loads(raw[6:])
                        if payload.get("type") == "done":
                            full_content = payload.get("full_report", full_content)
                        elif payload.get("type") == "token":
                            full_content += payload.get("content", "")
                except Exception:
                    pass
        finally:
            if full_content:
                await db.chat_sessions.update_one(
                    {"user_id": user_id},
                    {"$set": {"db_report": full_content, "updated_at": datetime.utcnow()}},
                    upsert=True,
                )
                print(f"[ChatRoute] Saved db_report to session | user={user_id} | len={len(full_content)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/db/report/pdf")
async def download_db_report_pdf(current_user: User = Depends(get_current_user)):
    """
    Download the persisted database analysis report as a PDF.

    Uses the same markdown stored on the chat session, rendered via the shared
    report renderer used for dashboard reports.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] GET /db/report/pdf called | user={user_id}")

    db = get_database()
    session_doc = await db.chat_sessions.find_one({"user_id": user_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="No report available")

    report_md = session_doc.get("db_report") or ""
    if not report_md:
        raise HTTPException(status_code=404, detail="No report available")

    html = render_simple_report_html(
        full_report_markdown=report_md,
        title="Database Analysis Report",
    )
    pdf_bytes = render_pdf_from_html(html)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="database-report.pdf"',
        },
    )


@router.delete("/db/overview")
async def clear_db_overview(current_user: User = Depends(get_current_user)):
    """Reset persisted summary, questions, and report so they can be regenerated."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/overview DELETE called | user={user_id}")
    db = get_database()
    await db.chat_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"db_summary": "", "db_questions": [], "db_report": "", "updated_at": datetime.utcnow()}},
    )
    return {"message": "Overview cleared"}


@router.get("/bookmarks")
async def get_bookmarks(current_user: User = Depends(get_current_user)):
    """Return the user's bookmarked questions from their chat session."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] GET /bookmarks | user={user_id}")
    db = get_database()
    session_doc = await db.chat_sessions.find_one({"user_id": user_id})
    if not session_doc:
        return {"bookmarks": []}
    bookmarks = session_doc.get("bookmarks", [])
    # Serialise datetime to ISO string for JSON
    for b in bookmarks:
        if isinstance(b.get("created_at"), datetime):
            b["created_at"] = b["created_at"].isoformat()
    print(f"[ChatRoute] Returning {len(bookmarks)} bookmarks")
    return {"bookmarks": bookmarks}


class BookmarkRequest(BaseModel):
    question: str


@router.post("/bookmarks", status_code=201)
async def add_bookmark(
    request: BookmarkRequest,
    current_user: User = Depends(get_current_user),
):
    """Add a question to the user's bookmarks list (stored in chat_sessions)."""
    user_id = str(current_user._id)
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    print(f"[ChatRoute] POST /bookmarks | user={user_id} | question='{question[:80]}'")
    db = get_database()

    # Check for duplicate
    session_doc = await db.chat_sessions.find_one({"user_id": user_id})
    if session_doc:
        existing = session_doc.get("bookmarks", [])
        if any(b.get("question") == question for b in existing):
            raise HTTPException(status_code=409, detail="Already bookmarked")

    import uuid
    new_bookmark = {
        "id": str(uuid.uuid4()),
        "question": question,
        "created_at": datetime.utcnow().isoformat(),
    }

    await db.chat_sessions.update_one(
        {"user_id": user_id},
        {
            "$push": {"bookmarks": new_bookmark},
            "$set": {"updated_at": datetime.utcnow()},
        },
        upsert=True,
    )
    print(f"[ChatRoute] Bookmark saved | id={new_bookmark['id']}")
    return new_bookmark


@router.delete("/bookmarks/{bookmark_id}", status_code=204)
async def delete_bookmark(
    bookmark_id: str,
    current_user: User = Depends(get_current_user),
):
    """Remove a bookmark from the user's chat session by its id."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] DELETE /bookmarks/{bookmark_id} | user={user_id}")
    db = get_database()
    result = await db.chat_sessions.update_one(
        {"user_id": user_id},
        {
            "$pull": {"bookmarks": {"id": bookmark_id}},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    print(f"[ChatRoute] Bookmark deleted | id={bookmark_id}")


# ---------------------------------------------------------------------------
# Graphs tab persistence (stored on chat_sessions)
# ---------------------------------------------------------------------------

class DbGraphInstance(BaseModel):
    id: str
    table_data: list
    table_columns: list
    graph_type: str
    xKey: str
    yKey: str
    source_label: Optional[str] = None


class SaveGraphsRequest(BaseModel):
    graphs: list[DbGraphInstance]


@router.get("/db/graphs")
async def get_db_graphs(current_user: User = Depends(get_current_user)):
    """Return the user's Graphs tab instances from their chat session."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] GET /db/graphs | user={user_id}")
    db = get_database()
    session_doc = await db.chat_sessions.find_one({"user_id": user_id})
    graphs = session_doc.get("graphs", []) if session_doc else []
    print(f"[ChatRoute] Returning {len(graphs)} graph instances")
    return {"graphs": graphs}


@router.put("/db/graphs")
async def save_db_graphs(
    request: SaveGraphsRequest,
    current_user: User = Depends(get_current_user),
):
    """Overwrite the user's Graphs tab instances on their chat session."""
    user_id = str(current_user._id)
    graphs = [g.model_dump() for g in request.graphs]
    print(f"[ChatRoute] PUT /db/graphs | user={user_id} | count={len(graphs)}")
    db = get_database()
    await db.chat_sessions.update_one(
        {"user_id": user_id},
        {"$set": {"graphs": graphs, "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return {"message": "Graphs saved", "count": len(graphs)}


@router.delete("/history")
async def clear_chat_history(current_user: User = Depends(get_current_user)):
    """Clear all chat messages for the current user."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] /history DELETE called | user={user_id}")

    db = get_database()
    result = await db.chat_messages.delete_many({"user_id": user_id})
    print(f"[ChatRoute] Deleted {result.deleted_count} messages")

    return {"message": f"Cleared {result.deleted_count} messages"}
