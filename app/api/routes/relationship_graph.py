"""
Relationship graph APIs.
"""

import json
import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.cache_service import cache_service
from app.schema_engine.relationship_graph import RelationshipGraphEngine
from app.services.relationship_package_mapper import relationship_package_to_dto
from app.core.structured_logging import api_message, error_message
from app.schemas.api_schemas import (
    GraphExportResponse,
    RelationshipGraphResponse,
    TableNeighborsResponse,
    JoinPathsResponse,
    RelationshipPackageResponse,
    RelationshipLineageResponse,
)

router = APIRouter(tags=["Relationship Graph"])
logger = logging.getLogger(__name__)


def _map_join_columns(items):
    return [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in items]


def _map_nodes(items):
    return [asdict(item) for item in items]


def _map_edges(items):
    payload = []
    for item in items:
        data = asdict(item)
        data["join_columns"] = _map_join_columns(data.get("join_columns", []))
        payload.append(data)
    return payload


def _map_paths(items):
    paths = []
    for path in items:
        path_data = asdict(path)
        path_data["steps"] = [
            {
                **asdict(step),
                "join_columns": _map_join_columns(asdict(step).get("join_columns", [])),
            }
            for step in path.steps
        ]
        paths.append(path_data)
    return paths


@router.get(
    "/relationships/graph/{db_id}",
    response_model=RelationshipGraphResponse,
    summary="Get the persisted relationship graph for a database",
)
async def get_relationship_graph(db_id: int, db: AsyncSession = Depends(get_db)) -> RelationshipGraphResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    cache_key = f"relationships:{db_id}:graph"
    cached = await cache_service.get(cache_key)
    if cached:
        payload = json.loads(cached)
        payload["cache_status"] = "cache"
        logger.info(api_message("relationships graph", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
        return RelationshipGraphResponse.model_validate(payload)
    try:
        snapshot = await engine.get_relationship_graph(db_id)
        payload = asdict(snapshot)
        payload["metrics"] = asdict(snapshot.metrics)
        payload["nodes"] = _map_nodes(snapshot.nodes)
        payload["edges"] = _map_edges(snapshot.edges)
        payload["cache_status"] = "live"
        await cache_service.set(cache_key, json.dumps(payload, default=str), ttl_seconds=600)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(api_message("relationships graph", db_id=db_id, duration_ms=f"{duration_ms:.2f}"))
        return RelationshipGraphResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("relationship graph lookup failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build relationship graph",
        )


@router.get(
    "/relationships/{db_id}",
    response_model=RelationshipPackageResponse,
    summary="Get canonical relationship package for a database",
)
async def get_relationship_package(db_id: int, db: AsyncSession = Depends(get_db)) -> RelationshipPackageResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    cache_key = f"relationships:{db_id}:package"
    cached = await cache_service.get(cache_key)
    if cached:
        payload = json.loads(cached)
        payload["cache_status"] = "cache"
        logger.info(api_message("relationships package", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
        return RelationshipPackageResponse.model_validate(payload)
    package = await engine.get_relationship_package(db_id)
    normalized = {
        "database_id": package.get("database_id", db_id),
        "packages": [asdict(relationship_package_to_dto(item)) for item in package.get("packages", [])],
        "cache_status": "live",
    }
    await cache_service.set(cache_key, json.dumps(normalized, default=str), ttl_seconds=600)
    logger.info(api_message("relationships package", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
    return RelationshipPackageResponse.model_validate(normalized)


@router.get(
    "/relationships/domains/{db_id}",
    response_model=RelationshipPackageResponse,
    summary="Get domain-scoped relationship packages for a database",
)
async def get_relationship_domains(db_id: int, db: AsyncSession = Depends(get_db)) -> RelationshipPackageResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    cache_key = f"relationships:{db_id}:domains"
    cached = await cache_service.get(cache_key)
    if cached:
        payload = json.loads(cached)
        payload["cache_status"] = "cache"
        logger.info(api_message("relationships domains", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
        return RelationshipPackageResponse.model_validate(payload)
    package = await engine.get_relationship_package(db_id)
    normalized = {
        "database_id": package.get("database_id", db_id),
        "packages": [asdict(relationship_package_to_dto(item)) for item in package.get("packages", [])],
        "cache_status": "live",
    }
    await cache_service.set(cache_key, json.dumps(normalized, default=str), ttl_seconds=600)
    logger.info(api_message("relationships domains", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
    return RelationshipPackageResponse.model_validate(normalized)


@router.get(
    "/relationships/lineage/{db_id}",
    response_model=RelationshipLineageResponse,
    summary="Get relationship lineage for a database",
)
async def get_relationship_lineage(db_id: int, db: AsyncSession = Depends(get_db)) -> RelationshipLineageResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    cache_key = f"relationships:{db_id}:lineage"
    cached = await cache_service.get(cache_key)
    if cached:
        payload = json.loads(cached)
        logger.info(api_message("relationships lineage", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}", cache_hit=True))
        return RelationshipLineageResponse.model_validate(payload)
    package = await engine.get_relationship_package(db_id)
    lineage: list[dict] = []
    for item in package.get("packages", []):
        dto = relationship_package_to_dto(item)
        lineage.extend(dto.entity_graph or [])
        lineage.extend(dto.lifecycle_flows or [])
    payload = {"database_id": db_id, "lineage": lineage}
    await cache_service.set(cache_key, json.dumps(payload, default=str), ttl_seconds=600)
    logger.info(api_message("relationships lineage", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
    return RelationshipLineageResponse.model_validate(payload)


@router.get(
    "/relationships/tables/{table_id}/neighbors",
    response_model=TableNeighborsResponse,
    summary="Get neighbor tables around a table",
)
async def get_table_neighbors(
    table_id: int,
    depth: int = Query(default=1, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
) -> TableNeighborsResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    try:
        snapshot = await engine.get_neighbors(table_id, depth=depth)
        payload = asdict(snapshot)
        payload["neighbors"] = _map_nodes(snapshot.neighbors)
        payload["edges"] = _map_edges(snapshot.edges)
        logger.info(api_message("relationships neighbors", table_id=table_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return TableNeighborsResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("neighbor lookup failed", table_id=table_id, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load table neighbors",
        )


@router.get(
    "/relationships/join-paths/{table_a}/{table_b}",
    response_model=JoinPathsResponse,
    summary="Get join path(s) between two tables",
)
async def get_join_paths(
    table_a: int,
    table_b: int,
    max_paths: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> JoinPathsResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    try:
        snapshot = await engine.get_join_paths(table_a, table_b, max_paths=max_paths)
        payload = asdict(snapshot)
        payload["paths"] = _map_paths(snapshot.paths)
        logger.info(api_message("relationships join paths", table_a=table_a, table_b=table_b, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return JoinPathsResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("join path lookup failed", table_a=table_a, table_b=table_b, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load join paths",
        )


@router.get(
    "/relationships/graph/{db_id}/export",
    response_model=GraphExportResponse,
    summary="Export the relationship graph as JSON, markdown, or a Mermaid diagram",
)
async def export_relationship_graph(
    db_id: int,
    export_format: str = Query(default="json", pattern="^(json|markdown|diagram)$"),
    db: AsyncSession = Depends(get_db),
) -> GraphExportResponse:
    engine = RelationshipGraphEngine(db)
    start = time.perf_counter()
    try:
        snapshot = await engine.get_relationship_graph(db_id)
        bundle = engine.export_graph(snapshot, export_format=export_format)
        logger.info(api_message("relationships export", db_id=db_id, duration_ms=f"{(time.perf_counter() - start) * 1000:.2f}"))
        return GraphExportResponse(
            format=bundle.format,
            filename=bundle.filename,
            content=bundle.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(error_message("graph export failed", db_id=db_id, reason=exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export relationship graph",
        )
