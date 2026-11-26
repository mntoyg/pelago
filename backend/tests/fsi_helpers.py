"""Builders for FSI tests: the real Chonburi parameters, UTC timestamps, one cell with every input present."""
from datetime import date, datetime, timedelta, timezone

from fsi.config import FsiParams
from fsi.model import CellInputs
from ingest.config import load_area

UTC = timezone.utc
RUN = date(2026, 11, 26)               # area-local date (Asia/Bangkok)
NOON_UTC = datetime(2026, 11, 26, 5, 0, tzinfo=UTC)     # 12:00 local on RUN


def params(**over) -> FsiParams:
    p = FsiParams.from_area(load_area("th-chonburi-coast"))
    if not over:
        return p
    from dataclasses import replace
    return replace(p, **over)


def obs_days_ago(n: int) -> datetime:
    """12:00 local (05:00 UTC) n local days before RUN, so the local date is exactly RUN - n."""
    return NOON_UTC - timedelta(days=n)


def full_cell(cid=1, sst_age=0, chl_age=0, **over) -> CellInputs:
    d = dict(cell_id=cid, sst_c=29.0, sst_observed_at=obs_days_ago(sst_age), sst_grad_c_per_km=0.02,
             chl_mg_m3=1.0, chl_observed_at=obs_days_ago(chl_age), chl_product="daily", depth_m=30.0)
    d.update(over)
    return CellInputs(**d)
