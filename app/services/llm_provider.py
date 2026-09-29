"""
Centralized chat-LLM factory + per-call cost/token usage tracking.

Every LLM call site in the app (question resolver, orchestrator, SQL
subagent, visualize chart-picker, simple chat, report generation, legacy
Vanna path) goes through get_chat_llm() instead of constructing
ChatOpenAI/ChatGoogleGenerativeAI directly. This is what makes the
per-user OpenRouter model choice apply everywhere with a single switch.

Design notes (why it's structured this way):
  - get_chat_llm() returns the RAW LangChain chat model (never a wrapper),
    so it can still be handed straight to langgraph's create_react_agent
    or streamed/invoked exactly like before — zero risk of breaking tool
    calling or streaming behavior.
  - Because the model object isn't wrapped, usage capture is a separate,
    explicit step: call sites pass the LLM's response (or, for LangGraph
    runs, the full message list) through record_llm_usage()/
    record_llm_usage_from_messages(). These are PURE, synchronous,
    in-memory functions — they only append a plain dict to
    llm_ctx["usage_log"] and never touch the database. That makes them
    safe to call from anywhere, including sync code running in a worker
    thread (e.g. question_resolver.resolve_question via run_in_executor),
    where awaiting an async Motor call would be unsafe (Motor's client is
    bound to the event loop it was created on).
  - The actual MongoDB write happens exactly once per user turn, via the
    async flush_usage_log(), called from app/routes/chat.py after the
    whole pipeline finishes.
  - When OPENROUTER_ENABLED=false (default), get_chat_llm() falls through
    to the exact same USE_GEMINI -> OpenAI gpt-4.1 logic that
    langchain_agent._create_chat_llm()/_create_mini_llm() used before this
    refactor, so behavior is unchanged for every existing deployment.
"""

from datetime import datetime
from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import settings

print("[LLMProvider] Module loaded")


# ---------------------------------------------------------------------------
# Model preference resolution
# ---------------------------------------------------------------------------

def resolve_model_pref(user) -> Optional[dict]:
    """Resolve the per-user OpenRouter model preference to use for one request.

    Returns None whenever OpenRouter is disabled/unconfigured, or the user
    (and the admin default) have no model selected yet — in which case every
    downstream get_chat_llm() call transparently uses the existing
    USE_GEMINI/OpenAI behavior.
    """
    if not (settings.OPENROUTER_ENABLED and settings.OPENROUTER_API_KEY.strip()):
        return None
    model_id = (getattr(user, "preferred_model", None) or "").strip()
    if not model_id:
        model_id = settings.OPENROUTER_DEFAULT_MODEL.strip()
    if not model_id:
        return None
    return {"provider": "openrouter", "model": model_id}


def new_llm_ctx(model_pref: Optional[dict]) -> dict:
    """Build a fresh per-request context dict threaded through every LLM call
    site. `usage_log` is a plain list every call site appends plain dicts to."""
    return {"model_pref": model_pref, "usage_log": []}


# ---------------------------------------------------------------------------
# Chat LLM factory
# ---------------------------------------------------------------------------

def get_chat_llm(
    *,
    llm_ctx: Optional[dict] = None,
    streaming: bool = False,
    callbacks: Optional[list] = None,
    max_tokens: Optional[int] = None,
):
    """Build the chat LLM to use for one call, honoring precedence:
    OpenRouter (per-user pick, only when enabled) > Gemini (USE_GEMINI) >
    OpenAI gpt-4.1 (default, unchanged from before this feature existed).

    Returns (llm, provider, model_id) — provider/model_id are needed by the
    caller to attribute cost/usage correctly.
    """
    model_pref = (llm_ctx or {}).get("model_pref") if llm_ctx else None

    if (
        settings.OPENROUTER_ENABLED
        and settings.OPENROUTER_API_KEY.strip()
        and model_pref
        and model_pref.get("provider") == "openrouter"
        and model_pref.get("model")
    ):
        model_id = model_pref["model"]
        try:
            from app.services.openrouter_manager import get_model_supported_params

            kwargs: dict = dict(
                model=model_id,
                temperature=0,
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY,
            )
            # Only send determinism params the model actually advertises support
            # for (unknown/uncached models: try anyway, OpenRouter ignores
            # unsupported params rather than erroring for most providers).
            supported = get_model_supported_params(model_id)
            if not supported or "seed" in supported:
                kwargs["seed"] = 42
            if not supported or "frequency_penalty" in supported:
                kwargs["frequency_penalty"] = 0
            if not supported or "presence_penalty" in supported:
                kwargs["presence_penalty"] = 0
            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            extra_headers = {}
            if settings.OPENROUTER_APP_URL.strip():
                extra_headers["HTTP-Referer"] = settings.OPENROUTER_APP_URL.strip()
            if settings.OPENROUTER_APP_NAME.strip():
                extra_headers["X-Title"] = settings.OPENROUTER_APP_NAME.strip()
            if extra_headers:
                kwargs["default_headers"] = extra_headers

            if streaming:
                kwargs["streaming"] = True
            if callbacks:
                kwargs["callbacks"] = callbacks

            print(f"[LLMProvider] Using OpenRouter model={model_id!r}")
            return ChatOpenAI(**kwargs), "openrouter", model_id
        except Exception as e:
            print(f"[LLMProvider] OpenRouter LLM init failed ({type(e).__name__}: {e}) — falling back to default provider")

    if settings.USE_GEMINI and settings.GEMINI_API_KEY:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            kwargs = dict(
                model="gemini-2.5-pro",
                temperature=0,
                google_api_key=settings.GEMINI_API_KEY,
            )
            if max_tokens:
                kwargs["max_output_tokens"] = max_tokens
            if streaming:
                kwargs["streaming"] = True
            if callbacks:
                kwargs["callbacks"] = callbacks
            print("[LLMProvider] Using Gemini 2.5 Pro")
            return ChatGoogleGenerativeAI(**kwargs), "gemini", "gemini-2.5-pro"
        except ImportError as e:
            print(f"[LLMProvider] USE_GEMINI=True but langchain_google_genai not available: {e}. Falling back to GPT.")
        except Exception as e:
            print(f"[LLMProvider] Gemini init failed: {e}. Falling back to GPT.")

    kwargs = dict(
        model="gpt-4.1",
        temperature=0,
        seed=42,
        frequency_penalty=0,
        presence_penalty=0,
        openai_api_key=settings.OPENAI_API_KEY,
    )
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if streaming:
        kwargs["streaming"] = True
    if callbacks:
        kwargs["callbacks"] = callbacks
    print("[LLMProvider] Using gpt-4.1 (OpenAI)")
    return ChatOpenAI(**kwargs), "openai", "gpt-4.1"


