from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from backend import advisor
from backend.engine import EXAMPLE, recommend, simulate
from backend.main import RATE_BUCKETS, app

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_live_api(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("RULESET", "dataset-v1")
    RATE_BUCKETS.clear()
    advisor.CACHE.clear()


def test_endpoints_and_invalid_never_calls_llm():
    assert client.get("/api/health").json()["status"] == "ok"
    assert len(client.get("/api/data").json()["measures"]) == 14
    body = EXAMPLE.model_dump()
    assert client.post("/api/simulate", json=body).json()["result"]["score"] == pytest.approx(56.54307)
    assert client.post("/api/recommend", json=body).json()["candidates"]
    body["decisions"] = body["decisions"][:4]
    assert client.post("/api/preview", json=body).json()["complete"] is False
    with patch("backend.main.advisor.analyze") as mocked:
        response = client.post("/api/analyze", json=body)
        assert response.status_code == 422
        assert "score" not in response.json()
        mocked.assert_not_called()


def test_schema_tamper_body_limit_ruleset(monkeypatch):
    body = EXAMPLE.model_dump()
    body["decisions"][0]["cost"] = 0
    assert client.post("/api/simulate", json=body).status_code == 422
    assert client.post("/api/simulate", content=b"x" * 17000).status_code == 413
    assert client.post("/api/simulate", content=b"bad json").status_code == 422
    monkeypatch.setenv("RULESET", "one-per-direction-v1")
    assert client.post("/api/simulate", json=EXAMPLE.model_dump()).status_code == 409
    example = client.get("/api/data").json()["example"]
    assert client.post("/api/simulate", json=example).status_code == 200


def test_fallback_and_rate_limit():
    first = client.post("/api/analyze", json=EXAMPLE.model_dump()).json()
    assert first["source"] == "fallback_no_key"
    assert first["facts"]["score"].startswith("Score: 52.55768")
    for _ in range(11):
        assert client.post("/api/analyze", json=EXAMPLE.model_dump()).status_code == 200
    assert client.post("/api/analyze", json=EXAMPLE.model_dump()).status_code == 429


def test_mocked_provider_structured_output_cache_and_bad_references(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    result, recs = simulate(EXAMPLE), recommend(EXAMPLE)
    audit = advisor.Audit.model_validate(advisor.fallback(result, recs))
    with patch("backend.advisor.OpenAI") as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status="completed", output_text=audit.model_dump_json())
        report = advisor.analyze(EXAMPLE, result, recs)
        assert report["source"] == "openai"
        assert advisor.analyze(EXAMPLE, result, recs)["cached"] is True
        assert create.call_count == 1
        assert create.call_args.kwargs["store"] is False
        assert create.call_args.kwargs["text"]["format"]["strict"] is True
        advisor.CACHE.clear()
        audit.summary.evidence_ids = ["invented"]
        create.return_value.output_text = audit.model_dump_json()
        assert advisor.analyze(EXAMPLE, result, recs)["source"] == "fallback_api_error"


def test_refusal_timeout_and_missing_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    result, recs = simulate(EXAMPLE), recommend(EXAMPLE)
    assert advisor.analyze(EXAMPLE, result, recs)["source"] == "fallback_no_model"
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    with patch("backend.advisor.OpenAI") as sdk:
        create = sdk.return_value.__enter__.return_value.responses.create
        create.return_value = SimpleNamespace(status="incomplete", output_text="")
        assert advisor.analyze(EXAMPLE, result, recs)["source"] == "fallback_api_error"
        create.side_effect = advisor.OpenAIError("simulated provider error")
        assert advisor.analyze(EXAMPLE, result, recs)["source"] == "fallback_api_error"


def test_generated_numbers_and_unverified_recommendations_rejected():
    result, recs = simulate(EXAMPLE), recommend(EXAMPLE)
    audit = advisor.Audit.model_validate(advisor.fallback(result, recs))
    facts = advisor.facts_for(result, recs)
    audit.summary.text = "Score вырос на 999."
    with pytest.raises(ValueError):
        advisor.validate_audit(audit, facts, recs["candidates"])
    audit.summary.text = "Сценарий улучшает показатели."
    audit.recommendations[0].candidate_id = "invented"
    with pytest.raises(ValueError):
        advisor.validate_audit(audit, facts, recs["candidates"])
