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


class ChatPendingResponse(BaseModel):
    active: bool
    user_message_id: str = ""
    question: str = ""


class ChatCancelRequest(BaseModel):
    user_message_id: Optional[str] = None
    keep_partial: bool = False
    partial_content: Optional[str] = None


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
    """Retrieve the last n Q/A pairs for context injection. Includes sql_query for assistant messages so the resolver and agent have full context."""
    cursor = db.chat_messages.find(
        {"user_id": user_id, "session_id": session_id}
    ).sort("created_at", -1).limit(n * 2)

    messages = await cursor.to_list(length=n * 2)
    messages.reverse()  # oldest first

    print(f"[ChatRoute] Loaded {len(messages)} history messages for context")
    out = []
    for m in messages:
        item = {"role": m["role"], "content": m["content"]}
        if m.get("role") == "assistant" and m.get("sql_query"):
            item["sql_query"] = m["sql_query"]
        out.append(item)
    return out


async def _is_generation_cancelled(db, user_message_id: str) -> bool:
    """True when the user pressed Stop for this generation."""
    doc = await db.chat_generations.find_one({"user_message_id": user_message_id})
    return bool(doc and doc.get("status") == "cancelled")


async def _mark_generation_completed(db, user_message_id: str) -> None:
    """Mark completed only if the user has not cancelled this generation."""
    await db.chat_generations.update_one(
        {"user_message_id": user_message_id, "status": {"$ne": "cancelled"}},
        {"$set": {"status": "completed", "updated_at": datetime.utcnow()}},
    )


async def _delete_user_message(db, user_id: str, user_message_id: str) -> bool:
    """Remove the user message when a send is cancelled during thinking."""
    try:
        user_oid = ObjectId(user_message_id)
    except Exception:
        return False
    result = await db.chat_messages.delete_one({"_id": user_oid, "user_id": user_id})
    return result.deleted_count > 0


async def _cleanup_cancelled_generation(
    db, user_id: str, session_id: str, user_message_id: str
) -> None:
    """Remove assistant replies and user message when cancelled without keep_partial."""
    doc = await db.chat_generations.find_one({"user_message_id": user_message_id})
    if not doc or doc.get("status") != "cancelled" or doc.get("keep_partial"):
        return
    deleted = await _delete_assistants_after_user(db, user_id, session_id, user_message_id)
    if deleted:
        print(
            f"[ChatRoute] Post-cancel cleanup removed {deleted} assistant(s) | "
            f"user_message_id={user_message_id}"
        )
    if await _delete_user_message(db, user_id, user_message_id):
        print(
            f"[ChatRoute] Post-cancel cleanup removed user message | "
            f"user_message_id={user_message_id}"
        )


async def _find_first_assistant_after_user(
    db, user_id: str, session_id: str, user_message_id: str
) -> str:
    """Return the earliest assistant message id saved after a user message."""
    try:
        user_oid = ObjectId(user_message_id)
    except Exception:
        return ""
    user_doc = await db.chat_messages.find_one({"_id": user_oid, "user_id": user_id})
    if not user_doc:
        return ""
    assistant = await db.chat_messages.find_one(
        {
            "user_id": user_id,
            "session_id": session_id,
            "role": "assistant",
            "created_at": {"$gte": user_doc["created_at"]},
        },
        sort=[("created_at", 1)],
    )
    return str(assistant["_id"]) if assistant else ""


async def _resolve_existing_assistant_id(
    db,
    user_id: str,
    session_id: str,
    user_message_id: str,
    existing_id: str = "",
) -> str:
    """Find the single assistant doc for this generation (never create duplicates)."""
    if existing_id:
        return existing_id
    gen = await db.chat_generations.find_one({"user_message_id": user_message_id})
    if gen and gen.get("assistant_message_id"):
        return gen["assistant_message_id"]
    return await _find_first_assistant_after_user(db, user_id, session_id, user_message_id)


async def _set_generation_assistant_id(
    db, user_message_id: str, assistant_id: str
) -> None:
    if not assistant_id:
        return
    await db.chat_generations.update_one(
        {"user_message_id": user_message_id},
        {"$set": {"assistant_message_id": assistant_id, "updated_at": datetime.utcnow()}},
    )


