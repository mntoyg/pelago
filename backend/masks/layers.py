"""Read the polygon layers of one area from backend/config/layers/<area_id>/ (untrusted files, validated before use).

A layer is either usable or absent. Anything wrong with a file (missing, symlink, too big, not JSON, not polygons, NaN,
out-of-range coordinate, unclosed ring, no overlap with the area) makes the layer ABSENT with a short reason code, and an
absent layer means "unknown" in the mask, which is never recommended. The reason is a code, not the file's text.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from ingest.config import _AREA_ID
from .fetch_eez import check_collection

LAYERS_DIR = Path(__file__).resolve().parent.parent / "config" / "layers"
MAX_FILE_BYTES = 40 * 1024 * 1024
FILES = {"land": "land.geojson", "eez": "eez.geojson", "internal_waters": "internal_waters.geojson"}


class LayerError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class LoadedLayers:
    geoms: dict[str, list[str]] = field(default_factory=dict)       # layer -> GeoJSON geometry strings
    sha256: dict[str, str] = field(default_factory=dict)            # layer -> hash of the file bytes
    problems: dict[str, str] = field(default_factory=dict)          # layer -> reason code (absent layers only)

    @property
    def land(self) -> list[str] | None:
        return self.geoms.get("land")

    @property
    def eez(self) -> list[str] | None:
        """EEZ and internal waters together: the national waters. Needs both files (and see geo.py: also the land)."""
        if "eez" in self.geoms and "internal_waters" in self.geoms:
            return self.geoms["eez"] + self.geoms["internal_waters"]
        return None


def _bbox_of(doc) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for f in doc["features"]:
        g = f["geometry"]
        for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
            for ring in poly:
                xs += [p[0] for p in ring]
                ys += [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def read_layer_file(path: Path, area_bbox) -> tuple[list[str], str]:
    """(GeoJSON geometry strings, sha256 of the bytes). Raises LayerError(code)."""
    try:
        if path.is_symlink() or not path.is_file():
            raise LayerError("missing")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise LayerError("too_large")
        data = path.read_bytes()
    except OSError:
        raise LayerError("unreadable") from None
    try:
        doc = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError):
        raise LayerError("not_json") from None
    try:
        check_collection(doc)
    except (ValueError, TypeError, KeyError, IndexError):
        raise LayerError("bad_geometry") from None
    x0, y0, x1, y1 = _bbox_of(doc)
    a0, b0, a1, b1 = area_bbox
    if x1 < a0 or x0 > a1 or y1 < b0 or y0 > b1:
        raise LayerError("no_overlap")
    return [json.dumps(f["geometry"], separators=(",", ":")) for f in doc["features"]], hashlib.sha256(data).hexdigest()


def _reject_constant(name):         # json accepts NaN / Infinity by default; refuse them
    raise ValueError("non-finite number")


def load_layers(area_id: str, area_bbox, directory: Path | None = None) -> LoadedLayers:
    if not _AREA_ID.fullmatch(area_id):          # also blocks path traversal through the folder name
        raise LayerError("bad_area_id")
    base = (directory or LAYERS_DIR) / area_id
    out = LoadedLayers()
    for name, fname in FILES.items():
        try:
            out.geoms[name], out.sha256[name] = read_layer_file(base / fname, area_bbox)
        except LayerError as exc:
            out.problems[name] = exc.code
    return out
