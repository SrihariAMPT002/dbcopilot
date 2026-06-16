from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


async def _mock_get_db():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    yield session


app.dependency_overrides[get_db] = _mock_get_db


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_stage_progress_endpoint_returns_payload(client):
    fake_payload = {
        "database_id": 1,
        "parent_job_id": 10,
        "overall_status": "running",
        "overall_progress_percentage": 50,
        "current_stage": "relationships",
        "completed_stages": 2,
        "running_stages": 1,
        "failed_stages": 0,
        "pending_stages": 5,
        "stages": [],
        "graph": [],
        "message": "Stage progress loaded.",
    }

    with patch(
        "app.api.routes.pipeline.DatabasePipelineOrchestrator.get_stage_progress",
        new=AsyncMock(return_value=fake_payload),
    ):
        response = client.get("/api/v1/pipeline/stage-progress/1")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "running"
    assert body["current_stage"] == "relationships"
