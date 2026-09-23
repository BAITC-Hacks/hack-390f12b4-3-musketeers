"""Exercise the UI proxy against the real calculation API without networking."""
from contextlib import asynccontextmanager

import httpx
from fastapi.testclient import TestClient
import pytest

from backend.engine import EXAMPLE
from backend.main import app as backend
from frontend.server import app


@pytest.fixture
def client(monkeypatch):
    @asynccontextmanager
    async def lifespan(application):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),
                                     base_url="http://test-api") as api:
            application.state.api = api
            yield

    monkeypatch.setattr(app.router, "lifespan_context", lifespan)
    monkeypatch.setenv("RULESET", "dataset-v1")
    with TestClient(app) as client:
        yield client


def test_ui_serves_only_public_assets(client):
    page = client.get("/")
    assert page.status_code == 200
    assert 'lang="ru"' in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200
    for path in ("/.env", "/server.py", "/api/unknown", "/api/analyze"):
        assert client.get(path).status_code == 404


def test_proxy_preserves_validation_and_exact_score(client):
    body = EXAMPLE.model_dump()
    result = client.post("/api/simulate", json=body)
    assert result.status_code == 200
    assert result.json()["result"]["score"] == pytest.approx(56.54307)
    body["decisions"] = [
        {"measure_id": "M3", "district_id": "nura"},
        {"measure_id": "M5", "district_id": "saryarka"},
        {"measure_id": "M7", "district_id": "nura"},
        {"measure_id": "M8", "district_id": "nura"},
        {"measure_id": "M13", "district_id": "almaty"},
    ]
    response = client.post("/api/preview", json=body)
    assert response.status_code == 422
    assert any(e["code"] == "budget" for e in response.json()["detail"])
    assert "projection" not in response.json()
    body["ruleset"] = "one-per-direction-v1"
    assert client.post("/api/simulate", json=body).status_code == 409


def test_proxy_rejects_oversized_body_and_unknown_fields(client):
    assert client.post("/api/preview", content=b"x" * 16385).status_code == 413
    body = EXAMPLE.model_dump()
    body["cost"] = 0
    assert client.post("/api/preview", json=body).status_code == 422


def test_download_is_attachment_and_revalidates_the_plan(client):
    result = client.get("/download/scenario", params={"payload": EXAMPLE.model_dump_json()})
    assert result.status_code == 200
    assert "attachment;" in result.headers["content-disposition"]
    assert result.json() == EXAMPLE.model_dump()
    assert client.get("/download/scenario", params={"payload": '{"decisions":[{"measure_id":"unknown"}]}'}).status_code == 422
    assert client.get("/download/scenario", params={"payload": "invalid"}).status_code == 422
    assert client.get("/download/scenario", params={"payload": "x" * 16385}).status_code == 413


def test_proxy_reports_backend_offline(client):
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError("offline")

    original = app.state.api.request
    app.state.api.request = unavailable
    try:
        response = client.get("/api/data")
        assert response.status_code == 503
        assert "Нет связи" in response.json()["detail"]
    finally:
        app.state.api.request = original
