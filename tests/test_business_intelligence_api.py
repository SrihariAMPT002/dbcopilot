from __future__ import annotations

from unittest.mock import AsyncMock

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


def test_business_intelligence_opportunities_returns_404_for_missing_database(client):
    response = client.get("/api/v1/business-intelligence/opportunities/999999")
    assert response.status_code == 404


def test_business_intelligence_predictive_readiness_returns_404_for_missing_database(client):
    response = client.get("/api/v1/business-intelligence/predictive-readiness/999999")
    assert response.status_code == 404
