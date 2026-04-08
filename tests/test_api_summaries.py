"""API integration tests for the Daily Summarizer summary endpoints.

Tests run against real output files in the project's output/ directory.
"""

from __future__ import annotations

import subprocess

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


# ---- Status endpoint ----


def test_status_endpoint():
    """GET /api/v1/status returns health info."""
    resp = client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "db_connected" in data
    assert "summary_count" in data
    assert "last_summary_date" in data


# ---- Summary list ----


def test_list_summaries():
    """GET /api/v1/summaries returns a non-empty list of dates."""
    resp = client.get("/api/v1/summaries")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 4
    for item in data:
        assert "date" in item
        assert "has_sidecar" in item


def test_list_summaries_has_preview_data():
    """Items with sidecars include meeting_count as an integer."""
    resp = client.get("/api/v1/summaries")
    data = resp.json()
    sidecar_items = [item for item in data if item["has_sidecar"]]
    assert len(sidecar_items) >= 1
    for item in sidecar_items:
        assert isinstance(item["meeting_count"], int)


# ---- Summary detail ----


def test_get_summary_with_sidecar():
    """GET a date that has both markdown and sidecar JSON."""
    resp = client.get("/api/v1/summaries/2026-04-08")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-04-08"
    assert isinstance(data["markdown"], str)
    assert len(data["markdown"]) > 0
    assert isinstance(data["sidecar"], dict)


def test_get_summary_without_sidecar():
    """GET a date that has markdown but no sidecar JSON."""
    resp = client.get("/api/v1/summaries/2026-04-01")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["markdown"], str)
    assert len(data["markdown"]) > 0
    assert data["sidecar"] is None


def test_get_summary_not_found():
    """GET a date with no summary returns 404."""
    resp = client.get("/api/v1/summaries/9999-01-01")
    assert resp.status_code == 404


def test_get_summary_invalid_date():
    """GET with an invalid date string returns 422."""
    resp = client.get("/api/v1/summaries/not-a-date")
    assert resp.status_code == 422


# ---- CORS ----


def test_cors_headers():
    """CORS preflight allows requests from localhost:3000."""
    resp = client.options(
        "/api/v1/status",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" in resp.headers
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


# ---- Architectural constraints ----


def test_no_sqlite3_in_api():
    """No direct sqlite3 imports exist anywhere in src/api/."""
    result = subprocess.run(
        ["grep", "-r", "import sqlite3", "src/api/"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"Found sqlite3 imports in api/: {result.stdout}"


def test_busy_timeout_in_db():
    """The entity db module includes busy_timeout pragma."""
    text = open("src/entity/db.py").read()
    assert "busy_timeout" in text
