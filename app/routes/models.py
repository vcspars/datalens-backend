"""Model catalog route — lets the frontend know whether OpenRouter model
selection is enabled, and if so, which free + tool-capable models to offer."""
from fastapi import APIRouter, Depends

from app.config import settings
from app.routes.auth import get_current_user
from app.models.user import User
from app.services.openrouter_manager import get_cached_openrouter_models

router = APIRouter(prefix="/models", tags=["models"])

print("[ModelsRoute] Router initialized")


def _provider_label(model_id: str) -> str:
    """Derive a human-readable provider label from an OpenRouter model id
    prefix, e.g. 'openai/gpt-4o-mini' -> 'OpenAI'."""
    prefix = (model_id.split("/", 1)[0] if "/" in model_id else "").lower()
    labels = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "meta-llama": "Meta",
        "mistralai": "Mistral",
        "deepseek": "DeepSeek",
        "qwen": "Qwen",
        "microsoft": "Microsoft",
        "x-ai": "xAI",
        "nvidia": "NVIDIA",
        "cohere": "Cohere",
    }
    return labels.get(prefix, prefix.replace("-", " ").title() if prefix else "Other")


@router.get("/catalog")
async def get_model_catalog(current_user: User = Depends(get_current_user)):
    """Return {"openrouter_enabled": bool, "models": [...]}.

    The frontend uses `openrouter_enabled` to decide whether to render the
    model picker at all (hidden entirely when false, so the header/UI stays
    pixel-identical to today for any deployment that hasn't turned this on).
    """
    if not settings.OPENROUTER_ENABLED:
        return {"openrouter_enabled": False, "models": []}

    catalog = await get_cached_openrouter_models()
    models = [
        {
            "id": m.get("id"),
            "name": m.get("name") or m.get("id"),
            "provider": _provider_label(m.get("id") or ""),
            "context_length": m.get("context_length"),
            "free": True,
        }
        for m in catalog
        if m.get("id")
    ]
    models.sort(key=lambda m: (m["provider"], m["name"]))
    return {"openrouter_enabled": True, "models": models}
