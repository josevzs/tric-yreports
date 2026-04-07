from fastapi import APIRouter

from backend.models import ProviderSettings
from backend.config import load_settings, save_settings

router = APIRouter()


@router.get("/settings", response_model=ProviderSettings)
async def get_settings():
    settings = load_settings()
    # Mask API keys in response (show only if set, not the actual value)
    masked = settings.model_copy()
    if masked.claude_api_key:
        masked.claude_api_key = "***set***"
    if masked.openai_api_key:
        masked.openai_api_key = "***set***"
    return masked


@router.post("/settings")
async def update_settings(body: ProviderSettings):
    current = load_settings()
    # Don't overwrite real keys if placeholder is sent
    if body.claude_api_key == "***set***":
        body.claude_api_key = current.claude_api_key
    if body.openai_api_key == "***set***":
        body.openai_api_key = current.openai_api_key
    save_settings(body)
    return {"saved": True}
