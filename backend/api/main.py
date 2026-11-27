"""FastAPI application factory and HTTP safety policies."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import uuid
from datetime import UTC, date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from ingest.config import CONFIG_DIR, AreaConfig, ConfigError, load_area
from ingest.timeutil import local_date_of, local_today
from fsi.moon import moon_for_local_date

from .repository import DatabaseUnavailable, PostgresRepository
from .validation import ValidationProblem, validate_area_id, validate_spots_query

API_VERSION = "1.0"
SERVICE_VERSION = "0.1.0"
AREA_ID_RE = re.compile(r"^[a-z]{2}(-[a-z0-9]+)+$")
DATASET_IDS = {
    "erddap_mur_sst": "jplMURSST41",
    "erddap_viirs_chl": "nesdisVHNchlaDaily",
    "erddap_viirs_n20_chl": "nesdisVHNnoaa20chlaDaily",
    "erddap_etopo_depth": "ETOPO_2022_v1_15s",
    "open_meteo_marine": "marine-api + forecast API",
}


class APIProblem(Exception):
    def __init__(self, status: int, code: str, title: str, detail: str = ""):
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail


class RateLimiter:
    """Small per-process fixed-window limiter; no caller address is logged or persisted."""

    def __init__(self, limit: int = 60, window_seconds: int = 60, max_keys: int = 10_000):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._buckets: dict[str, tuple[int, int]] = {}

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        window = int(current // self.window_seconds)
        bucket = self._buckets.get(key)
        if bucket is None and len(self._buckets) >= self.max_keys:
            self._buckets = {k: v for k, v in self._buckets.items() if v[1] == window}
            if len(self._buckets) >= self.max_keys:
                retry = max(1, int((window + 1) * self.window_seconds - current))
                return False, retry
        count, previous_window = bucket or (0, window)
        if previous_window != window:
            count = 0
        count += 1
        self._buckets[key] = (count, window)
        retry = max(1, int((window + 1) * self.window_seconds - current))
        return count <= self.limit, retry


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive timestamps are not valid API output")
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        raise TypeError("filesystem paths cannot appear in API output")
    raise TypeError(f"unsupported API value: {type(value).__name__}")


def _etag(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_value).encode("utf-8")
    return '"' + hashlib.sha256(payload).hexdigest() + '"'


def _response(request: Request, value: Any, cache_control: str, status_code: int = 200) -> Response:
    encoded = jsonable_encoder(value, custom_encoder={datetime: _json_value})
    validator = _etag(encoded)
    if request.headers.get("if-none-match"):
        candidates = [token.strip() for token in request.headers["if-none-match"].split(",")]
        if "*" in candidates or validator in candidates:
            return Response(status_code=304, headers={"ETag": validator, "Cache-Control": cache_control})
    response = JSONResponse(encoded, status_code=status_code)
    response.headers["ETag"] = validator
    response.headers["Cache-Control"] = cache_control
    return response


def _problem_body(request: Request, status: int, code: str, title: str, detail: str = "", errors=None):
    body = {
        "type": f"urn:pelago:problem:{code}",
        "title": title,
        "status": status,
        "code": code,
        "request_id": getattr(request.state, "request_id", ""),
    }
    if status == 422:
        body["errors"] = errors or []
        body["detail"] = "Request validation failed."
    elif status != 500 and detail:
        body["detail"] = detail[:160]
    return JSONResponse(body, status_code=status, media_type="application/problem+json", headers={"Cache-Control": "no-store"})


def _area_configs() -> dict[str, AreaConfig]:
    if not CONFIG_DIR.is_dir():
        raise RuntimeError("area configuration directory missing")
    configs = {}
    for path in sorted(CONFIG_DIR.glob("*.json")):
        if path.is_file() and AREA_ID_RE.fullmatch(path.stem):
            configs[path.stem] = load_area(path.stem)
    return configs


def _legal(area: AreaConfig) -> dict[str, Any]:
    cfg = area.raw["legal"]
    required = list(cfg["layers_required"])
    loaded = list(cfg["layers_loaded"])
    checked = [name for name in required if name in loaded]
    missing = [name for name in required if name not in loaded]
    return {
        "status": "incomplete" if missing else "complete",
        "layers_checked": checked,
        "layers_missing": missing,
        "incomplete_policy": cfg["incomplete_policy"],
    }


def _verification(area: AreaConfig, repository) -> dict[str, Any]:
    row = repository.region_verification(area.area_id)
    if row:
        return {"level": row["verification_level"], "verified_trips": row["verified_trips"]}
    # The demo configuration explicitly carries the trial-area notice; do not infer beta/confirmed.
    return {"level": "trial", "verified_trips": 0}


def _area_summary(area: AreaConfig, verification: dict[str, Any]) -> dict[str, Any]:
    return {
        "area_id": area.area_id,
        "name": area.raw["name"],
        "country_code": area.country_code,
        "bbox": [round(float(x), 4) for x in area.bbox],
        "timezone": area.timezone,
        "legal_status": _legal(area)["status"],
        "verification_level": verification["level"],
    }


def _area_body(area: AreaConfig, verification: dict[str, Any]) -> dict[str, Any]:
    fsi = area.raw["fsi"]
    from ingest.fetchers.registry import REGISTRY
    return {
        "api_version": API_VERSION,
        "area_id": area.area_id,
        "name": area.raw["name"],
        "names": area.raw["names"],
        "country_code": area.country_code,
        "timezone": area.timezone,
        "bbox": [round(float(x), 4) for x in area.bbox],
        "grid": {"scheme": "pelago-cell-v1", "cell_deg": 0.05},
        "sea_window_local": list(area.sea_window),
        "boat_classes": area.raw["boat_classes"],
        "fsi": {"model_version": fsi["model_version"], "weights": fsi["weights"], "weights_status": "untuned"},
        "verification": verification,
        "legal": {**_legal(area), "label": "trial: legal layers incomplete" if _legal(area)["status"] == "incomplete" else None},
        "licence_route": area.licence_route,
        "sources": [
            {"variable": variable, **source,
             "provider": "Open-Meteo" if source["source_id"] == "open_meteo_marine" else "NOAA CoastWatch ERDDAP",
             "dataset_id": getattr(REGISTRY[source["source_id"]], "dataset", DATASET_IDS[source["source_id"]]),
             "route_allowed": list(REGISTRY[source["source_id"]].routes)}
            for variable, sources in area.raw["sources"].items()
            for source in sources
            if area.licence_route in REGISTRY[source["source_id"]].routes
        ],
        "attributions": [],
        "notices": list(area.raw["notices"]),
        "config_hash": area.sha256[:12],
        "label": "trial: legal layers incomplete" if _legal(area)["status"] == "incomplete" else None,
    }


def _next_expected_run(area: AreaConfig, now: datetime) -> datetime | None:
    local_time = area.raw.get("schedule", {}).get("run_local_time")
    if not isinstance(local_time, str) or not re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", local_time):
        return None
    hours, minutes = (int(part) for part in local_time.split(":"))
    if hours > 23:
        return None
    zone = ZoneInfo(area.timezone)
    local_now = now.astimezone(zone)
    candidate = datetime.combine(local_now.date(), dt_time(hours, minutes), zone)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC).replace(microsecond=0)


def _freshness_payload(area: AreaConfig, records: dict[str, list[dict[str, Any]]], now: datetime) -> dict[str, Any]:
    local_date = local_today(area.timezone, now)
    success = {row["variable"]: row for row in records["success"]}
    attempts = {row["variable"]: row for row in records["attempts"]}
    sources = []
    usable = 0
    degraded = False
    for variable in ("sst", "chl", "depth", "wave_wind"):
        row = success.get(variable)
        attempt = attempts.get(variable)
        static = variable == "depth"
        if variable == "wave_wind" and area.licence_route == "B":
            row = None
            attempt = None
        if row is None or (row["data_date"] is None and not static):
            age = None
            status = "never"
            source_id = None
            role = None
            data_date = None
            ingest_at = None
        else:
            data_date = row["data_date"]
            age = max(0, (local_date - data_date).days) if data_date else None
            if static:
                status = "fresh"
                age = None
            else:
                limits = area.max_age_days["wave_wind_hours"] if variable == "wave_wind" else area.max_age_days[variable]
                fresh_days = 1 if variable == "wave_wind" else limits["fresh"]
                max_days = 2 if variable == "wave_wind" else limits["max"]
                status = "fresh" if age <= fresh_days else "stale" if age <= max_days else "expired"
            source_id = row["source_id"]
            role = row["fetcher_role"]
            ingest_at = row["finished_at"]
            if status in ("fresh", "stale"):
                usable += 1
        if row is None:
            fresh_days, max_days = (0, 0) if static else ((1, 2) if variable == "wave_wind" else
                (area.max_age_days[variable]["fresh"], area.max_age_days[variable]["max"]))
        else:
            fresh_days, max_days = (0, 0) if static else ((1, 2) if variable == "wave_wind" else
                (area.max_age_days[variable]["fresh"], area.max_age_days[variable]["max"]))
        last_attempt = None if attempt is None else {
            "status": attempt["status"], "attempt": attempt["attempt"], "started_at": attempt["started_at"],
            "finished_at": attempt["finished_at"], "error_code": attempt["error_code"],
        }
        sources.append({
            "variable": variable,
            "source_id": source_id,
            "fetcher_role": role,
            "status": status,
            "latest_data_date": data_date,
            "latest_ingest_at": ingest_at,
            "age_days": age,
            "fresh_days": fresh_days,
            "max_age_days": max_days,
            "fallback_active": role == "fallback",
            "last_attempt": last_attempt,
        })
        degraded = degraded or status in ("stale", "expired") or role == "fallback"

    latest = {}
    for row in records["compute"]:
        if row["status"] in ("success", "partial"):
            latest[row["job_kind"]] = row
    compute = {}
    all_today = True
    for kind in ("mask", "fsi", "pick"):
        row = latest.get(kind)
        compute[kind] = {
            "last_success_at": row["finished_at"] if row else None,
            "run_date": row["run_date"] if row else None,
            "model_version": row["model_version"] if row else None,
        }
        all_today = all_today and bool(row and row["run_date"] == local_date)
    last_compute = [row["finished_at"] for row in latest.values() if row["finished_at"]]
    compute_stale = bool(last_compute and now - max(last_compute) > timedelta(hours=36))
    status = "down" if usable == 0 or compute_stale else "degraded" if degraded or not all_today else "ok"
    return {
        "api_version": API_VERSION,
        "area_id": area.area_id,
        "generated_at": now,
        "local_date": local_date,
        "status": status,
        "sources": sources,
        "compute": compute,
        "next_expected_run_at": _next_expected_run(area, now),
    }


def _age_days(value: datetime | None, area: AreaConfig, run_date: date) -> int | None:
    if value is None:
        return None
    return max(0, (run_date - local_date_of(value, area.timezone)).days)


def _spot_body(row: dict[str, Any], area: AreaConfig, run_date: date, boat_class: str) -> dict[str, Any]:
    weights = area.raw["fsi"]["weights"]
    subscore_keys = ("sst", "front", "chl", "depth", "moon", "season")
    subscores = {}
    for key in subscore_keys:
        score = row[f"s_{key}"]
        fresh = row[f"a_{key}"]
        subscores[key] = {
            "score": None if score is None else round(float(score), 3),
            "weight": float(weights[key]),
            "freshness": None if fresh is None else round(float(fresh), 3),
        }
    sst_age = _age_days(row["sst_observed_at"], area, run_date)
    chl_age = _age_days(row["chl_observed_at"], area, run_date)
    at = row["computed_at"]
    wx_at = row["wx_issued_at"]
    age_hours = None if wx_at is None else max(0, int((at - wx_at).total_seconds() // 3600))
    observation = lambda value, timestamp, age, source, product=None: {
        "value": None if value is None else float(value), "observed_at": timestamp,
        "age_days": age, "source_id": source, "product": product,
    }
    forecast = lambda value: {
        "value": None if value is None else float(value), "issued_at": wx_at, "age_hours": age_hours,
        "window_local": list(area.sea_window), "source_id": row["wx_source"],
    }
    sea_level = row["sea_state_level"]
    sea_reason = row["sea_reason_code"]
    sea_labels = {
        "calm": "Sea conditions are below the configured caution thresholds.",
        "wave_caution": "Wave height is at the caution threshold.",
        "wind_caution": "Wind speed is at the caution threshold.",
        "wave_wind_caution": "Wave height and wind speed are at caution thresholds.",
        "forecast_missing": "A usable wave or wind forecast is missing.",
        "forecast_stale": "The wave or wind forecast is stale.",
    }
    return {
        "rank": row["pick_rank"], "cell_id": row["cell_id"],
        "position": {"lat": round(float(row["lat"]), 4), "lon": round(float(row["lon"]), 4)},
        "fsi": round(float(row["fsi"])), "subscores": subscores,
        "confidence": row["confidence"], "confidence_cap": row["confidence_cap"],
        "confidence_reasons": list(row["confidence_reasons"] or []), "model_version": row["model_version"],
        "observations": {
            "sst": observation(None if row["sst_c"] is None else round(float(row["sst_c"]), 2), row["sst_observed_at"], sst_age, row["sst_source"]),
            "front": observation(None if row["sst_grad_c_per_km"] is None else round(float(row["sst_grad_c_per_km"]), 3), row["sst_observed_at"], sst_age, row["sst_source"]),
            "chl": observation(None if row["chl_mg_m3"] is None else round(float(row["chl_mg_m3"]), 3), row["chl_observed_at"], chl_age, row["chl_source"], row["chl_product"]),
            "depth": observation(None if row["depth_m"] is None else round(float(row["depth_m"])), None, None, row["depth_source"]),
            "wave": forecast(None if row["wave_window_max_m"] is None else round(float(row["wave_window_max_m"]), 2)),
            "wind": forecast(None if row["wind_window_max_kmh"] is None else round(float(row["wind_window_max_kmh"]))),
            "moon": moon_for_local_date(run_date, area.timezone),
        },
        "sea_state": {"level": sea_level, "reason_code": sea_reason,
                       "reason": sea_labels.get(sea_reason, "Sea state was computed from the configured thresholds."),
                       "boat_class": boat_class},
        "legal_status": row["mask_legal_status"], "notices": [],
    }


def _distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"])))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def _filter_spots(rows: list[dict[str, Any]], area: AreaConfig,
                  verification_level: str, limit: int) -> list[dict[str, Any]]:
    """Recheck every recommendation invariant at the read boundary; corrupt rows fail closed."""
    picked = []
    minimum = float(area.raw["fsi"]["min_spacing_km"])
    incomplete_allowed = area.raw["legal"]["incomplete_policy"] == "label"
    for row in rows:
        coordinates = (row.get("lat"), row.get("lon"), row.get("fsi"))
        if any(value is None or isinstance(value, bool) or not math.isfinite(float(value)) for value in coordinates):
            continue
        if row.get("fsi") is None or row.get("sst_c") is None or row.get("eligible") is not True:
            continue
        if row.get("is_water") is not True or row.get("eez_ok") is not True:
            continue
        if any(row.get(flag) is False for flag in ("disputed_ok", "protected_ok", "closure_ok", "boat_zone_ok")):
            continue
        if row.get("forecast_ok") is not True or row.get("sea_state_level") == "red":
            continue
        if row.get("mask_legal_status") == "incomplete" and not incomplete_allowed:
            continue
        if verification_level == "trial" and row.get("confidence") == "high":
            continue
        if area.licence_route == "B" and row.get("wx_source") == "open_meteo_marine":
            continue
        if any(_distance_km(row, previous) < minimum for previous in picked):
            continue
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked


def create_app(repository=None, *, cors_origins: tuple[str, ...] | None = None, rate_limit: int = 60) -> FastAPI:
    app = FastAPI(title="Pelago Asia API", version=SERVICE_VERSION, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.repository = repository or PostgresRepository()
    app.state.limiter = RateLimiter(limit=rate_limit)
    origins = cors_origins if cors_origins is not None else tuple(
        origin.strip() for origin in os.environ.get(
            "CORS_ALLOW_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",") if origin.strip()
    )
    for origin in origins:
        parsed = urlsplit(origin)
        if (origin == "*" or parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("CORS origins must be explicit HTTP(S) origins without credentials or paths")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["If-None-Match", "Accept", "X-Request-Id"],
        expose_headers=["ETag", "Cache-Control", "X-Request-Id"],
    )

    @app.middleware("http")
    async def request_policy(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        if len(request.url.path.encode("utf-8")) + len(request.scope.get("query_string", b"")) > 2048:
            response = _problem_body(request, 422, "validation_error", "Invalid request", errors=[
                {"param": "query", "code": "invalid_format", "message": "request target is too long"}
            ])
        else:
            client_key = request.client.host if request.client else "unknown"
            allowed, retry = app.state.limiter.allow(client_key)
            if request.method not in ("OPTIONS",) and not allowed:
                response = _problem_body(request, 429, "rate_limited", "Rate limit exceeded", "Please retry later.")
                response.headers["Retry-After"] = str(retry)
            else:
                response = await call_next(request)
        if request.method == "HEAD":
            response = Response(content=b"", status_code=response.status_code, headers=dict(response.headers))
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        vary = {value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()}
        vary.add("Accept-Encoding")
        response.headers["Vary"] = ", ".join(sorted(vary))
        if response.status_code >= 400:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(APIProblem)
    async def api_problem_handler(request: Request, exc: APIProblem):
        return _problem_body(request, exc.status, exc.code, exc.title, exc.detail)

    @app.exception_handler(ValidationProblem)
    async def validation_problem_handler(request: Request, exc: ValidationProblem):
        return _problem_body(request, 422, "validation_error", "Invalid request", errors=[
            {"param": exc.param[:32], "code": exc.code, "message": exc.message[:160]}
        ])

    @app.exception_handler(DatabaseUnavailable)
    async def database_problem_handler(request: Request, exc: DatabaseUnavailable):
        response = _problem_body(request, 503, "service_unavailable", "Service unavailable", "Database unavailable.")
        response.headers["Retry-After"] = "5"
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        return _problem_body(request, 422, "validation_error", "Invalid request", errors=[
            {"param": "request", "code": "invalid_format", "message": "request parameters are invalid"}
        ])

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return _problem_body(request, 404, "not_found", "Not found", "No matching resource.")
        if exc.status_code == 405:
            return _problem_body(request, 405, "method_not_allowed", "Method not allowed", "Only read methods are supported.")
        return _problem_body(request, exc.status_code, "internal_error", "Request failed")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        return _problem_body(request, 500, "internal_error", "Internal server error")

    @app.api_route("/v1/health", methods=["GET", "HEAD"])
    async def health(request: Request):
        ok = app.state.repository.health()
        if not ok:
            raise DatabaseUnavailable("database unavailable")
        return _response(request, {
            "api_version": API_VERSION,
            "status": "ok",
            "service_version": SERVICE_VERSION,
            "time": datetime.now(UTC).replace(microsecond=0),
            "checks": {"database": "ok"},
        }, "no-store")

    @app.api_route("/v1/areas", methods=["GET", "HEAD"])
    async def areas(request: Request):
        configs = _area_configs()
        verification = app.state.repository.list_regions_verification()
        body = {
            "api_version": API_VERSION,
            "areas": [_area_summary(area, {"level": verification.get(area.area_id, {}).get("verification_level", "trial"),
                                           "verified_trips": verification.get(area.area_id, {}).get("verified_trips", 0)})
                      for area in configs.values()],
        }
        return _response(request, body, "public, max-age=3600")

    @app.api_route("/v1/areas/{area_id}", methods=["GET", "HEAD"])
    async def area_detail(area_id: str, request: Request):
        validate_area_id(area_id)
        try:
            area = load_area(area_id)
        except ConfigError as exc:
            if "not found" in str(exc):
                raise APIProblem(404, "area_not_found", "Area not found", "No area with this id.") from exc
            raise
        verification = _verification(area, app.state.repository)
        return _response(request, _area_body(area, verification), "public, max-age=3600")

    @app.api_route("/v1/areas/{area_id}/freshness", methods=["GET", "HEAD"])
    async def freshness(area_id: str, request: Request):
        validate_area_id(area_id)
        try:
            area = load_area(area_id)
        except ConfigError as exc:
            raise APIProblem(404, "area_not_found", "Area not found", "No area with this id.") from exc
        now = datetime.now(UTC).replace(microsecond=0)
        payload = _freshness_payload(area, app.state.repository.freshness_rows(area_id), now)
        return _response(request, payload, "public, max-age=60")

    @app.api_route("/v1/areas/{area_id}/spots", methods=["GET", "HEAD"])
    async def spots(area_id: str, request: Request):
        validate_area_id(area_id)
        try:
            area = load_area(area_id)
        except ConfigError as exc:
            raise APIProblem(404, "area_not_found", "Area not found", "No area with this id.") from exc
        query = validate_spots_query(list(request.query_params.multi_items()), area.timezone,
                                     boat_classes=tuple(area.raw["boat_classes"]))
        verification = _verification(area, app.state.repository)
        bundle = app.state.repository.spots_bundle(area_id, query["date"], query["boat_class"],
                                                   area.raw["fsi"]["model_version"], verification["level"],
                                                   area.licence_route, query["limit"])
        validated_spots = _filter_spots(bundle["spots"], area, verification["level"], query["limit"])
        if bundle["status"] == "no_run":
            status = "no_run"
        elif _legal(area)["status"] == "incomplete" and area.raw["legal"]["incomplete_policy"] == "withhold":
            status = "withheld_legal_incomplete"
        elif bundle["scored"] == 0:
            status = "no_data"
        elif bundle["water"] > 0 and bundle["red"] >= bundle["water"]:
            status = "withheld_sea_red"
        elif bundle["eligible"] == 0:
            status = "no_eligible_cells"
        else:
            status = "ok" if validated_spots else "no_eligible_cells"

        boat = area.raw["boat_classes"][query["boat_class"]]
        max_wave = bundle.get("max_wave_m")
        max_wind = bundle.get("max_wind_kmh")
        red_wave = max_wave is not None and max_wave >= boat["wave_red_m"]
        red_wind = max_wind is not None and max_wind >= boat["wind_red_kmh"]
        yellow_wave = max_wave is not None and max_wave >= boat["wave_yellow_m"]
        yellow_wind = max_wind is not None and max_wind >= boat["wind_yellow_kmh"]
        if red_wave or red_wind:
            level = "red"
            reason_code = "wave_wind_danger" if red_wave and red_wind else "wave_danger" if red_wave else "wind_danger"
        elif yellow_wave or yellow_wind:
            level = "yellow"
            reason_code = "wave_wind_caution" if yellow_wave and yellow_wind else "wave_caution" if yellow_wave else "wind_caution"
        elif bundle["no_forecast"] == bundle["water"] and bundle["water"] > 0:
            level, reason_code = "yellow", "forecast_missing"
        elif bundle["water"] == 0:
            level, reason_code = "yellow", "forecast_missing"
        else:
            level, reason_code = "green", "calm"
        water = bundle["water"]
        now = datetime.now(UTC).replace(microsecond=0)
        local_date = query["date"]
        summary_sources = {name: {"source_id": None, "observed_at": None, "age_days": None, "status": "never"}
                           for name in ("sst", "chl", "depth", "wave_wind")}
        for item in bundle.get("sources", []):
            name = item["variable"]
            observed_at = item["observed_at"]
            source_id = item["source_id"]
            if name == "wave_wind" and area.licence_route == "B":
                source_id = None
                observed_at = None
            age = _age_days(observed_at, area, local_date)
            max_age = (1 if name == "wave_wind" else 0 if name == "depth" else area.max_age_days[name]["fresh"])
            max_days = (2 if name == "wave_wind" else 0 if name == "depth" else area.max_age_days[name]["max"])
            freshness_status = ("never" if source_id is None else "fresh" if age is None or age <= max_age
                                else "stale" if age <= max_days else "expired")
            summary_sources[name] = {"source_id": source_id, "observed_at": observed_at,
                                     "age_days": age, "status": freshness_status}
        spots_payload = [_spot_body(row, area, local_date, query["boat_class"]) for row in validated_spots] if status == "ok" else []
        status_details = {
            "ok": f"{len(spots_payload)} eligible spot(s) were selected.",
            "no_run": "No completed compute run exists for this date.",
            "no_data": "No cell has a usable sea-surface temperature observation.",
            "no_eligible_cells": "No scored cells are eligible for recommendation.",
            "withheld_sea_red": "All scored water cells are above the configured red sea-state threshold.",
            "withheld_legal_incomplete": "Recommendations are withheld while required legal layers are incomplete.",
        }
        etag_cache = ("public, max-age=300, stale-while-revalidate=300" if status == "ok" and local_date == local_today(area.timezone, now)
                      else "public, max-age=3600" if status == "ok" else "public, max-age=60")
        generated_at = bundle["job"]["finished_at"] if bundle.get("job") else now
        body = {
            "api_version": API_VERSION,
            "area_id": area_id,
            "date": query["date"],
            "boat_class": query["boat_class"],
            "status": status,
            "status_detail": status_details[status],
            "generated_at": generated_at,
            "run_id": str(bundle["job"]["run_id"]) if bundle.get("job") else None,
            "model_version": area.raw["fsi"]["model_version"],
            "config_hash": (bundle.get("config_sha256") or area.sha256)[:12],
            "verification_level": verification["level"],
            "confidence_ceiling": "medium" if verification["level"] == "trial" else "high",
            "legal": _legal(area),
            "area_sea_state": {"level": level, "reason_code": reason_code,
                               "reason": "Area-level worst sea state from stored mask rows.",
                               "share_red": bundle["red"] / water if water else 0.0,
                               "share_yellow": bundle["yellow"] / water if water else 0.0,
                               "share_no_forecast": bundle["no_forecast"] / water if water else 1.0,
                               "window_local": list(area.sea_window)},
            "sources": summary_sources,
            "caveats": ["legal_layers_incomplete", "no_official_warning_feed", "no_thunderstorm_rule"],
            "notices": list(area.raw["notices"]),
            "attribution_ids": [],
            "spots": spots_payload,
        }
        return _response(request, body, etag_cache)

    return app


app = create_app()
