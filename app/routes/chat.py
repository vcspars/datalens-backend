"""Chat with Database routes — SSE streaming via LangChain SQL agent"""
import json
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from bson import ObjectId

from app.database import get_database
from app.routes.auth import get_current_user
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.services.langchain_agent import stream_chat_with_database

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
        error_occurred = False

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

            # Stream from LangChain agent
            async for chunk in stream_chat_with_database(question, history):
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
                )
                await db.chat_messages.insert_one(assistant_msg.to_dict())
                print(f"[ChatRoute] Saved assistant message to MongoDB | has_table={has_table} | tables={len(all_tables)}")
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
    Stream an AI-generated overview/summary of the connected SQL Server database.
    Saves the full result to the user's chat_session document after streaming.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/summary called | user={user_id}")

    from app.services.langchain_agent import stream_generate_report

    prompt = (
        "Connect to the SQL Server database and provide a comprehensive summary covering: "
        "1) list of all available tables with a brief description of what each stores, "
        "2) approximate row counts where possible, "
        "3) key columns and data types, "
        "4) notable relationships between tables. "
        "Use markdown headers (##, ###) and bullet points for readability."
    )

    _summary_system = (
        "You are a database analyst. Answer ONLY what is asked — do NOT prepend any title, "
        "document heading, 'Data Summary Report', 'Executive Summary', or similar phrase. "
        "Start your response directly with the first markdown section header (e.g. ## Tables). "
        "Format output as clean markdown with proper spacing between sections. "
        "Do NOT wrap the output in code fences."
    )

    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context="",
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
    Stream AI-generated suggested questions for the connected SQL Server database.
    Parses the numbered list and saves it to the user's chat_session document.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/questions called | user={user_id}")

    from app.services.langchain_agent import stream_generate_report

    prompt = (
        "Based on the SQL Server database structure, generate exactly 5 insightful questions "
        "that a business analyst would want to ask. "
        "Each question should be practical and answerable with a SQL query."
    )

    _questions_system = (
        "You are a database analyst. Return ONLY a numbered list of 5 questions, "
        "nothing else — no title, no preamble, no explanation, no closing remarks. "
        "Format exactly as:\n1. <question>\n2. <question>\n..."
    )

    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context="",
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
                questions = [q for q in questions if q][:5]
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
    Stream an AI-generated full analysis report of the database.
    Saves the full result to the user's chat_session document after streaming.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /db/report called | user={user_id}")

    from app.services.langchain_agent import stream_generate_report

    prompt = (
        "Generate a comprehensive database analysis report covering: "
        "table structures, data volumes, key business entities, relationships, "
        "and notable patterns or insights visible from the schema and data."
    )

    _report_system = (
        "You are a professional data analyst. Generate a detailed markdown report. "
        "Do NOT add a document title or top-level heading — start directly with "
        "the first section (e.g. ## Overview). "
        "Use markdown headers (##, ###), bullet points, and blank lines between sections "
        "for clear readability. Do NOT wrap the output in code fences."
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
