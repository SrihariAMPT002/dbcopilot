"""AI business intelligence APIs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.data_product_service import DataProductService
from app.services.opportunity_service import OpportunityService
from app.services.predictive_readiness_service import PredictiveReadinessService
from app.services.recommendation_service import RecommendationService
from app.services.warehouse_design_service import WarehouseDesignService
from app.models.business_insight import BusinessInsight
from app.models.recommendation import Recommendation
from app.models.data_product import DataProduct
from app.models.warehouse_design import WarehouseDesign
from app.models.predictive_readiness import PredictiveReadiness
from sqlalchemy import func, select

router = APIRouter(prefix="/business-intelligence", tags=["Business Intelligence"])
logger = logging.getLogger(__name__)


@router.get("/health/{db_id}")
async def health(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    counts = {}
    for label, model, field, extra_filter in [
        ("business_insights", BusinessInsight, BusinessInsight.database_id, None),
        ("opportunities", Recommendation, Recommendation.database_id, Recommendation.recommendation_type == "opportunity"),
        ("recommendations", Recommendation, Recommendation.database_id, Recommendation.recommendation_type != "opportunity"),
        ("data_products", DataProduct, DataProduct.database_id, None),
        ("warehouse_designs", WarehouseDesign, WarehouseDesign.database_id, None),
        ("predictive_readiness", PredictiveReadiness, PredictiveReadiness.database_id, None),
    ]:
        stmt = select(func.count(model.id)).where(field == db_id)
        latest_stmt = select(model).where(field == db_id)
        if extra_filter is not None:
          stmt = stmt.where(extra_filter)
          latest_stmt = latest_stmt.where(extra_filter)
        result = await db.execute(stmt)
        latest = await db.execute(latest_stmt.order_by(model.created_at.desc()).limit(1))
        row = latest.scalars().first()
        counts[label] = {
            "count": int(result.scalar() or 0),
            "latest_trace_id": getattr(row, "trace_id", None) if row else None,
            "state": "empty" if not row else "healthy",
        }
    return {"database_id": db_id, "packages": counts}


@router.post("/generate/{db_id}")
async def generate_business_intelligence(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        opportunities = await OpportunityService(db).generate_for_database(db_id)
        data_products = await DataProductService(db).generate_for_database(db_id)
        warehouse_designs = await WarehouseDesignService(db).generate_for_database(db_id)
        recommendations = await RecommendationService(db).generate_for_database(db_id)
        predictive_readiness = await PredictiveReadinessService(db).generate_for_database(db_id)
        return {
            "database_id": db_id,
            "opportunities": opportunities,
            "data_products": data_products,
            "warehouse_designs": warehouse_designs,
            "recommendations": recommendations,
            "predictive_readiness": predictive_readiness,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Business intelligence generation failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate business intelligence")


@router.get("/opportunities/{db_id}")
async def get_opportunities(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await OpportunityService(db).get_opportunities(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/data-products/{db_id}")
async def get_data_products(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await DataProductService(db).get_products(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/warehouse-designs/{db_id}")
async def get_warehouse_designs(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await WarehouseDesignService(db).get_designs(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/recommendations/{db_id}")
async def get_recommendations(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await RecommendationService(db).get_recommendations(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/predictive-readiness/{db_id}")
async def get_predictive_readiness(db_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await PredictiveReadinessService(db).get_predictive_readiness(db_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
