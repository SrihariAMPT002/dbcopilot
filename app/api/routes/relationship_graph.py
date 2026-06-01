"""
Relationship graph APIs.
"""

import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schema_engine.relationship_graph import RelationshipGraphEngine
from app.schemas.api_schemas import GraphExportResponse, RelationshipGraphResponse, TableNeighborsResponse, JoinPathsResponse

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
@router.get(
    "/relationship-graph/{db_id}",
    response_model=RelationshipGraphResponse,
    include_in_schema=False,
)
async def get_relationship_graph(db_id: int, db: AsyncSession = Depends(get_db)) -> RelationshipGraphResponse:
    engine = RelationshipGraphEngine(db)
    try:
        snapshot = await engine.get_relationship_graph(db_id)
        payload = asdict(snapshot)
        payload["metrics"] = asdict(snapshot.metrics)
        payload["nodes"] = _map_nodes(snapshot.nodes)
        payload["edges"] = _map_edges(snapshot.edges)
        return RelationshipGraphResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Relationship graph lookup failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build relationship graph",
        )


@router.get(
    "/relationships/tables/{table_id}/neighbors",
    response_model=TableNeighborsResponse,
    summary="Get neighbor tables around a table",
)
@router.get(
    "/table-neighbors/{table_id}",
    response_model=TableNeighborsResponse,
    include_in_schema=False,
)
async def get_table_neighbors(
    table_id: int,
    depth: int = Query(default=1, ge=1, le=4),
    db: AsyncSession = Depends(get_db),
) -> TableNeighborsResponse:
    engine = RelationshipGraphEngine(db)
    try:
        snapshot = await engine.get_neighbors(table_id, depth=depth)
        payload = asdict(snapshot)
        payload["neighbors"] = _map_nodes(snapshot.neighbors)
        payload["edges"] = _map_edges(snapshot.edges)
        return TableNeighborsResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Neighbor lookup failed for table_id=%s: %s", table_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load table neighbors",
        )


@router.get(
    "/relationships/join-paths/{table_a}/{table_b}",
    response_model=JoinPathsResponse,
    summary="Get join path(s) between two tables",
)
@router.get(
    "/join-paths/{table_a}/{table_b}",
    response_model=JoinPathsResponse,
    include_in_schema=False,
)
async def get_join_paths(
    table_a: int,
    table_b: int,
    max_paths: int = Query(default=5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> JoinPathsResponse:
    engine = RelationshipGraphEngine(db)
    try:
        snapshot = await engine.get_join_paths(table_a, table_b, max_paths=max_paths)
        payload = asdict(snapshot)
        payload["paths"] = _map_paths(snapshot.paths)
        return JoinPathsResponse.model_validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Join path lookup failed for table_a=%s table_b=%s: %s",
            table_a,
            table_b,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load join paths",
        )


@router.get(
    "/relationships/graph/{db_id}/export",
    response_model=GraphExportResponse,
    summary="Export the relationship graph as JSON, markdown, or a Mermaid diagram",
)
@router.get(
    "/relationship-graph/{db_id}/export",
    response_model=GraphExportResponse,
    include_in_schema=False,
)
async def export_relationship_graph(
    db_id: int,
    export_format: str = Query(default="json", pattern="^(json|markdown|diagram)$"),
    db: AsyncSession = Depends(get_db),
) -> GraphExportResponse:
    engine = RelationshipGraphEngine(db)
    try:
        snapshot = await engine.get_relationship_graph(db_id)
        bundle = engine.export_graph(snapshot, export_format=export_format)
        return GraphExportResponse(
            format=bundle.format,
            filename=bundle.filename,
            content=bundle.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Graph export failed for db_id=%s: %s", db_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export relationship graph",
        )
