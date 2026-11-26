"""Shared test helpers: a small area on a real-looking config, synthetic data builders, an in-memory writer."""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingest.config import CONFIG_DIR, load_area

UTC = timezone.utc


@pytest.fixture
def make_area(tmp_path):
    """make_area(bbox=[...], **overrides) -> AreaConfig built from the real Chonburi config with changes applied."""
    def _make(bbox=None, mutate=None):
        raw = json.loads((CONFIG_DIR / "th-chonburi-coast.json").read_text(encoding="utf-8"))
        if bbox:
            raw["bbox"] = bbox
        if mutate:
            mutate(raw)
        d = tmp_path / "areas"
        d.mkdir(exist_ok=True)
        (d / "th-chonburi-coast.json").write_text(json.dumps(raw), encoding="utf-8")
        return load_area("th-chonburi-coast", d)
    return _make


@pytest.fixture
def small_area(make_area):
    """2 x 2 cells: lon 100.7..100.8, lat 12.2..12.3 (cell centres 12.225/12.275 x 100.725/100.775)."""
    return make_area([100.7, 12.2, 100.8, 12.3])
