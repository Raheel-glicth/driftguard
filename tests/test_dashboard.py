from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from driftguard.api.dashboard import create_dashboard_router
from driftguard.sdk import DriftGuard


def test_dashboard_routes_render_project_hub_and_reports(guard: DriftGuard) -> None:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(create_dashboard_router(guard))

    with TestClient(app) as client:
        home_response = client.get("/")
        reports_response = client.get("/reports")
        legacy_response = client.get("/dashboard")

    assert home_response.status_code == 200
    assert "DriftGuard Project Hub" in home_response.text
    assert "Live Chat Demo" in home_response.text
    assert "DriftGuard Reports" in home_response.text

    assert reports_response.status_code == 200
    assert "DriftGuard Reports" in reports_response.text
    assert "Focused Trace Report" in reports_response.text

    assert legacy_response.status_code == 200
    assert "DriftGuard Reports" in legacy_response.text
