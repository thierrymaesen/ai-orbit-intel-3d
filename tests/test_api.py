"""Tests for AI-Orbit Intelligence 3D API.

Sprint 10: Automated test suite using pytest + httpx ASGITransport.
Tests run without live TLE data (satellites may not be loaded).
"""

import pytest
import httpx

from app.main import app

transport = httpx.ASGITransport(app=app)
client = httpx.Client(transport=transport, base_url="http://testserver")


# ----------------------------------------------------------------
# 1. Health check
# ----------------------------------------------------------------
class TestHealthCheck:
    """Verify the /health endpoint returns status ok."""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_ok(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_version(self):
        data = client.get("/health").json()
        assert "version" in data
        assert data["version"] == "1.0.0"


# ----------------------------------------------------------------
# 2. Root / frontend
# ----------------------------------------------------------------
class TestFrontend:
    """Verify the root endpoint serves HTML."""

    def test_root_returns_html(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


# ----------------------------------------------------------------
# 3. Positions endpoint
# ----------------------------------------------------------------
class TestPositions:
    """Verify /api/positions returns a list (may be empty or 503 if no TLE data)."""

    def test_positions_response_code(self):
        response = client.get("/api/positions?filter_type=TOP10")
        # 200 if data loaded, 503 if not - both are valid in CI
        assert response.status_code in (200, 503)

    def test_positions_schema_when_loaded(self):
        response = client.get("/api/positions?filter_type=TOP10")
        if response.status_code == 200:
            data = response.json()
            assert "satellites" in data
            assert "total_satellites" in data
            assert "timestamp" in data
            assert isinstance(data["satellites"], list)


# ----------------------------------------------------------------
# 4. Anomalies endpoint
# ----------------------------------------------------------------
class TestAnomalies:
    """Verify /api/v1/anomalies returns 404 when no analysis has run."""

    def test_anomalies_without_data(self):
        response = client.get("/api/v1/anomalies")
        # 200 if analysis ran during lifespan, 404 if not
        assert response.status_code in (200, 404)


# ----------------------------------------------------------------
# 5. Single satellite lookup
# ----------------------------------------------------------------
class TestSatelliteLookup:
    """Verify /api/v1/satellite/{norad_id} handles missing satellites."""

    def test_satellite_not_found(self):
        response = client.get("/api/v1/satellite/9999999")
        assert response.status_code == 404


# ----------------------------------------------------------------
# 6. OpenAPI docs
# ----------------------------------------------------------------
class TestDocs:
    """Verify Swagger / OpenAPI docs are accessible."""

    def test_docs_available(self):
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json(self):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "AI-Orbit Intelligence 3D"
        assert data["info"]["version"] == "1.0.0"
