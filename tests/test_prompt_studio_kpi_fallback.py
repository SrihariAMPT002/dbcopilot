from __future__ import annotations

import pytest

from app.services.prompt_studio_service import PromptStudioService


class _FailingDB:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("kpi unavailable")


@pytest.mark.asyncio
async def test_fetch_kpi_summary_gracefully_handles_errors():
    service = PromptStudioService(_FailingDB())

    summary = await service._fetch_kpi_summary(1)

    assert summary["kpi_count"] == 0
    assert summary["kpis"] == []
    assert summary["unavailable"] is True