# ---------------------------------------------------------------------------
# Usage extraction (pure, no I/O)
# ---------------------------------------------------------------------------

def usage_from_response(response) -> Optional[dict]:
    """Extract {prompt_tokens, completion_tokens, total_tokens} from a single
    AIMessage/ChatResult. Tolerant of provider differences — returns None
    when no usage info is present rather than raising."""
    if response is None:
        return None
    um = getattr(response, "usage_metadata", None)
    if um:
        input_tokens = um.get("input_tokens", 0) or 0
        output_tokens = um.get("output_tokens", 0) or 0
        total_tokens = um.get("total_tokens") or (input_tokens + output_tokens)
        return {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
    rm = getattr(response, "response_metadata", None) or {}
    tu = rm.get("token_usage") or rm.get("usage")
    if tu:
        return {
            "prompt_tokens": tu.get("prompt_tokens", 0) or 0,
            "completion_tokens": tu.get("completion_tokens", 0) or 0,
            "total_tokens": tu.get("total_tokens", 0) or 0,
        }
    return None


def sum_usage_from_messages(messages: Optional[list]) -> Optional[dict]:
    """Sum usage across every message that carries usage metadata — used for
    LangGraph ReAct runs (create_react_agent), where one logical "step"
    (orchestrator / sql_subagent) is actually N underlying LLM calls."""
    prompt_tokens = completion_tokens = total_tokens = 0
    found = False
    for m in messages or []:
        usage = usage_from_response(m)
        if not usage:
            continue
        found = True
        prompt_tokens += usage["prompt_tokens"]
        completion_tokens += usage["completion_tokens"]
        total_tokens += usage["total_tokens"]
    if not found:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------

def _price_per_token(provider: str, model: str) -> tuple[float, float]:
    """(prompt_price_per_token, completion_price_per_token) in USD."""
    if provider == "openrouter":
        from app.services.openrouter_manager import get_model_pricing

        pricing = get_model_pricing(model)
        if pricing:
            return pricing["prompt"], pricing["completion"]
        return 0.0, 0.0
    entry = (settings.LLM_PRICING_TABLE or {}).get(f"{provider}:{model}")
    if entry:
        return (
            float(entry.get("prompt_per_token", 0) or 0),
            float(entry.get("completion_per_token", 0) or 0),
        )
    return 0.0, 0.0


# ---------------------------------------------------------------------------
# Recording (in-memory accumulation) + flushing (the one place that hits Mongo)
# ---------------------------------------------------------------------------

def record_llm_usage(
    usage: Optional[dict],
    *,
    step: str,
    provider: str,
    model: str,
    llm_ctx: Optional[dict] = None,
) -> None:
    """Append one usage entry to llm_ctx["usage_log"]. Pure/in-memory — never
    touches the database, so it's safe to call from sync or async code, on
    any thread. No-ops when llm_ctx is None (e.g. call sites outside the
    authenticated chat pipeline, or usage metadata wasn't available)."""
    if llm_ctx is None or not usage:
        return
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    if total_tokens <= 0:
        return
    prompt_price, completion_price = _price_per_token(provider, model)
    cost_usd = round(prompt_tokens * prompt_price + completion_tokens * completion_price, 8)
    entry = {
        "step": step,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
    }
    llm_ctx.setdefault("usage_log", []).append(entry)
    print(
        f"[LLMProvider] usage recorded | step={step} provider={provider} model={model} "
        f"tokens={total_tokens} cost=${cost_usd:.6f}"
    )


async def flush_usage_log(
    db,
    llm_ctx: Optional[dict],
    *,
    user_id: str,
    session_id: str,
    user_message_id: str,
) -> None:
    """Persist every usage entry accumulated for one user turn to MongoDB in
    a single batch insert. The only place this module touches the database.
    Safe no-op when there is nothing to flush or db is unavailable."""
    if not llm_ctx or db is None:
        return
    entries = llm_ctx.get("usage_log") or []
    if not entries:
        return
    now = datetime.utcnow()
    docs = []
    for e in entries:
        doc = dict(e)
        doc.update(
            {
                "user_id": user_id,
                "session_id": session_id,
                "user_message_id": user_message_id,
                "created_at": now,
            }
        )
        docs.append(doc)
    try:
        await db.llm_usage_logs.insert_many(docs)
        total_cost = sum(d.get("cost_usd", 0) for d in docs)
        total_tokens = sum(d.get("total_tokens", 0) for d in docs)
        print(
            f"[LLMProvider] Flushed {len(docs)} usage log(s) | user_message_id={user_message_id} | "
            f"total_tokens={total_tokens} | total_cost=${total_cost:.6f}"
        )
    except Exception as e:
        print(f"[LLMProvider] Failed to flush usage log: {type(e).__name__}: {e}")