async def _dedupe_assistants_after_user(
    db, user_id: str, session_id: str, user_message_id: str, keep_id: str
) -> int:
    """Remove duplicate assistant replies for one user message, keeping keep_id."""
    if not keep_id:
        return 0
    try:
        user_oid = ObjectId(user_message_id)
        keep_oid = ObjectId(keep_id)
    except Exception:
        return 0
    user_doc = await db.chat_messages.find_one({"_id": user_oid, "user_id": user_id})
    if not user_doc:
        return 0
    cursor = db.chat_messages.find(
        {
            "user_id": user_id,
            "session_id": session_id,
            "role": "assistant",
            "created_at": {"$gte": user_doc["created_at"]},
        },
        sort=[("created_at", 1)],
    )
    assistants = await cursor.to_list(length=20)
    dup_ids = [
        a["_id"] for a in assistants
        if a["_id"] != keep_oid
    ]
    if not dup_ids:
        return 0
    result = await db.chat_messages.delete_many({"_id": {"$in": dup_ids}, "user_id": user_id})
    if result.deleted_count:
        print(
            f"[ChatRoute] Deduped {result.deleted_count} duplicate assistant(s) | "
            f"keep={keep_id} | user_message_id={user_message_id}"
        )
    return result.deleted_count


async def _upsert_assistant_for_generation(
    db,
    user_id: str,
    session_id: str,
    user_message_id: str,
    content: str,
    existing_id: str = "",
    has_table: bool = False,
    table_data=None,
    table_columns=None,
    all_tables=None,
    sql_query: str = "",
) -> str:
    """Insert or update the assistant reply for an in-flight generation (partial save)."""
    content = (content or "").strip()
    if not content:
        return existing_id or ""

    if table_data is None:
        table_data = []
    if table_columns is None:
        table_columns = []
    if all_tables is None:
        all_tables = []

    fields = {
        "content": content,
        "has_table": has_table,
        "table_data": table_data,
        "table_columns": table_columns,
        "tables": all_tables,
        "sql_query": sql_query or "",
    }

    resolved_id = await _resolve_existing_assistant_id(
        db, user_id, session_id, user_message_id, existing_id
    )
    if resolved_id:
        try:
            await db.chat_messages.update_one(
                {"_id": ObjectId(resolved_id), "user_id": user_id},
                {"$set": fields},
            )
            await _dedupe_assistants_after_user(
                db, user_id, session_id, user_message_id, resolved_id
            )
            await _set_generation_assistant_id(db, user_message_id, resolved_id)
            return resolved_id
        except Exception:
            pass

    assistant_msg = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=content,
        has_table=has_table,
        table_data=table_data,
        table_columns=table_columns,
        tables=all_tables,
        sql_query=sql_query or "",
    )
    result = await db.chat_messages.insert_one(assistant_msg.to_dict())
    saved_id = str(result.inserted_id)
    await _dedupe_assistants_after_user(db, user_id, session_id, user_message_id, saved_id)
    await _set_generation_assistant_id(db, user_message_id, saved_id)
    print(f"[ChatRoute] Upserted partial assistant | id={saved_id} | len={len(content)}")
    return saved_id


async def _save_partial_for_keep_cancel(
    db,
    user_id: str,
    session_id: str,
    user_message_id: str,
    content: str,
    existing_id: str = "",
    has_table: bool = False,
    table_data=None,
    table_columns=None,
    all_tables=None,
    sql_query: str = "",
) -> str:
    """Persist partial assistant content when the user stops mid-stream."""
    doc = await db.chat_generations.find_one({"user_message_id": user_message_id})
    if not doc or doc.get("status") != "cancelled" or not doc.get("keep_partial"):
        return existing_id or ""
    return await _upsert_assistant_for_generation(
        db,
        user_id,
        session_id,
        user_message_id,
        content,
        existing_id,
        has_table,
        table_data,
        table_columns,
        all_tables,
        sql_query,
    )


