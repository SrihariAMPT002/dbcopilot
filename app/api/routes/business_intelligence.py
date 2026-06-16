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

router = APIRouter(prefix="/business-intelligence", tags=["Business Intelligence"])
logger = logging.getLogger(__name__)


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
