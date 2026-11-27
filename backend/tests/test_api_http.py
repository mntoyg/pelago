import asyncio

import httpx

from api.main import RateLimiter, create_app
from api.repository import DatabaseUnavailable


class FakeRepository:
    def __init__(self):
        self.verification_level = "trial"

    def health(self):
        return True

    def region_verification(self, area_id):
        return {"verification_level": self.verification_level, "verified_trips": 0}

    def list_regions_verification(self):
        return {"th-chonburi-coast": {"region_id": "th-chonburi-coast", "verification_level": self.verification_level,
                                       "verified_trips": 0}}

    def freshness_rows(self, area_id):
        return {"success": [], "attempts": [], "compute": []}

    def spots_bundle(self, area_id, run_date, boat_class, model_version, verification_level, licence_route, limit):
        return {"status": "no_run", "job": None, "scored": 0, "eligible": 0, "water": 0, "red": 0,
                "yellow": 0, "no_forecast": 0, "max_wave_m": None, "max_wind_kmh": None,
                "config_sha256": None, "sources": [], "spots": []}


class APITestClient:
    def __init__(self, rate_limit=60, repository=None):
        self.app = create_app(repository or FakeRepository(), cors_origins=("http://localhost:8000",), rate_limit=rate_limit)

    async def _send(self, method, path, headers=None):
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers)

    def request(self, method, path, headers=None):
        return asyncio.run(self._send(method, path, headers))

    def get(self, path, headers=None):
        return self.request("GET", path, headers)


def client(rate_limit=60, repository=None):
    return APITestClient(rate_limit=rate_limit, repository=repository)


def test_health_returns_utc_and_required_headers():
    response = client().get("/v1/health")
    assert response.status_code == 200
    assert response.json()["time"].endswith("Z")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_area_detail_exposes_incomplete_legal_trial_label():
    response = client().get("/v1/areas/th-chonburi-coast")
    assert response.status_code == 200
    body = response.json()
    assert body["legal"]["status"] == "incomplete"
    assert body["label"] == "trial: legal layers incomplete"
    assert body["verification"]["level"] == "trial"
    assert body["legal"]["label"] == "trial: legal layers incomplete"
    assert all({"variable", "source_id", "role", "provider", "dataset_id", "route_allowed"} <= set(source)
               for source in body["sources"])


def test_area_list_exposes_contract_summary_fields():
    response = client().get("/v1/areas")
    assert response.status_code == 200
    area = response.json()["areas"][0]
    assert {"area_id", "name", "country_code", "bbox", "timezone", "legal_status", "verification_level"} <= set(area)


def test_unknown_area_and_unknown_path_use_problem_details():
    unknown = client().get("/v1/areas/th-not-configured")
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "area_not_found"
    assert unknown.headers["content-type"].startswith("application/problem+json")
    missing = client().get("/v1/not-an-endpoint")
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_unicode_path_and_oversized_target_are_422_not_500():
    unicode_path = client().get("/v1/areas/th-caf%C3%A9")
    assert unicode_path.status_code == 422
    assert unicode_path.json()["errors"][0]["code"] == "invalid_format"
    too_long = client().get("/v1/areas/" + "a" * 2100)
    assert too_long.status_code == 422


def test_health_database_errors_are_safe_and_retryable():
    class DownRepository(FakeRepository):
        def health(self):
            raise DatabaseUnavailable("dsn=postgresql://user:private@database.invalid/db")

    response = client(repository=DownRepository()).get("/v1/health")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert "private" not in response.text and "database.invalid" not in response.text
    assert "Traceback" not in response.text


def test_spots_rejects_unknown_and_repeated_parameters():
    unknown = client().get("/v1/areas/th-chonburi-coast/spots?boatclass=small")
    assert unknown.status_code == 422
    assert unknown.json()["errors"][0]["code"] == "unknown_parameter"
    duplicate = client().get("/v1/areas/th-chonburi-coast/spots?date=2026-11-27&date=2026-11-26")
    assert duplicate.status_code == 422
    assert duplicate.json()["errors"][0]["code"] == "invalid_format"
    unicode_value = client().get("/v1/areas/th-chonburi-coast/spots?boat_class=small%E2%9D%A4")
    assert unicode_value.status_code == 422
    assert unicode_value.json()["errors"][0]["code"] == "invalid_format"


def test_empty_spots_is_a_contract_200_with_no_run_status():
    response = client().get("/v1/areas/th-chonburi-coast/spots")
    assert response.status_code == 200
    assert response.json()["status"] == "no_run"
    assert response.json()["spots"] == []


def test_freshness_response_has_all_source_slots_and_compute_jobs():
    response = client().get("/v1/areas/th-chonburi-coast/freshness")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "down"
    assert {item["variable"] for item in body["sources"]} == {"sst", "chl", "depth", "wave_wind"}
    assert set(body["compute"]) == {"mask", "fsi", "pick"}


def test_etag_is_deterministic_and_conditional_get_returns_304():
    test_client = client()
    first = test_client.get("/v1/areas/th-chonburi-coast")
    second = test_client.get("/v1/areas/th-chonburi-coast")
    assert first.headers["etag"] == second.headers["etag"]
    cached = test_client.get("/v1/areas/th-chonburi-coast", headers={"If-None-Match": first.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""


def test_etag_changes_when_the_response_body_changes():
    repository = FakeRepository()
    test_client = client(repository=repository)
    trial = test_client.get("/v1/areas/th-chonburi-coast")
    repository.verification_level = "beta"
    beta = test_client.get("/v1/areas/th-chonburi-coast")
    assert trial.json()["verification"]["level"] == "trial"
    assert beta.json()["verification"]["level"] == "beta"
    assert trial.headers["etag"] != beta.headers["etag"]


def test_cors_only_echoes_allowlisted_origin():
    test_client = client()
    allowed = test_client.get("/v1/health", headers={"Origin": "http://localhost:8000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8000"
    denied = test_client.get("/v1/health", headers={"Origin": "https://attacker.invalid"})
    assert "access-control-allow-origin" not in denied.headers


def test_cors_preflight_and_head_are_supported_without_body():
    test_client = client()
    preflight = test_client.request("OPTIONS", "/v1/health", headers={
        "Origin": "http://localhost:8000", "Access-Control-Request-Method": "GET",
    })
    assert preflight.status_code == 200
    head = test_client.request("HEAD", "/v1/health")
    assert head.status_code == 200
    assert head.content == b""


def test_wildcard_cors_configuration_fails_closed():
    try:
        create_app(FakeRepository(), cors_origins=("*",))
    except ValueError as exc:
        assert "explicit" in str(exc)
    else:
        raise AssertionError("wildcard CORS origin must be rejected")


def test_non_read_method_is_rejected_with_problem_details():
    response = client().request("POST", "/v1/health")
    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


def test_rate_limit_is_bounded_and_returns_retry_after():
    test_client = client(rate_limit=1)
    assert test_client.get("/v1/health").status_code == 200
    limited = test_client.get("/v1/health")
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) >= 1


def test_rate_limiter_bounds_distinct_client_keys_and_reclaims_expired_windows():
    limiter = RateLimiter(limit=10, window_seconds=10, max_keys=2)
    assert limiter.allow("client-a", now=1)[0] is True
    assert limiter.allow("client-b", now=1)[0] is True
    assert limiter.allow("client-c", now=1)[0] is False
    assert len(limiter._buckets) == 2
    assert limiter.allow("client-c", now=21)[0] is True
    assert len(limiter._buckets) == 1
