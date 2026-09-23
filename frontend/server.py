"""Serve the web UI and proxy its API calls to the calculation service."""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles


class SafeStaticFiles(StaticFiles):
    """Treat invalid Windows filenames in URLs as missing assets."""

    def lookup_path(self, path):
        try:
            return super().lookup_path(path)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 123:
                return "", None
            raise


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(
        base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        timeout=httpx.Timeout(50, connect=3), trust_env=False,
    ) as client:
        app.state.api = client
        yield


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
ENDPOINTS = {"data": "GET", "health": "GET", "preview": "POST", "simulate": "POST", "recommend": "POST", "analyze": "POST", "leaderboard": "GET", "submit": "POST"}


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@app.api_route("/api/{endpoint}", methods=["GET", "POST"])
async def proxy(endpoint: str, request: Request):
    if ENDPOINTS.get(endpoint) != request.method:
        return JSONResponse({"detail": "Маршрут не найден."}, status_code=404)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16384:
            return JSONResponse({"detail": "Запрос превышает 16 КБ."}, status_code=413)
    try:
        result = await request.app.state.api.request(
            request.method, f"/api/{endpoint}", content=bytes(body), params=request.query_params,
            headers={"Content-Type": "application/json", "X-Demo-Code": request.headers.get("X-Demo-Code", "")},
        )
    except httpx.RequestError:
        return JSONResponse({"detail": "Нет связи с сервером расчёта. Попробуйте ещё раз."}, status_code=503)
    return Response(result.content, status_code=result.status_code,
                    media_type="application/json")


@app.get("/download/scenario")
async def download_scenario(request: Request, payload: str):
    """Use a normal HTTP attachment; embedded browsers may not support blob downloads."""
    if len(payload.encode("utf-8")) > 16384:
        return JSONResponse({"detail": "Сценарий превышает 16 КБ."}, status_code=413)
    try:
        value = json.loads(payload)
    except ValueError:
        return JSONResponse({"detail": "Некорректный JSON."}, status_code=422)
    try:
        checked = await request.app.state.api.post("/api/preview", json=value)
    except httpx.RequestError:
        return JSONResponse({"detail": "Нет связи с сервером расчёта."}, status_code=503)
    if checked.status_code != 200:
        return Response(checked.content, status_code=checked.status_code, media_type="application/json")
    return Response(json.dumps(value, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="astana-scenario.json"'})


app.mount("/", SafeStaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
