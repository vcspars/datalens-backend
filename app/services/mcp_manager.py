"""
MCP (Model Context Protocol) tool cache manager.

Connects to a single hosted MCP server (HTTPS, Streamable HTTP transport) and
caches its tool catalog at startup — mirroring the SQLDatabase warm-up in
langchain_agent.py and the KPI snapshot warm-up in db_snapshot.py.

The cached tools are LangChain-compatible BaseTool objects (via
langchain-mcp-adapters). Each tool call opens its own HTTP session under the
hood — the tool objects themselves only carry connection config, so they are
safe to cache in memory and reuse across requests indefinitely (until the
periodic refresh replaces them).
"""

import asyncio
import time
from typing import Optional

from app.config import settings

print("[MCPManager] Module loaded")

_SERVER_NAME = "primary"

_cached_tools: list = []
_tools_loaded_at: Optional[float] = None
_last_error: str = ""
_load_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    """Lazily create the lock inside a running event loop (avoids binding to
    the wrong loop if this module is imported before one exists)."""
    global _load_lock
    if _load_lock is None:
        _load_lock = asyncio.Lock()
    return _load_lock


def is_mcp_configured() -> bool:
    """True when MCP is enabled and a server URL has been supplied via .env."""
    return bool(settings.MCP_ENABLED and settings.MCP_SERVER_URL.strip())


def _build_client():
    """Build a MultiServerMCPClient pointed at the hosted MCP server.

    langchain-mcp-adapters>=0.1.0 uses MultiServerMCPClient purely as a
    connection-config holder — get_tools() opens a fresh session per call,
    so no `async with` context manager is needed (or supported).
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    connection: dict = {
        "transport": "streamable_http",
        "url": settings.MCP_SERVER_URL.strip(),
    }
    if settings.MCP_API_KEY.strip():
        connection["headers"] = {"Authorization": f"Bearer {settings.MCP_API_KEY.strip()}"}

    return MultiServerMCPClient({_SERVER_NAME: connection})


async def init_mcp_tools(timeout: float = 20.0) -> int:
    """Fetch and cache the MCP server's tool catalog. Call once at startup.

    Never raises — logs and leaves the cache empty on failure so an MCP outage
    can never block server startup or break the LangChain SQL agent fallback.
    """
    global _cached_tools, _tools_loaded_at, _last_error

    if not is_mcp_configured():
        print("[MCPManager] MCP disabled or MCP_SERVER_URL not set — skipping tool discovery")
        return 0

    t0 = time.time()
    try:
        client = _build_client()
        tools = await asyncio.wait_for(client.get_tools(), timeout=timeout)
        _cached_tools = tools
        _tools_loaded_at = time.time()
        _last_error = ""
        elapsed = _tools_loaded_at - t0
        tool_names = [getattr(t, "name", "?") for t in tools]
        print(f"[MCPManager] Cached {len(tools)} MCP tool(s) in {elapsed:.2f}s: {tool_names}")
        return len(tools)
    except Exception as e:
        _last_error = f"{type(e).__name__}: {e}"
        print(f"[MCPManager] Tool discovery FAILED (chat will use the LangChain SQL agent until this recovers): {_last_error}")
        _cached_tools = []
        _tools_loaded_at = None
        return 0


async def _maybe_refresh() -> None:
    """Best-effort background refresh when the cache is stale or was never loaded."""
    stale = (
        _tools_loaded_at is None
        or (time.time() - _tools_loaded_at) > settings.MCP_TOOLS_REFRESH_MINUTES * 60
    )
    if not stale:
        return
    lock = _get_lock()
    if lock.locked():
        return
    async with lock:
        stale_now = (
            _tools_loaded_at is None
            or (time.time() - _tools_loaded_at) > settings.MCP_TOOLS_REFRESH_MINUTES * 60
        )
        if stale_now:
            await init_mcp_tools()


async def get_cached_mcp_tools() -> list:
    """Return cached MCP tool objects, refreshing in the background first if stale/empty."""
    if not is_mcp_configured():
        return []
    await _maybe_refresh()
    return _cached_tools


def get_mcp_tool_catalog_text() -> str:
    """Human-readable tool catalog (name + description + args) for prompts.

    Built dynamically from the cache on every call so the router/orchestrator
    prompts never go stale relative to the hosted server's actual tool list.
    """
    if not _cached_tools:
        return "(no MCP tools available)"
    lines = []
    for t in _cached_tools:
        name = getattr(t, "name", "unknown_tool")
        description = (getattr(t, "description", "") or "").strip()
        try:
            args = t.args or {}
        except Exception:
            args = {}
        args_text = f" | args: {args}" if args else ""
        lines.append(f"- {name}: {description}{args_text}")
    return "\n".join(lines)


def get_mcp_status() -> dict:
    """Diagnostic snapshot — useful for logging / a future health endpoint."""
    return {
        "configured": is_mcp_configured(),
        "tool_count": len(_cached_tools),
        "tool_names": [getattr(t, "name", "?") for t in _cached_tools],
        "loaded_at": _tools_loaded_at,
        "last_error": _last_error,
    }
