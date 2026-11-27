"""Load and validate an area config file (backend/config/areas/<area_id>.json).

Unknown keys are rejected so a typo cannot silently change behaviour. The SHA-256 of the file bytes is the
`config_sha256` stored with every result. No secret may live in a config file: a value that looks like a URL
with credentials, a token or a key is refused.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .grid import CoordinateError, cells_in_bbox

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config" / "areas"
_TOP = {"area_id", "name", "names", "country_code", "timezone", "bbox", "licence_route", "sea_window_local",
        "boat_classes", "fsi", "max_age_days", "legal", "sources", "ingest", "schedule", "notices"}
_VARS = ("sst", "chl", "depth", "wave_wind")
_AREA_ID = re.compile(r"[a-z]{2}(-[a-z0-9]+)+")
_HOST = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
_SECRET = re.compile(r"(api[_-]?key|token|secret|passw|://[^/\s]*:[^@/\s]*@|bearer\s)", re.I)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    role: str  # 'primary' | 'fallback'


@dataclass(frozen=True)
class AreaConfig:
    raw: dict[str, Any]
    sha256: str

    @property
    def area_id(self) -> str: return self.raw["area_id"]
    @property
    def timezone(self) -> str: return self.raw["timezone"]
    @property
    def bbox(self) -> tuple[float, float, float, float]: return tuple(self.raw["bbox"])  # lon0, lat0, lon1, lat1
    @property
    def country_code(self) -> str: return self.raw["country_code"]
    @property
    def licence_route(self) -> str: return self.raw["licence_route"]
    @property
    def sea_window(self) -> tuple[str, str]: return tuple(self.raw["sea_window_local"])
    @property
    def ingest(self) -> dict[str, Any]: return self.raw["ingest"]
    @property
    def retries(self) -> int: return self.raw["schedule"]["retries"]
    @property
    def max_age_days(self) -> dict[str, Any]: return self.raw["max_age_days"]

    def chain(self, variable: str) -> list[SourceRef]:
        return [SourceRef(s["source_id"], s["role"]) for s in self.raw["sources"][variable]]

    def allowed_hosts(self, source_id: str) -> tuple[str, ...]:
        for chain in self.raw["sources"].values():
            for source in chain:
                if source["source_id"] == source_id:
                    return tuple(source["hosts"])
        return ()

    @property
    def all_allowed_hosts(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(host for chain in self.raw["sources"].values()
                                   for source in chain for host in source["hosts"]))

    def cell_ids(self) -> list[int]:
        lon0, lat0, lon1, lat1 = self.bbox
        return cells_in_bbox(lon0, lat0, lon1, lat1)


def _walk_strings(node: Any, path: str = ""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(str(k), path + "/" + str(k))
            yield from _walk_strings(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


_FSI_KEYS = {"model_version", "weights", "targets", "depth", "front", "moon", "season", "freshness", "min_spacing_km"}
FSI_WEIGHT_KEYS = ("sst", "front", "chl", "depth", "moon", "season")
_FSI_TARGET_KEYS = {"sst_c", "sst_sigma_c", "log10_chl", "log10_chl_sigma", "bloom_mg_m3"}
_MODEL_VERSION = re.compile(r"fsi-v[0-9]+\.[0-9]+\.[0-9]+")


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _block(fsi: dict, key: str, keys: set[str]) -> dict:
    b = fsi.get(key)
    if not isinstance(b, dict) or set(b) != keys:
        raise ConfigError(f"fsi.{key} must have exactly the keys {sorted(keys)}")
    for k, v in b.items():
        if not _is_num(v):
            raise ConfigError(f"fsi.{key}.{k} must be a finite number")
    return b


def validate_fsi(fsi: Any) -> None:
    """Strict check of the whole fsi block: unknown or missing keys, bool / NaN / Infinity / negative values, a weight
    sum of 0 and inconsistent ranges are refused, so a typo cannot silently change a score."""
    if not isinstance(fsi, dict) or set(fsi) != _FSI_KEYS:
        raise ConfigError(f"fsi must have exactly the keys {sorted(_FSI_KEYS)}")
    if not isinstance(fsi["model_version"], str) or not _MODEL_VERSION.fullmatch(fsi["model_version"]):
        raise ConfigError("fsi.model_version must look like fsi-v1.0.0")
    w = fsi["weights"]
    if not isinstance(w, dict) or set(w) != set(FSI_WEIGHT_KEYS):
        raise ConfigError(f"fsi.weights must have exactly the keys {list(FSI_WEIGHT_KEYS)}")
    for k, v in w.items():
        if not _is_num(v) or v < 0 or v > 1000:
            raise ConfigError(f"fsi.weights.{k} must be a finite number in 0..1000")
    if not sum(w.values()) > 0:
        raise ConfigError("fsi.weights must not sum to 0")
    t = _block(fsi, "targets", _FSI_TARGET_KEYS)
    if t["sst_sigma_c"] <= 0 or t["log10_chl_sigma"] <= 0 or t["bloom_mg_m3"] <= 0:
        raise ConfigError("fsi.targets: sigmas and the bloom threshold must be greater than 0")
    d = _block(fsi, "depth", {"ramp_up_m", "full_to_m", "zero_at_m"})
    if not 0 < d["ramp_up_m"] <= d["full_to_m"] < d["zero_at_m"]:
        raise ConfigError("fsi.depth needs 0 < ramp_up_m <= full_to_m < zero_at_m")
    f = _block(fsi, "front", {"min_cells"})
    if f["min_cells"] < 1 or f["min_cells"] != int(f["min_cells"]):
        raise ConfigError("fsi.front.min_cells must be an integer >= 1")
    if not 0 <= _block(fsi, "moon", {"illum_penalty"})["illum_penalty"] <= 1:
        raise ConfigError("fsi.moon.illum_penalty must be in 0..1")
    if not 0 <= _block(fsi, "season", {"flat"})["flat"] <= 1:
        raise ConfigError("fsi.season.flat must be in 0..1")
    fr = _block(fsi, "freshness", {"grace_days", "decay_days"})
    if fr["grace_days"] < 0 or fr["decay_days"] <= 0:
        raise ConfigError("fsi.freshness needs grace_days >= 0 and decay_days > 0")
    if not _is_num(fsi["min_spacing_km"]) or fsi["min_spacing_km"] <= 0:
        raise ConfigError("fsi.min_spacing_km must be a number greater than 0")


def validate(raw: dict[str, Any]) -> None:
    if not isinstance(raw, dict):
        raise ConfigError("config must be a JSON object")
    extra = set(raw) - _TOP
    if extra:
        raise ConfigError(f"unknown config keys: {sorted(extra)}")
    if not _AREA_ID.fullmatch(str(raw.get("area_id", ""))):
        raise ConfigError("bad area_id")
    if raw.get("licence_route") not in ("A", "B"):
        raise ConfigError("licence_route must be A or B")
    try:
        ZoneInfo(raw["timezone"])
    except (KeyError, ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError("unknown IANA time zone") from exc
    bbox = raw.get("bbox")
    if (not isinstance(bbox, list) or len(bbox) != 4
            or not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in bbox)):
        raise ConfigError("bbox must be [min_lon, min_lat, max_lon, max_lat]")
    sw = raw.get("sea_window_local")
    if not (isinstance(sw, list) and len(sw) == 2 and all(re.fullmatch(r"\d\d:\d\d", str(x)) for x in sw)):
        raise ConfigError("sea_window_local must be two HH:MM strings")
    src = raw.get("sources", {})
    if set(src) != set(_VARS):
        raise ConfigError(f"sources must list exactly {_VARS}")
    for var, chain in src.items():
        if not chain or chain[0].get("role") != "primary":
            raise ConfigError(f"{var}: the first source must be the primary")
        for s in chain:
            if set(s) != {"source_id", "role", "hosts"} or s["role"] not in ("primary", "fallback") \
                    or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", str(s["source_id"])):
                raise ConfigError(f"{var}: bad source entry")
            hosts = s["hosts"]
            if (not isinstance(hosts, list) or not hosts
                    or any(not isinstance(host, str) or not _HOST.fullmatch(host) for host in hosts)
                    or len(set(hosts)) != len(hosts)):
                raise ConfigError(f"{var}: source hosts must be unique lowercase DNS hostnames")
    ing = raw.get("ingest", {})
    need = {"min_valid_fraction", "margin_pixels", "open_meteo", "request_pause_s", "http_timeout_s"}
    if set(ing) != need:
        raise ConfigError("ingest block has missing or unknown keys")
    mvf = ing["min_valid_fraction"]["sst"]
    if isinstance(mvf, bool) or not (isinstance(mvf, (int, float)) and 0 < mvf <= 1):
        raise ConfigError("min_valid_fraction.sst must be in (0, 1]")
    validate_fsi(raw.get("fsi"))
    retries = raw.get("schedule", {}).get("retries")
    if isinstance(retries, bool) or not isinstance(retries, int) or not 1 <= retries <= 5:
        raise ConfigError("schedule.retries must be 1..5")
    for path, text in _walk_strings(raw):
        if _SECRET.search(text):
            raise ConfigError(f"config value at {path} looks like a secret or a credentialed URL")
    try:   # the bbox must sit on the 0.05 degree grid
        cells_in_bbox(*bbox)
    except CoordinateError as exc:
        raise ConfigError(str(exc)) from exc


def load_area(area_id: str, directory: Path | None = None) -> AreaConfig:
    if not _AREA_ID.fullmatch(area_id):   # also blocks path traversal through the file name
        raise ConfigError("bad area_id")
    path = (directory or CONFIG_DIR) / f"{area_id}.json"
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConfigError("area config not found") from exc
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError("area config is not valid JSON") from exc
    validate(raw)
    if raw["area_id"] != area_id:
        raise ConfigError("area_id does not match the file name")
    return AreaConfig(raw=raw, sha256=hashlib.sha256(data).hexdigest())
