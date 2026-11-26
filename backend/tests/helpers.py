"""Synthetic-data builders and an in-memory writer shared by the tests."""
from __future__ import annotations

from datetime import datetime, timezone

from ingest.fetchers.base import Row

UTC = timezone.utc


def erddap_csv(header, units, rows):
    def f(v):
        return "NaN" if v is None else repr(v) if isinstance(v, float) else str(v)
    return ("\n".join([",".join(header), ",".join(units)] + [",".join(f(v) for v in r) for r in rows]) + "\n").encode()


class FakeWriter:
    """In-memory stand-in for ingest.db.Writer (same method names). `store` holds earlier grid values for carry-forward."""
    def __init__(self, earlier=None):
        self.runs, self.written, self.earlier = [], {}, earlier or {}
        self.locked = True

    def try_lock(self, area_id, run_date): return self.locked
    def ensure_region(self, area): self.region = area.area_id

    def start_run(self, area_id, run_date, variable, source_id, role):
        n = 1 + sum(1 for r in self.runs if (r["variable"], r["source_id"]) == (variable, source_id))
        run = dict(run_id=len(self.runs) + 1, variable=variable, source_id=source_id, role=role, attempt=n,
                   status="running", error_code=None, detail={}, rows_written=None, data_date=None)
        self.runs.append(run)
        return run["run_id"], n

    def finish_run(self, run_id, status, rows_written, data_date, error_code, detail):
        r = self.runs[run_id - 1]
        r.update(status=status, rows_written=rows_written, data_date=data_date, error_code=error_code, detail=detail)

    def write_rows(self, area_id, run_date, variable, rows, run_id):
        self.written[variable] = list(rows)
        return len(rows)

    def latest_before(self, area_id, run_date, variable):
        return list(self.earlier.get(variable, []))


def ok_rows(area, variable, value=1.0, t=datetime(2026, 11, 25, 9, 0, tzinfo=UTC), source="fake_src", extra=None):
    return [Row(c, value, t, source, "daily" if variable == "chl" else None, extra or {}) for c in area.cell_ids()]
