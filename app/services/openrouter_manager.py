"""
OpenRouter model catalog cache.

Mirrors the exact pattern of mcp_manager.py: fetch the catalog once at
startup, refresh it periodically in the background, and expose read-only
in-memory helpers to the rest of the app. All network I/O is skipped
entirely unless OPENROUTER_ENABLED=true and an API key is configured, so
this module is a complete no-op when the feature is off.

The catalog exposed to the frontend/model-picker is filtered down to models
that are BOTH:
  - free  (pricing.prompt == "0" and pricing.completion == "0"), and
  - tool-calling capable ("tools" in supported_parameters)
so that no matter what a user picks, the orchestrator/SQL-subagent ReAct
loops (which rely on tool calling) keep working.
"""

import asyncio
import time
from typing import Optional

import httpx

from app.config import settings

print("[OpenRouterManager] Module loaded")

_cached_models: list[dict] = []       # filtered: free + tool-capable (for the picker UI)
_models_by_id: dict[str, dict] = {}   # raw catalog entries, keyed by model id (pricing/support lookups)
_loaded_at: Optional[float] = None
_last_error: str = ""
_load_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    """Lazily create the lock inside a running event loop."""
    global _load_lock
    if _load_lock is None:
        _load_lock = asyncio.Lock()
    return _load_lock


def is_openrouter_configured() -> bool:
    """True when OpenRouter is enabled and an API key has been supplied."""
    return bool(settings.OPENROUTER_ENABLED and settings.OPENROUTER_API_KEY.strip())


def _to_float(value, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_free(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    return _to_float(pricing.get("prompt"), 1.0) == 0.0 and _to_float(pricing.get("completion"), 1.0) == 0.0


def _is_tool_capable(model: dict) -> bool:
    params = model.get("supported_parameters") or []
    return "tools" in params


async def init_openrouter_models(timeout: float = 15.0) -> int:
    """Fetch and cache the OpenRouter model catalog. Call once at startup.

    Never raises — logs and leaves the cache empty on failure so an
    OpenRouter outage can never block server startup. When the cache is
    empty, get_cached_openrouter_models() simply returns [] and the
    frontend model picker hides itself.
    """
    global _cached_models, _models_by_id, _loaded_at, _last_error

    if not is_openrouter_configured():
        print("[OpenRouterManager] OpenRouter disabled or API key missing — skipping catalog fetch")
        return 0

    t0 = time.time()
    try:
        headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY.strip()}"}
        url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        all_models = data.get("data") or []
        _models_by_id = {m["id"]: m for m in all_models if m.get("id")}
        filtered = [m for m in all_models if _is_free(m) and _is_tool_capable(m)]
        _cached_models = filtered
        _loaded_at = time.time()
        _last_error = ""
        elapsed = _loaded_at - t0
        print(
            f"[OpenRouterManager] Cached {len(filtered)}/{len(all_models)} free+tool-capable "
            f"OpenRouter model(s) in {elapsed:.2f}s"
        )
        return len(filtered)
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        print(f"[OpenRouterManager] Catalog fetch FAILED (model picker will stay hidden until this recovers): {_last_error}")
        return 0


async def _maybe_refresh() -> None:
    """Best-effort background refresh when the cache is stale or was never loaded."""
    stale = (
        _loaded_at is None
        or (time.time() - _loaded_at) > settings.OPENROUTER_MODELS_REFRESH_MINUTES * 60
    )
    if not stale:
        return
    lock = _get_lock()
    if lock.locked():
        return
    async with lock:
        stale_now = (
            _loaded_at is None
            or (time.time() - _loaded_at) > settings.OPENROUTER_MODELS_REFRESH_MINUTES * 60
        )
        if stale_now:
            await init_openrouter_models()


async def get_cached_openrouter_models() -> list[dict]:
    """Return cached, filtered (free + tool-capable) OpenRouter models,
    refreshing in the background first if stale/empty."""
    if not is_openrouter_configured():
        return []
    await _maybe_refresh()
    return _cached_models


def get_model_supported_params(model_id: str) -> set[str]:
    """Synchronous, in-memory lookup — used by the LLM factory to decide
    whether seed/frequency_penalty/presence_penalty are safe to send to a
    given model. Returns an empty set (== "unknown") if the model isn't in
    the cache; callers should treat unknown as "try, but don't assume"."""
    m = _models_by_id.get(model_id)
    if not m:
        return set()
    return set(m.get("supported_parameters") or [])


def get_model_pricing(model_id: str) -> Optional[dict]:
    """Per-token USD pricing straight from OpenRouter's own catalog, or None
    if the model isn't cached. {"prompt": float, "completion": float}."""
    m = _models_by_id.get(model_id)
    if not m:
        return None
    pricing = m.get("pricing") or {}
    if pricing.get("prompt") is None or pricing.get("completion") is None:
        return None
    return {
        "prompt": _to_float(pricing.get("prompt"), 0.0),
        "completion": _to_float(pricing.get("completion"), 0.0),
    }


def is_model_allowed(model_id: str) -> bool:
    """True if model_id is currently in the free+tool-capable cache — used to
    validate a user's model preference before saving it."""
    return any(m.get("id") == model_id for m in _cached_models)


def get_openrouter_status() -> dict:
    """Diagnostic snapshot — useful for logging / the catalog endpoint."""
    return {
        "configured": is_openrouter_configured(),
        "model_count": len(_cached_models),
        "loaded_at": _loaded_at,
        "last_error": _last_error,
    }
