"""Readiness remediation persistence."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.remediation_action import RemediationAction


class RemediationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self, database_id: int) -> list[RemediationAction]:
        result = await self.db.execute(
            select(RemediationAction).where(RemediationAction.database_id == database_id).order_by(RemediationAction.created_at.desc())
        )
        return list(result.scalars().all())

    async def persist(
        self,
        *,
        readiness_snapshot_id: int,
        database_id: int,
        recommendations: list[dict[str, Any]],
        trace_id: str | None = None,
    ) -> list[RemediationAction]:
        rows: list[RemediationAction] = []
        for item in recommendations:
            row = RemediationAction(
                readiness_snapshot_id=readiness_snapshot_id,
                database_id=database_id,
                issue=str(item.get("issue") or item.get("title") or "readiness_gap"),
                recommendation=str(item.get("recommendation") or item.get("text") or ""),
                expected_impact=item.get("expected_impact"),
                priority=item.get("priority"),
                confidence_score=float(item.get("confidence_score", 0.0) or 0.0),
                evidence=json.dumps(item.get("evidence") or [], default=str),
                trace_id=trace_id or item.get("trace_id"),
            )
            self.db.add(row)
            rows.append(row)
        await self.db.flush()
        return rows
