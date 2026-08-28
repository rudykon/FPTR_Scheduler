"""Load the canonical FPTR visual palette for publication figures."""

from __future__ import annotations

import json
from pathlib import Path


PALETTE_PATH = Path(__file__).resolve().parents[1] / "config/visual_palette.json"


def load_palette() -> dict[str, str]:
    payload = json.loads(PALETTE_PATH.read_text(encoding="utf-8"))
    if payload.pop("schema-version", None) != 1:
        raise ValueError("visual palette must use schema-version 1")
    return payload


PALETTE = load_palette()
