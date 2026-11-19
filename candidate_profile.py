"""Завантаження профілю кандидата з profile.json."""

import json
from pathlib import Path

DEFAULT_PROFILE_PATH = Path(__file__).parent / "profile.json"


def load_profile(path: Path | str = DEFAULT_PROFILE_PATH) -> dict:
    """Читає профіль кандидата з JSON-файлу. Онови profile.json, коли зʼявляться нові навички."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
