import json
import os
from pathlib import Path

from backend.models import ProviderSettings

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"


def load_settings() -> ProviderSettings:
    base = ProviderSettings()
    if SETTINGS_PATH.exists():
        try:
            base = ProviderSettings(**json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass

    # Environment variables override file-based settings (useful for server deployments)
    overrides: dict = {}
    if os.getenv("OPENAI_API_KEY"):
        overrides["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("CLAUDE_API_KEY"):
        overrides["claude_api_key"] = os.getenv("CLAUDE_API_KEY")
    if os.getenv("OLLAMA_BASE_URL"):
        overrides["ollama_base_url"] = os.getenv("OLLAMA_BASE_URL")
    if os.getenv("AI_PROVIDER"):
        overrides["provider"] = os.getenv("AI_PROVIDER")

    return base.model_copy(update=overrides) if overrides else base


def save_settings(settings: ProviderSettings) -> None:
    SETTINGS_PATH.write_text(
        settings.model_dump_json(indent=2), encoding="utf-8"
    )
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass  # Non-fatal on Windows or read-only filesystems
