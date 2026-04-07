import json
from pathlib import Path

from backend.models import ProviderSettings

SETTINGS_PATH = Path(__file__).parent.parent / "settings.json"


def load_settings() -> ProviderSettings:
    if SETTINGS_PATH.exists():
        try:
            return ProviderSettings(**json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return ProviderSettings()


def save_settings(settings: ProviderSettings) -> None:
    SETTINGS_PATH.write_text(
        settings.model_dump_json(indent=2), encoding="utf-8"
    )