async def _delete_assistants_after_user(
    db, user_id: str, session_id: str, user_message_id: str
) -> int:
    """Remove assistant replies saved after a cancelled user message."""
    try:
        user_oid = ObjectId(user_message_id)
    except Exception:
        return 0
    user_doc = await db.chat_messages.find_one({"_id": user_oid, "user_id": user_id})
    if not user_doc:
        return 0
    result = await db.chat_messages.delete_many({
        "user_id": user_id,
        "session_id": session_id,
        "role": "assistant",
        "created_at": {"$gte": user_doc["created_at"]},
    })
    return result.deleted_count


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

    # Save the user message IMMEDIATELY — before QuestionResolver runs.
    # QuestionResolver can take 1-4 s; if the user reloads during that window
    # the question must already be persisted so it shows up in history.
    user_msg = ChatMessage(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=question,
    )
    user_insert = await db.chat_messages.insert_one(user_msg.to_dict())
    user_message_id = str(user_insert.inserted_id)
    print(f"[ChatRoute] Saved user message to MongoDB (early, pre-resolver) | id={user_message_id}")

    await db.chat_generations.insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "user_message_id": user_message_id,
        "question": question,
        "status": "processing",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    user_role = getattr(current_user, "role", "executive") or "executive"
    chunk_queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    full_response = ""
    full_response_parts: list[str] = []
    has_table = False
    table_data = []
    table_columns = []
    all_tables: list = []
    sql_query = ""
    error_occurred = False
    already_saved = False
    pre_saved_id = ""

    async def _maybe_persist_streaming_partial(force: bool = False) -> None:
        """Save in-progress tokens so reload/stop can recover partial answers."""
        nonlocal already_saved, pre_saved_id
        if await _is_generation_cancelled(db, user_message_id):
            doc = await db.chat_generations.find_one({"user_message_id": user_message_id})
            if not doc or not doc.get("keep_partial"):
                return
        partial = full_response or "".join(full_response_parts)
        if not partial.strip():
            return
        if not force and len(full_response_parts) % 8 != 0:
            return
        new_id = await _upsert_assistant_for_generation(
            db,
            user_id,
            session_id,
            user_message_id,
            partial,
            pre_saved_id,
            has_table,
            table_data,
            table_columns,
            all_tables,
            sql_query,
        )
        if new_id:
            pre_saved_id = new_id
            already_saved = True

    async def _run_pipeline() -> None:
        """Resolve, stream, save — survives client disconnect/reload."""
        nonlocal full_response, full_response_parts, has_table
        nonlocal table_data, table_columns, all_tables, sql_query
        nonlocal error_occurred, already_saved, pre_saved_id

        try:
            await chunk_queue.put(
                f"data: {json.dumps({'type': 'user_saved', 'user_message_id': user_message_id})}\n\n"
            )

            if await _is_generation_cancelled(db, user_message_id):
                print(f"[ChatRoute] Pipeline aborted early — generation cancelled | id={user_message_id}")
                return

            if settings.USE_VANNA_AI:
                from app.services.vanna_agent import stream_chat_with_database_vanna
                stream_fn = stream_chat_with_database_vanna
                resolved_question = question
                access_denied = False
                denial_reason = ""
                print("[ChatRoute] Using Vanna AI agent")
            else:
                from app.services.question_resolver import resolve_question
                from app.services.langchain_agent import stream_chat_with_database, stream_simple_chat
                loop = asyncio.get_event_loop()
                resolved = await loop.run_in_executor(
                    None,
                    lambda: resolve_question(question, history, role=user_role),
                )
                resolved_question = resolved.get("resolved_question", question) or question
                intent = resolved.get("intent", "sql")
                is_followup = resolved.get("is_followup", False)
                access_denied = resolved.get("access_denied", False)
                denial_reason = resolved.get("denial_reason", "")
                print(
                    f"[ChatRoute] Resolved: intent={intent!r} is_followup={is_followup} "
                    f"access_denied={access_denied} | original='{question[:60]}' | "
                    f"resolved='{resolved_question[:60]}'"
                )
                if access_denied:
                    print(f"[ChatRoute] Access denied for role={user_role}: {denial_reason}")
                elif intent == "sql":
                    stream_fn = stream_chat_with_database
                    print("[ChatRoute] Routing to LangChain SQL agent")
                else:
                    stream_fn = stream_simple_chat
                    print("[ChatRoute] Routing to simple LLM (no SQL)")

            if access_denied:
                denial_msg = (
                    denial_reason
                    or "You don't have rights to access this information. "
                    "As per your current role, you are only assigned access to "
                    "topics relevant to your team."
                )
                full_response = denial_msg
                await chunk_queue.put(
                    f"data: {json.dumps({'type': 'token', 'content': denial_msg})}\n\n"
                )
                await chunk_queue.put(
                    f"data: {json.dumps({'type': 'done', 'has_table': False, 'table_data': [], 'table_columns': [], 'tables': [], 'full_response': denial_msg, 'sql_query': ''})}\n\n"
                )
            else:
                if settings.USE_VANNA_AI:
                    stream_iter = stream_fn(resolved_question, history)
                else:
                    stream_iter = stream_fn(resolved_question, history, role=user_role)

                async for _chunk in stream_iter:
                    if await _is_generation_cancelled(db, user_message_id):
                        print(f"[ChatRoute] Pipeline stream aborted — cancelled | id={user_message_id}")
                        await _maybe_persist_streaming_partial(force=True)
                        break
                    _skip = False
                    try:
                        _raw = _chunk.strip()
                        if _raw.startswith("data: "):
                            _p = json.loads(_raw[6:])
                            _t = _p.get("type")
                            if _t == "token":
                                full_response_parts.append(_p.get("content", ""))
                                await _maybe_persist_streaming_partial()
                            elif _t == "pre_done":
                                full_response = _p.get("full_response", "")
                                has_table = _p.get("has_table", False)
                                table_data = _p.get("table_data", [])
                                table_columns = _p.get("table_columns", [])
                                all_tables = _p.get("tables", [])
                                sql_query = _p.get("sql_query", "") or ""
                                if full_response:
                                    if await _is_generation_cancelled(db, user_message_id):
                                        break
                                    try:
                                        pre_saved_id = await _upsert_assistant_for_generation(
                                            db,
                                            user_id,
                                            session_id,
                                            user_message_id,
                                            full_response,
                                            pre_saved_id,
                                            has_table,
                                            table_data,
                                            table_columns,
                                            all_tables,
                                            sql_query,
                                        )
                                        if pre_saved_id:
                                            already_saved = True
                                            await _mark_generation_completed(db, user_message_id)
                                            print(
                                                f"[ChatRoute] BG pre-saved | id={pre_saved_id} | "
                                                f"has_table={has_table}"
                                            )
                                    except Exception as _pe:
                                        print(f"[ChatRoute] BG pre-save failed: {_pe}")
                                _skip = True
                            elif _t == "done":
                                full_response = _p.get("full_response", "") or full_response
                                if not full_response and full_response_parts:
                                    full_response = "".join(full_response_parts)
                                has_table = _p.get("has_table", False)
                                table_data = _p.get("table_data", [])
                                table_columns = _p.get("table_columns", [])
                                all_tables = _p.get("tables", [])
                                sql_query = _p.get("sql_query", "") or ""
                                # Finalize immediately so reload/poll clears stop UI
                                # even while cosmetic token chunks finish draining.
                                if full_response and not error_occurred:
                                    if not await _is_generation_cancelled(db, user_message_id):
                                        try:
                                            pre_saved_id = await _upsert_assistant_for_generation(
                                                db,
                                                user_id,
                                                session_id,
                                                user_message_id,
                                                full_response,
                                                pre_saved_id,
                                                has_table,
                                                table_data,
                                                table_columns,
                                                all_tables,
                                                sql_query,
                                            )
                                            if pre_saved_id:
                                                already_saved = True
                                            await _mark_generation_completed(db, user_message_id)
                                            print(
                                                f"[ChatRoute] done-event finalized | id={pre_saved_id} | "
                                                f"len={len(full_response)}"
                                            )
                                            try:
                                                chunk_queue.put_nowait(
                                                    f"data: {json.dumps({'type': 'saved', 'assistant_db_id': pre_saved_id})}\n\n"
                                                )
                                            except asyncio.QueueFull:
                                                pass
                                        except Exception as _de:
                                            print(f"[ChatRoute] done-event finalize failed: {_de}")
                            elif _t == "error":
                                error_occurred = True
                    except Exception:
                        pass
                    if not _skip:
                        try:
                            chunk_queue.put_nowait(_chunk)
                        except asyncio.QueueFull:
                            pass

            if not full_response and full_response_parts:
                full_response = "".join(full_response_parts)

            if await _is_generation_cancelled(db, user_message_id):
                print(f"[ChatRoute] Generation cancelled — partial save handled in finally | id={user_message_id}")
            elif full_response and not error_occurred:
                try:
                    if already_saved and pre_saved_id:
                        print(f"[ChatRoute] Using pre-saved id={pre_saved_id} | skipping duplicate insert")
                        await chunk_queue.put(
                            f"data: {json.dumps({'type': 'saved', 'assistant_db_id': pre_saved_id})}\n\n"
                        )
                        await _mark_generation_completed(db, user_message_id)
                    else:
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
                        result = await db.chat_messages.insert_one(assistant_msg.to_dict())
                        saved_id = str(result.inserted_id)
                        pre_saved_id = saved_id
                        already_saved = True
                        print(f"[ChatRoute] Saved assistant message | id={saved_id} | has_table={has_table}")
                        await chunk_queue.put(
                            f"data: {json.dumps({'type': 'saved', 'assistant_db_id': saved_id})}\n\n"
                        )
                        await _mark_generation_completed(db, user_message_id)
                except Exception as save_err:
                    print(f"[ChatRoute] Failed to save assistant message: {save_err}")

        except Exception as _pipe_err:
            print(f"[ChatRoute] Pipeline error: {_pipe_err}")
            import traceback
            traceback.print_exc()
            error_occurred = True
            try:
                await chunk_queue.put(
                    f"data: {json.dumps({'type': 'error', 'content': str(_pipe_err)})}\n\n"
                )
            except Exception:
                pass
        finally:
            cancelled = await _is_generation_cancelled(db, user_message_id)
            if cancelled:
                if not full_response and full_response_parts:
                    full_response = "".join(full_response_parts)
                saved_id = await _save_partial_for_keep_cancel(
                    db,
                    user_id,
                    session_id,
                    user_message_id,
                    full_response,
                    pre_saved_id,
                    has_table,
                    table_data,
                    table_columns,
                    all_tables,
                    sql_query,
                )
                if saved_id:
                    pre_saved_id = saved_id
                    already_saved = True
                await _cleanup_cancelled_generation(db, user_id, session_id, user_message_id)
            elif not already_saved and not error_occurred:
                if not full_response and full_response_parts:
                    full_response = "".join(full_response_parts)
                if full_response:
                    try:
                        _am2 = ChatMessage(
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
                        _r2 = await db.chat_messages.insert_one(_am2.to_dict())
                        pre_saved_id = str(_r2.inserted_id)
                        already_saved = True
                        print(f"[ChatRoute] Pipeline fallback save | id={pre_saved_id}")
                        await _mark_generation_completed(db, user_message_id)
                    except Exception as _e2:
                        print(f"[ChatRoute] Pipeline fallback save failed: {_e2}")
            elif already_saved and pre_saved_id:
                await _mark_generation_completed(db, user_message_id)
            # Never leave a saved generation stuck in processing
            _gen_doc = await db.chat_generations.find_one({"user_message_id": user_message_id})
            if _gen_doc and _gen_doc.get("status") == "processing" and already_saved:
                await _mark_generation_completed(db, user_message_id)
                print(
                    f"[ChatRoute] Safety-completed stuck generation | id={user_message_id}"
                )
            try:
                chunk_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            print(
                f"[ChatRoute] Pipeline done | cancelled={cancelled} | "
                f"already_saved={already_saved} | id={pre_saved_id or 'none'}"
            )

    asyncio.create_task(_run_pipeline())

    async def event_generator():
        try:
            while True:
                try:
                    _qchunk = await asyncio.wait_for(chunk_queue.get(), timeout=320.0)
                except asyncio.TimeoutError:
                    print("[ChatRoute] Queue read timeout — stream assumed ended")
                    break
                if _qchunk is None:
                    break
                yield _qchunk
        except (asyncio.CancelledError, GeneratorExit):
            print("[ChatRoute] Client disconnected — pipeline continues in background")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/pending", response_model=ChatPendingResponse)
async def get_chat_pending(current_user: User = Depends(get_current_user)):
    """Return whether this user has a generation still running (DB source of truth)."""
    user_id = str(current_user._id)
    db = get_database()
    doc = await db.chat_generations.find_one(
        {"user_id": user_id, "status": "processing"},
        sort=[("created_at", -1)],
    )
    if not doc:
        return ChatPendingResponse(active=False)
    return ChatPendingResponse(
        active=True,
        user_message_id=doc.get("user_message_id", ""),
        question=doc.get("question", ""),
    )


@router.post("/cancel")
async def cancel_chat_generation(
    body: ChatCancelRequest,
    current_user: User = Depends(get_current_user),
):
    """Stop an in-flight generation — prevents assistant reply from being kept."""
    user_id = str(current_user._id)
    db = get_database()
    session_id = await _get_or_create_session(db, user_id)

    query: dict = {"user_id": user_id, "status": "processing"}
    if body.user_message_id:
        query["user_message_id"] = body.user_message_id

    doc = await db.chat_generations.find_one(query, sort=[("created_at", -1)])
    if not doc:
        print(f"[ChatRoute] Cancel: no active generation for user={user_id}")
        return {"cancelled": False}

    user_message_id = doc["user_message_id"]
    await db.chat_generations.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "status": "cancelled",
                "keep_partial": body.keep_partial,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    deleted = 0
    user_deleted = False
    partial_saved_id = ""
    if body.keep_partial:
        partial_text = (body.partial_content or "").strip()
        if partial_text:
            existing_id = doc.get("assistant_message_id") or await _find_first_assistant_after_user(
                db, user_id, session_id, user_message_id
            )
            partial_saved_id = await _upsert_assistant_for_generation(
                db,
                user_id,
                session_id,
                user_message_id,
                partial_text,
                existing_id,
            )
            print(
                f"[ChatRoute] Cancel saved partial assistant | id={partial_saved_id} | "
                f"len={len(partial_text)}"
            )
    else:
        deleted = await _delete_assistants_after_user(db, user_id, session_id, user_message_id)
        user_deleted = await _delete_user_message(db, user_id, user_message_id)
    print(
        f"[ChatRoute] Cancelled generation | user_message_id={user_message_id} | "
        f"deleted_assistants={deleted} | deleted_user={user_deleted} | "
        f"partial_saved={bool(partial_saved_id)}"
    )
    return {
        "cancelled": True,
        "user_message_id": user_message_id,
        "question": doc.get("question", ""),
        "user_message_deleted": user_deleted,
        "assistant_db_id": partial_saved_id or None,
    }


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = Query(default=1000, ge=1, le=100000),
    current_user: User = Depends(get_current_user),
):
    """
    Return chat history for the current user, newest last.
    Used on page load to restore previous conversation.
    Fetches the *most recent* N messages so new conversations are never lost.
    """
    user_id = str(current_user._id)
    print(f"[ChatRoute] /history called | user={user_id} | limit={limit}")

    db = get_database()
    session_id = await _get_or_create_session(db, user_id)

    # Sort descending to grab the LATEST messages, then reverse for display
    cursor = db.chat_messages.find(
        {"user_id": user_id, "session_id": session_id}
    ).sort("created_at", -1).limit(limit)

    messages = await cursor.to_list(length=limit)
    messages.reverse()  # oldest-first for UI display order
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
                created_at=m["created_at"].isoformat() + "Z" if isinstance(m["created_at"], datetime) else str(m["created_at"]),
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
    Stream a role-aware, data-driven AI summary for management/leadership.

    Context used (merged):
      1. Pre-fetched business KPI snapshot from MongoDB (real numbers per role)
      2. Table row counts from SQL Server (existing approach, kept for breadth)

    Saves the full result to the user's chat_session document after streaming.
    """
    user_id = str(current_user._id)
    user_role = getattr(current_user, "role", "executive") or "executive"
    print(f"[ChatRoute] /db/summary called | user={user_id} | role={user_role}")

    from app.services.langchain_agent import stream_generate_report, get_table_row_counts
    from app.services.db_snapshot import get_snapshot_context

    # --- Build context: snapshot KPIs (role-specific, real numbers) + row counts ---
    print(f"[ChatRoute] Loading snapshot context for role={user_role}...")
    snapshot_context = await get_snapshot_context(user_role)
    print(f"[ChatRoute] Snapshot context loaded | chars={len(snapshot_context)}")

    try:
        row_counts_context = get_table_row_counts()
        print(f"[ChatRoute] Row counts loaded | chars={len(row_counts_context)}")
    except Exception as e:
        print(f"[ChatRoute] get_table_row_counts failed: {e}")
        row_counts_context = ""

    # Merge both context sources
    combined_context_parts = []
    if snapshot_context:
        combined_context_parts.append(snapshot_context)
    if row_counts_context:
        combined_context_parts.append(row_counts_context)
    combined_context = "\n\n".join(combined_context_parts)

    # Role-specific scope note for the prompt
    _role_scope = {
        "executive": (
            "You are writing for the executive leadership team. Cover ALL business areas: "
            "sales performance, profitability, procurement, inventory, customer and vendor relationships, "
            "returns, payments, and backorders."
        ),
        "sales": (
            "You are writing for the sales team. Focus on: sales revenue, customer activity, "
            "inventory availability for sales, discounts, customer returns, and payment status. "
            "Do not include vendor analytics, cost data, or profitability margins."
        ),
        "operations": (
            "You are writing for the operations team. Focus on: inventory levels, stock availability, "
            "reorder alerts, warehouse activity, backorders, and picking/reservation status. "
            "Do not include sales revenue, customer details, or vendor financials."
        ),
    }
    role_instruction = _role_scope.get(user_role, _role_scope["executive"])

    prompt = (
        f"{role_instruction} "
        "Using the real business figures in the Data Context, write a clear one-page summary. "
        "Whenever you reference a figure, explicitly state the year it belongs to "
        "(e.g. 'In 2025, total revenue was...' or 'As of 2025, inventory value stands at...'). "
        "Highlight the most important numbers — revenue, volumes, inventory health, outstanding items — "
        "and explain what they mean for the business in plain language. "
        "Use markdown (##, ###). Do not use technical terms, table names, or column names. "
        "Use only the figures from the Data Context; never invent numbers. "
        "Do not mention data gaps, missing records, or unavailable areas."
    )

    _summary_system = (
        "You are a business analyst writing a data summary for leadership. "
        "Start directly with the first section header (e.g. ## Business Performance Overview). "
        "Do NOT add a document title. Format as clean markdown with headers and bullet points. "
        "Do NOT wrap output in code fences. "
        "Tone: clear, confident, business-focused. "
        "Always include the specific year when citing any figure (e.g. 'In 2025...' or 'Year 2025:'). "
        "Always reference actual numbers from the Data Context to support your statements. "
        "Never mention data gaps, missing data, or technical terms. "
        "NEVER add footnote markers, reference numbers, or citations like (1), (2), [1], [2] anywhere in the output."
    )

    print(f"[ChatRoute] Starting summary stream | role={user_role} | context_chars={len(combined_context)}")
    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context=combined_context,
                template="summary",
                custom_system_prompt=_summary_system,
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
                    {"$set": {"db_summary": full_content, "updated_at": datetime.utcnow()}},
                    upsert=True,
                )
                print(f"[ChatRoute] Saved db_summary | user={user_id} | role={user_role} | len={len(full_content)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/db/questions")
async def stream_db_questions(current_user: User = Depends(get_current_user)):
    """
    Stream role-specific AI-generated suggested questions.

    Uses the pre-fetched KPI snapshot (real figures) + a plain-English schema
    summary for the user's role so the LLM generates questions that are:
      - Answerable from data the role actually has access to
      - Written in natural business language (no SQL/technical terms)
      - Grounded in real current numbers (not generic)

    Parses the numbered list and saves to the user's chat_session document.
    """
    user_id = str(current_user._id)
    user_role = getattr(current_user, "role", "executive") or "executive"
    print(f"[ChatRoute] /db/questions called | user={user_id} | role={user_role}")

    from app.services.langchain_agent import stream_generate_report
    from app.services.db_snapshot import get_snapshot_context, get_schema_summary_for_role

    print(f"[ChatRoute] Loading snapshot + schema for questions | role={user_role}...")
    snapshot_context = await get_snapshot_context(user_role)
    schema_summary = get_schema_summary_for_role(user_role)
    print(f"[ChatRoute] Questions context ready | snapshot_chars={len(snapshot_context)} | schema_chars={len(schema_summary)}")

    # Role-specific persona for the question generator
    _role_persona = {
        "executive": "a CEO or executive leadership team member",
        "sales": "a sales manager or sales team leader",
        "operations": "an operations manager or warehouse team leader",
    }
    persona = _role_persona.get(user_role, "a business manager")

    questions_context = (
        f"Data Scope (what information is available to analyze):\n{schema_summary}"
        + (f"\n\n{snapshot_context}" if snapshot_context else "")
    )

    prompt = (
        f"Generate exactly 10 questions that {persona} would naturally ask about business performance. "
        "Base the questions ONLY on the topics covered by the available data described in the Data Context. "
        "Every question must be directly answerable from the available data. "
        "Write questions in plain, everyday business language — no technical terms, no database jargon, "
        "no column names, no table names. "
        "IMPORTANT: Do NOT embed any numbers, amounts, percentages, or figures inside the questions. "
        "Questions must be open-ended and exploratory — they should ask 'how', 'what', 'which', or 'why', "
        "not reference specific values. "
        "Return ONLY a numbered list: 1. ... 2. ... 10. ..."
    )

    _questions_system = (
        "You are a business analyst helping leadership discover useful questions about their data. "
        "Return ONLY a plain numbered list of exactly 10 questions — nothing else. "
        "No title, no preamble, no explanation, no closing remarks. "
        "Format:\n1. <question>\n2. <question>\n...\n10. <question>\n"
        "Questions must be in natural business language. No SQL, no table names, no technical terms. "
        "Never include specific numbers, dollar amounts, percentages, or figures inside the question text."
    )

    print(f"[ChatRoute] Starting questions stream | role={user_role} | context_chars={len(questions_context)}")
    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context=questions_context,
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
                print(f"[ChatRoute] Saved {len(questions)} db_questions | user={user_id} | role={user_role}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/db/report")
async def stream_db_report(current_user: User = Depends(get_current_user)):
    """
    Stream a role-aware, data-driven leadership report.

    Uses the pre-fetched KPI snapshot from MongoDB as real-number context
    so the report contains actual business figures, not generic descriptions.
    Saves the full result to the user's chat_session document after streaming.
    """
    user_id = str(current_user._id)
    user_role = getattr(current_user, "role", "executive") or "executive"
    print(f"[ChatRoute] /db/report called | user={user_id} | role={user_role}")

    from app.services.langchain_agent import stream_generate_report
    from app.services.db_snapshot import get_snapshot_context

    print(f"[ChatRoute] Loading snapshot context for report | role={user_role}...")
    snapshot_context = await get_snapshot_context(user_role)
    print(f"[ChatRoute] Snapshot context loaded | chars={len(snapshot_context)}")

    # Role-specific section guidance
    _role_sections = {
        "executive": (
            "Include these sections: Business Overview; Sales & Revenue Performance; "
            "Profitability & Margins; Procurement & Vendor Activity; Inventory Health; "
            "Customer & Vendor Relationships; Returns & Payments; Decision Support Highlights."
        ),
        "sales": (
            "Include these sections: Sales Performance Overview; Customer Activity; "
            "Discount & Pricing Overview; Inventory Availability for Sales; "
            "Customer Returns Summary; Payment Status; Key Opportunities."
        ),
        "operations": (
            "Include these sections: Inventory Health Overview; Stock Availability; "
            "Reorder & Low-Stock Alerts; Warehouse Activity; Backorder Status; "
            "Operational Action Points."
        ),
    }
    section_guide = _role_sections.get(user_role, _role_sections["executive"])

    prompt = (
        f"Write a detailed business report for {user_role}-level readers using the real figures in the Data Context. "
        f"{section_guide} "
        "For each section, reference the actual numbers from the Data Context and explain what they mean. "
        "Use markdown (##, ###) with bullet points. "
        "Write in clear business language — no technical terms, table names, or column names. "
        "Never invent numbers. Do not mention data gaps or missing records."
    )

    _report_system = (
        "You are a business analyst writing a structured report for leadership. "
        "Start directly with the first section header — do NOT add a document title. "
        "Use markdown headers (##, ###), bullet points, and spacing between sections. "
        "Do NOT wrap the output in code fences. "
        "Anchor every claim to a number from the Data Context. "
        "Always include the specific year when citing any figure (e.g. 'In 2025...' or 'Year 2025:'). "
        "Keep the tone professional and business-focused. "
        "Never mention missing data, data gaps, or technical/database terminology. "
        "NEVER add footnote markers, reference numbers, superscripts, or inline citations like "
        "(1), (2), (1, 2), [1], [2], ^1, ^2, or any similar numbering — they must not appear anywhere in the output."
    )

    print(f"[ChatRoute] Starting report stream | role={user_role} | context_chars={len(snapshot_context)}")
    db = get_database()

    async def event_generator():
        full_content = ""
        try:
            async for chunk in stream_generate_report(
                prompt=prompt,
                items_context=snapshot_context,
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
                print(f"[ChatRoute] Saved db_report | user={user_id} | role={user_role} | len={len(full_content)}")

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
            b["created_at"] = b["created_at"].isoformat() + "Z"
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
        "created_at": datetime.utcnow().isoformat() + "Z",
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


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message_pair(
    message_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete an assistant message and its preceding user question."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] DELETE /messages/{message_id} | user={user_id}")

    db = get_database()

    # Validate ObjectId before querying — surface a clear 400 instead of a 500
    try:
        oid = ObjectId(message_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message id")

    # Find the assistant message
    assistant_msg = await db.chat_messages.find_one(
        {"_id": oid, "user_id": user_id}
    )
    if not assistant_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    deleted_ids = [assistant_msg["_id"]]

    # Find the user message immediately before this assistant message
    if assistant_msg.get("role") == "assistant":
        user_msg = await db.chat_messages.find_one(
            {
                "user_id": user_id,
                "session_id": assistant_msg["session_id"],
                "role": "user",
                "created_at": {"$lte": assistant_msg["created_at"]},
            },
            sort=[("created_at", -1)],
        )
        if user_msg:
            deleted_ids.append(user_msg["_id"])
    elif assistant_msg.get("role") == "user":
        # If the caller passed the user message id, also find the next assistant msg
        asst_msg = await db.chat_messages.find_one(
            {
                "user_id": user_id,
                "session_id": assistant_msg["session_id"],
                "role": "assistant",
                "created_at": {"$gte": assistant_msg["created_at"]},
            },
            sort=[("created_at", 1)],
        )
        if asst_msg:
            deleted_ids.append(asst_msg["_id"])

    result = await db.chat_messages.delete_many({"_id": {"$in": deleted_ids}})
    print(f"[ChatRoute] Deleted {result.deleted_count} messages (pair)")


@router.delete("/history")
async def clear_chat_history(current_user: User = Depends(get_current_user)):
    """Clear all chat messages for the current user."""
    user_id = str(current_user._id)
    print(f"[ChatRoute] /history DELETE called | user={user_id}")

    db = get_database()
    result = await db.chat_messages.delete_many({"user_id": user_id})
    print(f"[ChatRoute] Deleted {result.deleted_count} messages")

    return {"message": f"Cleared {result.deleted_count} messages"}
