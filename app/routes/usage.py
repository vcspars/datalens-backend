"""Per-call LLM cost/token usage — read-side aggregation routes.

Writes happen exclusively through app.services.llm_provider.flush_usage_log(),
called once per user turn from app/routes/chat.py. This module only reads
the llm_usage_logs collection back out for the UsageCosts.tsx page.
"""
from fastapi import APIRouter, Depends, Query

from app.database import get_database
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/usage", tags=["usage"])

print("[UsageRoute] Router initialized")


@router.get("/queries")
async def get_usage_queries(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """One row per user turn (user_message_id): the resolved question text
    (from chat_messages), total tokens, total cost, and timestamp — scoped to
    the current user, same as chat history."""
    db = get_database()
    user_id = str(current_user._id)

    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": "$user_message_id",
                "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                "total_completion_tokens": {"$sum": "$completion_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_cost_usd": {"$sum": "$cost_usd"},
                "step_count": {"$sum": 1},
                "created_at": {"$min": "$created_at"},
            }
        },
        {"$sort": {"created_at": -1}},
        {"$skip": offset},
        {"$limit": limit},
    ]
    rows = await db.llm_usage_logs.aggregate(pipeline).to_list(length=limit)

    # Total row count (for pagination) — cheap distinct count on the same scope.
    total_ids = await db.llm_usage_logs.distinct("user_message_id", {"user_id": user_id})
    total_count = len(total_ids)

    # Attach the original question text where we can find it.
    user_message_ids = [r["_id"] for r in rows if r.get("_id")]
    questions_by_id: dict = {}
    if user_message_ids:
        from bson import ObjectId

        object_ids = []
        for mid in user_message_ids:
            try:
                object_ids.append(ObjectId(mid))
            except Exception:
                continue
        if object_ids:
            cursor = db.chat_messages.find({"_id": {"$in": object_ids}, "role": "user"})
            async for m in cursor:
                questions_by_id[str(m["_id"])] = m.get("content", "")

    items = [
        {
            "user_message_id": r["_id"],
            "question": questions_by_id.get(r["_id"], ""),
            "total_prompt_tokens": r.get("total_prompt_tokens", 0),
            "total_completion_tokens": r.get("total_completion_tokens", 0),
            "total_tokens": r.get("total_tokens", 0),
            "total_cost_usd": round(r.get("total_cost_usd", 0) or 0, 6),
            "step_count": r.get("step_count", 0),
            "created_at": r["created_at"].isoformat() + "Z" if r.get("created_at") else None,
        }
        for r in rows
    ]

    return {"items": items, "total": total_count, "limit": limit, "offset": offset}


@router.get("/queries/{user_message_id}/steps")
async def get_usage_steps_for_query(
    user_message_id: str,
    current_user: User = Depends(get_current_user),
):
    """The per-step breakdown for one user turn (step name, provider/model,
    tokens, cost) — scoped to the current user."""
    db = get_database()
    user_id = str(current_user._id)

    cursor = db.llm_usage_logs.find(
        {"user_id": user_id, "user_message_id": user_message_id}
    ).sort("created_at", 1)
    docs = await cursor.to_list(length=200)

    steps = [
        {
            "step": d.get("step"),
            "provider": d.get("provider"),
            "model": d.get("model"),
            "prompt_tokens": d.get("prompt_tokens", 0),
            "completion_tokens": d.get("completion_tokens", 0),
            "total_tokens": d.get("total_tokens", 0),
            "cost_usd": round(d.get("cost_usd", 0) or 0, 6),
            "created_at": d["created_at"].isoformat() + "Z" if d.get("created_at") else None,
        }
        for d in docs
    ]

    return {
        "user_message_id": user_message_id,
        "steps": steps,
        "total_tokens": sum(s["total_tokens"] for s in steps),
        "total_cost_usd": round(sum(s["cost_usd"] for s in steps), 6),
    }
