"""HTTP boundary: validate and recalculate all client scenarios."""
from collections import OrderedDict, deque
import os
from threading import Lock
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from backend import advisor
from backend.engine import DATA, EXAMPLE, RULESETS, Scenario, project, recommend, simulate, validate

app = FastAPI(title="Аким на 5 часов", version="2.0.0")
RATE_BUCKETS = OrderedDict()
RATE_LOCK = Lock()


def active_ruleset():
    value = os.getenv("RULESET", "dataset-v1")
    if value not in RULESETS:
        raise RuntimeError("Unknown server RULESET")
    return value


def check(scenario, final=True):
    if scenario.ruleset != active_ruleset():
        raise HTTPException(409, detail=[{"code": "ruleset", "message": "Сценарий использует другой набор правил. Обновите страницу.", "affectedDecisionIds": []}])
    errors = validate(scenario, final=final)
    if errors:
        raise HTTPException(422, detail=errors)


@app.middleware("http")
async def body_limit(request: Request, call_next):
    if request.method == "POST":
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                return JSONResponse({"detail": "Запрос превышает 16 КБ."}, status_code=413)
        request._body = bytes(body)
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok", "ruleset": active_ruleset(), "dataset_version": DATA["version"],
            "ai_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))}


@app.get("/api/data")
def get_data():
    example = EXAMPLE
    if active_ruleset() == "one-per-direction-v1":
        example = Scenario.model_validate({"ruleset": active_ruleset(), "decisions": [
            {"measure_id": "M2"}, {"measure_id": "M4", "district_id": "saryarka"},
            {"measure_id": "M7", "district_id": "nura"}, {"measure_id": "M10", "district_id": "nura"},
            {"measure_id": "M12"}]})
    return {**DATA, "ruleset": active_ruleset(), "baseline": project([]), "example": example.model_dump()}


@app.post("/api/preview")
def preview(scenario: Scenario):
    check(scenario, final=False)
    return {"complete": len(scenario.decisions) == 5, "projection": project(scenario.decisions)}


@app.post("/api/simulate")
def simulation(scenario: Scenario):
    check(scenario)
    return simulate(scenario)


@app.post("/api/recommend")
def recommendations(scenario: Scenario):
    check(scenario)
    return recommend(scenario)


@app.post("/api/analyze")
def analyze(scenario: Scenario, request: Request):
    check(scenario)
    address = request.client.host if request.client else "unknown"
    now = monotonic()
    with RATE_LOCK:
        bucket = RATE_BUCKETS.setdefault(address, deque())
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 12:
            raise HTTPException(429, detail="Слишком много запросов анализа. Повторите через минуту.")
        bucket.append(now)
        RATE_BUCKETS.move_to_end(address)
        while len(RATE_BUCKETS) > 1024:
            RATE_BUCKETS.popitem(last=False)
    calculated = simulate(scenario)
    candidates = recommend(scenario)
    return advisor.analyze(scenario, calculated, candidates)
