"""FSI parameters taken from the area config. Nothing numeric is hard-coded in the model; the file is validated by
ingest.config.validate_fsi (strict) and the age limits are checked here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingest.config import AreaConfig, ConfigError, FSI_WEIGHT_KEYS, validate_fsi

# API_CONTRACT.md 4.6: a chlorophyll 8-day composite counts as fresh up to 8 days. The ingest only produces 'daily'
# today, so this is a code constant (PM decision C) and not a config key.
CHL_8DAY_FRESH_DAYS = 8
SUBSCORES = FSI_WEIGHT_KEYS     # ("sst", "front", "chl", "depth", "moon", "season")


@dataclass(frozen=True)
class FsiParams:
    model_version: str
    weights: dict[str, float]
    sst_c: float
    sst_sigma_c: float
    log10_chl: float
    log10_chl_sigma: float
    bloom_mg_m3: float
    depth_ramp_up_m: float
    depth_full_to_m: float
    depth_zero_at_m: float
    front_min_cells: int
    moon_illum_penalty: float
    season_flat: float
    grace_days: float
    decay_days: float
    sst_fresh_days: int
    sst_max_days: int
    chl_fresh_days: int
    chl_max_days: int
    timezone: str
    config_sha256: str

    @classmethod
    def from_area(cls, area: AreaConfig) -> "FsiParams":
        return cls.from_raw(area.raw, area.sha256)

    @classmethod
    def from_raw(cls, raw: dict[str, Any], sha256: str) -> "FsiParams":
        validate_fsi(raw.get("fsi"))
        f = raw["fsi"]
        if f["weights"]["sst"] <= 0:
            raise ConfigError("fsi.weights.sst must be greater than 0 (SST is what makes a cell scoreable)")
        ages = {}
        for var in ("sst", "chl"):
            a = raw.get("max_age_days", {}).get(var)
            ok = (isinstance(a, dict) and set(a) == {"fresh", "max"}
                  and all(isinstance(a[k], int) and not isinstance(a[k], bool) and a[k] >= 0 for k in a)
                  and a["fresh"] <= a["max"])
            if not ok:
                raise ConfigError(f"max_age_days.{var} needs integer fresh <= max, both >= 0")
            ages[var] = a
        t, d = f["targets"], f["depth"]
        return cls(
            model_version=f["model_version"], weights={k: float(f["weights"][k]) for k in SUBSCORES},
            sst_c=t["sst_c"], sst_sigma_c=t["sst_sigma_c"], log10_chl=t["log10_chl"],
            log10_chl_sigma=t["log10_chl_sigma"], bloom_mg_m3=t["bloom_mg_m3"],
            depth_ramp_up_m=d["ramp_up_m"], depth_full_to_m=d["full_to_m"], depth_zero_at_m=d["zero_at_m"],
            front_min_cells=int(f["front"]["min_cells"]), moon_illum_penalty=f["moon"]["illum_penalty"],
            season_flat=f["season"]["flat"], grace_days=f["freshness"]["grace_days"],
            decay_days=f["freshness"]["decay_days"], sst_fresh_days=ages["sst"]["fresh"],
            sst_max_days=ages["sst"]["max"], chl_fresh_days=ages["chl"]["fresh"], chl_max_days=ages["chl"]["max"],
            timezone=raw["timezone"], config_sha256=sha256)
