"""Readiness remediation APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.readiness_snapshot import ReadinessSnapshot
from app.models.remediation_action import RemediationAction

router = APIRouter(prefix="/readiness/remediation", tags=["AI Readiness Remediation"])


@router.get("/{db_id}")
async def readiness_remediation(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(RemediationAction).where(RemediationAction.database_id == db_id).order_by(RemediationAction.created_at.desc())
    )
    rows = result.scalars().all()
    if not rows:
        snapshot = await db.execute(
            select(ReadinessSnapshot).where(ReadinessSnapshot.database_id == db_id).order_by(ReadinessSnapshot.generated_at.desc()).limit(1)
        )
        latest = snapshot.scalars().first()
        return {
            "database_id": db_id,
            "remediations": [],
            "latest_snapshot_id": latest.id if latest else None,
        }
    return {
        "database_id": db_id,
        "remediations": [
            {
                "id": row.id,
                "readiness_snapshot_id": row.readiness_snapshot_id,
                "database_id": row.database_id,
                "issue": row.issue,
                "recommendation": row.recommendation,
                "expected_impact": row.expected_impact,
                "priority": row.priority,
                "confidence_score": row.confidence_score,
                "evidence": row.evidence,
                "trace_id": row.trace_id,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }
