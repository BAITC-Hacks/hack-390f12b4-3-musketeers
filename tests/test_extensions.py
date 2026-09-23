from copy import deepcopy
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import pytest
from backend.engine import DATA, EXAMPLE, Scenario, recommend, simulate
from backend.events import event_data
from backend import advisor, leaderboard
from backend.main import app, RATE_BUCKETS


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "city.sqlite3"))
    monkeypatch.setenv("RULESET", "dataset-v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
    RATE_BUCKETS.clear()
    advisor.CACHE.clear()


def test_event_is_deterministic_and_preserves_official_dataset():
    original = deepcopy(DATA)
    winter = EXAMPLE.model_copy(update={"event_id": "winter-v1"})
    first, second = simulate(winter), simulate(winter)
    assert first == second
    assert first["baseline"]["score"] < simulate(EXAMPLE)["baseline"]["score"]
    assert first["spent"] == 95 and first["remaining"] == 5
    assert DATA == original
    assert simulate(EXAMPLE)["result"]["score"] == pytest.approx(56.54307)
    altered = event_data(DATA, "winter-v1")
    assert next(d for d in altered["districts"] if d["id"] == "almaty")["values"]["C1"] == next(d for d in DATA["districts"] if d["id"] == "almaty")["values"]["C1"] - 15
    for c in recommend(winter)["candidates"]:
        assert c["scenario"]["event_id"] == "winter-v1"
        assert simulate(Scenario.model_validate(c["scenario"]))["result"]["score"] == c["score"]


def test_leaderboard_recomputes_persists_and_separates_conditions():
    client = TestClient(app)
    body = {"team_name": "Test Team", "token": str(uuid4()), "scenario": EXAMPLE.model_dump()}
    assert client.post("/api/submit", json={**body, "score": 999}).status_code == 422
    assert client.post("/api/submit", json=body).json()["score"] == pytest.approx(56.54307)
    assert TestClient(app).get("/api/leaderboard").json()["entries"][0]["team_name"] == "Test Team"
    assert client.get("/api/leaderboard?event_id=winter-v1").json()["entries"] == []
    assert client.post("/api/submit", json={**body, "token": str(uuid4())}).status_code == 409
    assert client.post("/api/submit", json={**body, "team_name": "Updated Team"}).status_code == 200
    rows = client.get("/api/leaderboard").json()["entries"]
    assert len(rows) == 1 and rows[0]["team_name"] == "Updated Team"
    assert "owner" not in rows[0] and "token" not in rows[0]
    body["scenario"]["decisions"] = []
    assert client.post("/api/submit", json=body).status_code == 422


def test_unknown_events_and_demo_access(monkeypatch):
    client = TestClient(app)
    body = EXAMPLE.model_dump()
    assert client.post("/api/preview", json={**body, "event_id": "invented"}).status_code == 422
    assert client.get("/api/leaderboard?event_id=invented").status_code == 422
    monkeypatch.setenv("DEMO_ACCESS_CODE", "demo-test")
    for _ in range(13):
        assert client.post("/api/analyze", json=body).status_code == 403
    assert client.post("/api/analyze", json=body, headers={"X-Demo-Code": "demo-test"}).status_code == 200
    assert client.post("/api/simulate", json=body).status_code == 200


def test_daily_limit_is_atomic_and_persistent(monkeypatch):
    monkeypatch.setenv("AI_DAILY_LIMIT", "3")
    # Initialize schema before independent concurrent connections.
    with leaderboard.database():
        pass
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: leaderboard.reserve_ai_call(), range(12)))
    assert sum(results) == 3
    assert not leaderboard.reserve_ai_call()


def test_hosted_entrypoint_assets_and_download():
    from backend.hosted import app as hosted
    client = TestClient(hosted)
    assert client.get("/").status_code == 200
    assert client.get("/.env").status_code == 404
    assert client.get("/backend/main.py").status_code == 404
    assert client.get("/api/health").status_code == 200
    result = client.get("/download/scenario", params={"payload": EXAMPLE.model_dump_json()})
    assert result.json() == EXAMPLE.model_dump()
    assert "attachment" in result.headers["content-disposition"]


def test_submission_rate_limit():
    client = TestClient(app)
    body = {"team_name": "Rate Test", "token": str(uuid4()), "scenario": EXAMPLE.model_dump()}
    for _ in range(12):
        assert client.post("/api/submit", json=body).status_code == 200
    assert client.post("/api/submit", json=body).status_code == 429
