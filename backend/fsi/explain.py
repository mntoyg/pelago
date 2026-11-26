"""Per-cell explanation in the shape of API_CONTRACT.md 4.5 (subscores, observations, confidence), plus what the contract
leaves to the server: each input's share of the score, and which inputs are placeholders."""
from __future__ import annotations

from datetime import date

from .config import SUBSCORES, FsiParams
from .model import PLACEHOLDERS, CellInputs, CellScore
from .moon import moon_for_local_date

DATA_INPUTS = ("sst", "front", "chl", "depth")


def _r(x, n=3):
    return None if x is None else round(float(x), n)


def explain_cell(c: CellInputs, s: CellScore, run_date: date, p: FsiParams) -> dict:
    den = sum(p.weights[k] * s.fresh[k] for k in SUBSCORES if s.scores[k] is not None and s.fresh[k])
    sub = {}
    for k in SUBSCORES:
        sc, a = s.scores[k], s.fresh[k]
        used = sc is not None and bool(a)
        sub[k] = {
            "score": _r(sc), "weight": p.weights[k], "freshness": _r(a),
            "contribution_points": _r(100 * p.weights[k] * a * sc / den, 2) if used and s.fsi is not None else None,
            "placeholder": k in PLACEHOLDERS,
            "status": s.states[k].status if k in s.states else "ok" if k in PLACEHOLDERS else "missing",
        }
    data_w = sum(p.weights[k] for k in DATA_INPUTS)
    data_used = sum(p.weights[k] * s.fresh[k] for k in DATA_INPUTS if s.scores[k] is not None and s.fresh[k])
    obs = {
        "sst": {"value": _r(c.sst_c), "observed_at": c.sst_observed_at, "age_days": s.states["sst"].age_days},
        "front": {"value": _r(c.sst_grad_c_per_km, 4), "observed_at": c.sst_observed_at,
                  "age_days": s.states["front"].age_days},
        "chl": {"value": _r(c.chl_mg_m3, 4), "observed_at": c.chl_observed_at, "age_days": s.states["chl"].age_days,
                "product": c.chl_product},
        "depth": {"value": _r(c.depth_m, 1), "observed_at": None, "age_days": None},
        "moon": moon_for_local_date(run_date, p.timezone),
    }
    notes = ["demo_weights_untuned"] + (["no_verified_catch_logs"] if s.confidence_cap else [])
    if s.front_note:
        notes.append(s.front_note)
    if s.states.get("front") and s.states["front"].used:
        notes.append("front_percentile_over_depth_not_null_cells")   # ETOPO water proxy until the land mask exists
    return {
        "model_version": p.model_version, "fsi": s.fsi, "subscores": sub, "observations": obs,
        "confidence": s.confidence, "confidence_cap": s.confidence_cap,
        "confidence_reasons": list(s.confidence_reasons),
        "data_weight_share": _r(data_used / data_w, 3) if s.fsi is not None else None,
        "notes": notes,
    }
