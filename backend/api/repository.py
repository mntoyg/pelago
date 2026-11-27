"""PostgreSQL read adapter. All SQL is parameterised and every connection is read-only."""
from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.rows import dict_row


class DatabaseUnavailable(RuntimeError):
    pass


class PostgresRepository:
    def __init__(self, database_url: str | None = None):
        self._database_url = database_url if database_url is not None else os.environ.get("DATABASE_URL")

    def _query(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self._database_url:
            raise DatabaseUnavailable("database unavailable")
        try:
            with psycopg.connect(
                self._database_url,
                connect_timeout=3,
                options="-c default_transaction_read_only=on",
                row_factory=dict_row,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return list(cur.fetchall()) if cur.description else []
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            raise DatabaseUnavailable("database unavailable") from exc

    def health(self) -> bool:
        rows = self._query("SELECT 1 AS ok")
        return bool(rows and rows[0]["ok"] == 1)

    def region_verification(self, area_id: str) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT verification_level, verified_trips FROM pelago.regions WHERE region_id = %s",
            (area_id,),
        )
        return rows[0] if rows else None

    def list_regions_verification(self) -> dict[str, dict[str, Any]]:
        return {
            row["region_id"]: row
            for row in self._query("SELECT region_id, verification_level, verified_trips FROM pelago.regions")
        }

    def freshness_rows(self, area_id: str) -> dict[str, list[dict[str, Any]]]:
        success = self._query(
            """SELECT variable, source_id, fetcher_role, data_date, started_at, finished_at, attempt
               FROM pelago.v_ingest_last_success WHERE region_id = %s ORDER BY variable""",
            (area_id,),
        )
        attempts = self._query(
            """SELECT variable, source_id, fetcher_role, status, attempt, started_at, finished_at, error_code
               FROM pelago.v_ingest_last_attempt WHERE region_id = %s ORDER BY variable""",
            (area_id,),
        )
        compute = self._query(
            """SELECT DISTINCT ON (job_kind) job_kind, status, run_date, started_at, finished_at,
                      detail->>'model_version' AS model_version
               FROM pelago.job_runs
               WHERE region_id = %s AND job_kind IN ('mask', 'fsi', 'pick') AND status IN ('success', 'partial')
               ORDER BY job_kind, started_at DESC""",
            (area_id,),
        )
        return {"success": success, "attempts": attempts, "compute": compute}

    def spots_bundle(self, area_id: str, run_date, boat_class: str, model_version: str,
                     verification_level: str, licence_route: str, limit: int) -> dict[str, Any]:
        jobs = self._query(
            """SELECT run_id, status, finished_at, detail
               FROM pelago.job_runs
               WHERE region_id = %s AND run_date = %s AND job_kind = 'pick' AND status IN ('success', 'partial')
               ORDER BY started_at DESC LIMIT 1""",
            (area_id, run_date),
        )
        if not jobs:
            return {"status": "no_run", "job": None, "scored": 0, "eligible": 0, "water": 0, "red": 0,
                    "yellow": 0, "no_forecast": 0, "max_wave_m": None, "max_wind_kmh": None,
                    "config_sha256": None, "sources": [], "spots": []}
        job = jobs[0]
        stats = self._query(
            """SELECT count(*) FILTER (WHERE f.fsi IS NOT NULL) AS scored,
                      count(*) FILTER (WHERE m.eligible IS TRUE) AS eligible,
                      count(*) FILTER (WHERE m.is_water IS TRUE) AS water,
                      count(*) FILTER (WHERE m.is_water AND m.sea_state_level = 'red') AS red,
                      count(*) FILTER (WHERE m.is_water AND m.sea_state_level = 'yellow') AS yellow,
                      count(*) FILTER (WHERE m.is_water AND m.forecast_ok IS FALSE) AS no_forecast,
                      max(g.wave_window_max_m) AS max_wave_m, max(g.wind_window_max_kmh) AS max_wind_kmh,
                      max(f.config_sha256) AS config_sha256
               FROM pelago.grid_daily g
               LEFT JOIN pelago.fsi_daily f ON f.region_id = g.region_id AND f.run_date = g.run_date
                    AND f.cell_id = g.cell_id AND f.model_version = %s
               LEFT JOIN pelago.cell_mask_daily m ON m.region_id = g.region_id AND m.run_date = g.run_date
                    AND m.cell_id = g.cell_id AND m.boat_class = %s
               WHERE g.region_id = %s AND g.run_date = %s""",
            (model_version, boat_class, area_id, run_date),
        )[0]
        source_rows = self._query(
            """SELECT 'sst' AS variable, (array_agg(sst_source ORDER BY sst_observed_at DESC)
                         FILTER (WHERE sst_source IS NOT NULL))[1] AS source_id,
                      max(sst_observed_at) AS observed_at
               FROM pelago.grid_daily WHERE region_id = %s AND run_date = %s
               UNION ALL
               SELECT 'chl', (array_agg(chl_source ORDER BY chl_observed_at DESC)
                         FILTER (WHERE chl_source IS NOT NULL))[1], max(chl_observed_at)
               FROM pelago.grid_daily WHERE region_id = %s AND run_date = %s
               UNION ALL
               SELECT 'depth', (array_agg(depth_source ORDER BY depth_source)
                         FILTER (WHERE depth_source IS NOT NULL))[1], NULL::timestamptz
               FROM pelago.grid_daily WHERE region_id = %s AND run_date = %s
               UNION ALL
               SELECT 'wave_wind', (array_agg(wx_source ORDER BY wx_issued_at DESC)
                         FILTER (WHERE wx_source IS NOT NULL))[1], max(wx_issued_at)
               FROM pelago.grid_daily WHERE region_id = %s AND run_date = %s""",
            (area_id, run_date, area_id, run_date, area_id, run_date, area_id, run_date),
        )
        rows = self._query(
            """SELECT r.pick_rank, r.cell_id, r.fsi, f.confidence, r.legal_status,
                      f.confidence_cap, f.confidence_reasons, f.model_version, f.computed_at,
                      f.s_sst, f.s_front, f.s_chl, f.s_depth, f.s_moon, f.s_season,
                      f.a_sst, f.a_front, f.a_chl, f.a_depth, f.a_moon, f.a_season,
                      g.lat, g.lon, g.sst_c, g.sst_observed_at, g.sst_source, g.sst_grad_c_per_km,
                      g.chl_mg_m3, g.chl_observed_at, g.chl_source, g.chl_product,
                      g.depth_m, g.depth_source, g.wave_window_max_m, g.wind_window_max_kmh,
                      g.wx_issued_at, g.wx_source,
                      m.sea_state_level, m.sea_reason_code, m.legal_status AS mask_legal_status,
                      m.eligible, m.is_water, m.eez_ok, m.disputed_ok, m.protected_ok, m.closure_ok,
                      m.boat_zone_ok, m.forecast_ok, m.legal_unknown_allowed
               FROM pelago.recommendations r
               JOIN pelago.fsi_daily f ON f.region_id = r.region_id AND f.run_date = r.run_date
                    AND f.model_version = r.model_version AND f.cell_id = r.cell_id
               JOIN pelago.grid_daily g ON g.region_id = r.region_id AND g.run_date = r.run_date
                    AND g.cell_id = r.cell_id
               JOIN pelago.cell_mask_daily m ON m.region_id = r.region_id AND m.run_date = r.run_date
                    AND m.boat_class = r.boat_class AND m.cell_id = r.cell_id
               WHERE r.region_id = %s AND r.run_date = %s AND r.boat_class = %s
                 AND r.model_version = %s AND r.run_id = %s
                 AND r.eligible IS TRUE AND r.scored IS TRUE AND f.fsi IS NOT NULL AND f.s_sst IS NOT NULL
                 AND m.eligible IS TRUE AND m.is_water IS TRUE AND m.eez_ok IS TRUE
                 AND m.disputed_ok IS NOT FALSE AND m.protected_ok IS NOT FALSE
                 AND m.closure_ok IS NOT FALSE AND m.boat_zone_ok IS NOT FALSE
                 AND m.forecast_ok IS TRUE AND m.sea_state_level <> 'red'
                 AND (m.legal_status = 'complete' OR m.legal_unknown_allowed IS TRUE)
                 AND (%s <> 'trial' OR f.confidence <> 'high')
                 AND (%s <> 'B' OR g.wx_source IS DISTINCT FROM 'open_meteo_marine')
               ORDER BY r.pick_rank LIMIT %s""",
            (area_id, run_date, boat_class, model_version, job["run_id"], verification_level, licence_route, limit),
        )
        return {"status": "ok", "job": job, **stats, "sources": source_rows, "spots": rows}
