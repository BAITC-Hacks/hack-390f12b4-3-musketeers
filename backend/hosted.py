"""Single-process deployment: public assets and API on the same origin."""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from backend.main import app as api, check, body_limit
from backend.engine import Scenario
from frontend.server import headers

app = FastAPI(title="Аким на 5 часов", version="2.1.0")
app.include_router(api.router)
app.middleware("http")(body_limit)
app.middleware("http")(headers)


@app.get("/download/scenario")
def download(payload: str):
    if len(payload.encode()) > 16384:
        raise HTTPException(413, "Сценарий превышает 16 КБ.")
    try:
        scenario = Scenario.model_validate_json(payload)
    except ValidationError:
        raise HTTPException(422, "Некорректный сценарий.") from None
    check(scenario, final=False)
    return Response(json.dumps(scenario.model_dump(), ensure_ascii=False, indent=2),
                    media_type="application/json", headers={"Content-Disposition": 'attachment; filename="astana-scenario.json"'})


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "frontend/web", html=True), name="web")
