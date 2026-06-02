"""
Export APIs for AI schema intelligence artifacts.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models.metadata import (
    ConnectedDatabase,
    DatabaseSchema,
    DatabaseTable,
    EmbeddingStatus,
    SchemaEmbedding,
    SchemaSemantic,
)
from app.schema_engine.prompt_builder import PromptBuilder
from app.schema_engine.relationship_graph import RelationshipGraphEngine
router = APIRouter(prefix="/exports", tags=["Exports"])
logger = logging.getLogger(__name__)


def _fmt_format(value: str) -> str:
    return (value or "json").lower().strip()


async def _fetch_database(db: AsyncSession, db_id: int) -> ConnectedDatabase:
    result = await db.execute(
        select(ConnectedDatabase).where(ConnectedDatabase.id == db_id)
    )
    database = result.scalars().first()
    if not database:
        raise HTTPException(status_code=404, detail=f"Database {db_id} not found")
    return database


async def _fetch_tables(db: AsyncSession, db_id: int) -> List[DatabaseTable]:
    result = await db.execute(
        select(DatabaseTable)
        .join(DatabaseSchema)
        .options(
            selectinload(DatabaseTable.schema),
            selectinload(DatabaseTable.columns),
            selectinload(DatabaseTable.relationships_from),
        )
        .where(DatabaseSchema.connected_db_id == db_id)
        .order_by(DatabaseSchema.name, DatabaseTable.name)
    )
    return result.scalars().unique().all()


async def _fetch_semantics(db: AsyncSession, db_id: int) -> Dict[int, SchemaSemantic]:
    result = await db.execute(
        select(SchemaSemantic).where(SchemaSemantic.database_id == db_id)
    )
    return {item.table_id: item for item in result.scalars().all()}


async def _fetch_embeddings(db: AsyncSession, db_id: int) -> Dict[int, SchemaEmbedding]:
    result = await db.execute(
        select(SchemaEmbedding)
        .join(DatabaseTable)
        .join(DatabaseSchema)
        .where(DatabaseSchema.connected_db_id == db_id)
    )
    return {item.table_id: item for item in result.scalars().all()}


def _relationship_to_text(rel: Any) -> str:
    target_schema = f"{rel.referenced_schema}." if rel.referenced_schema else ""
    return f"{rel.column_name} -> {target_schema}{rel.referenced_table_name}.{rel.referenced_column_name}"


def _build_schema_package(
    database: ConnectedDatabase,
    tables: List[DatabaseTable],
    semantics: Dict[int, SchemaSemantic],
    embeddings: Dict[int, SchemaEmbedding],
) -> Dict[str, Any]:
    schema_package: Dict[str, Any] = {
        "database_id": database.id,
        "database_name": database.display_name or database.name,
        "db_type": database.db_type.value,
        "schemas": [],
    }
    grouped: Dict[str, Dict[str, Any]] = {}
    for table in tables:
        schema_bucket = grouped.setdefault(
            table.schema.name,
            {"schema_name": table.schema.name, "tables": []},
        )
        semantic = semantics.get(table.id)
        embedding = embeddings.get(table.id)
        schema_bucket["tables"].append(
            {
                "table_id": table.id,
                "table_name": table.name,
                "table_type": table.table_type.value,
                "row_count": table.row_count,
                "description": table.description,
                "columns": [
                    {
                        "name": column.name,
                        "data_type": column.data_type,
                        "is_nullable": column.is_nullable,
                        "is_primary_key": column.is_primary_key,
                        "is_foreign_key": column.is_foreign_key,
                        "is_unique": column.is_unique,
                        "is_indexed": column.is_indexed,
                        "description": column.description,
                    }
                    for column in table.columns
                ],
                "relationships": [_relationship_to_text(rel) for rel in table.relationships_from],
                "semantic": {
                    "business_summary": semantic.semantic_summary if semantic else None,
                    "likely_usage": semantic.likely_usage if semantic else [],
                    "important_columns": semantic.important_columns if semantic else [],
                    "business_keywords": semantic.business_keywords if semantic else [],
                    "possible_questions": semantic.possible_questions if semantic else [],
                },
                "embedding": {
                    "status": embedding.embedding_status.value if embedding else EmbeddingStatus.pending.value,
                    "model": embedding.embedding_model if embedding else None,
                    "vector_id": embedding.vector_id if embedding else None,
                    "generated_at": embedding.generated_at.isoformat() if embedding else None,
                },
            }
        )

    schema_package["schemas"] = list(grouped.values())
    return schema_package


def _build_prompt_package(database: ConnectedDatabase, prompt_context: str, semantics: Dict[int, SchemaSemantic]) -> Dict[str, Any]:
    return {
        "database_id": database.id,
        "database_name": database.display_name or database.name,
        "prompt_context": prompt_context,
        "semantic_table_count": len(semantics),
    }


def _build_embeddings_package(
    database: ConnectedDatabase,
    tables: List[DatabaseTable],
    embeddings: Dict[int, SchemaEmbedding],
) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    for table in tables:
        embedding = embeddings.get(table.id)
        records.append(
            {
                "table_id": table.id,
                "schema_name": table.schema.name,
                "table_name": table.name,
                "table_type": table.table_type.value,
                "embedding_status": embedding.embedding_status.value if embedding else EmbeddingStatus.pending.value,
                "embedding_model": embedding.embedding_model if embedding else None,
                "vector_id": embedding.vector_id if embedding else None,
                "generated_at": embedding.generated_at.isoformat() if embedding else None,
                "row_count": table.row_count,
                "description": table.description,
            }
        )

    return {
        "database_id": database.id,
        "database_name": database.display_name or database.name,
        "records": records,
        "indexed_tables": sum(1 for item in records if item["embedding_status"] == EmbeddingStatus.completed.value),
    }


def _build_graph_package(snapshot: Any) -> Dict[str, Any]:
    return {
        "database_id": snapshot.database_id,
        "database_name": snapshot.database_name,
        "generated_at": snapshot.generated_at.isoformat(),
        "metrics": asdict(snapshot.metrics) if snapshot.metrics else {},
        "nodes": [asdict(node) for node in snapshot.nodes],
        "edges": [
            {
                **asdict(edge),
                "join_columns": [asdict(item) for item in edge.join_columns],
            }
            for edge in snapshot.edges
        ],
        "cycles": snapshot.cycles,
    }


def _as_markdown_schema(package: Dict[str, Any]) -> str:
    lines = [
        f"# Schema Intelligence Export",
        "",
        f"- Database: {package['database_name']}",
        f"- Type: {package['db_type']}",
        "",
    ]
    for schema in package.get("schemas", []):
        lines.append(f"## Schema: {schema['schema_name']}")
        for table in schema.get("tables", []):
            lines.append(f"### {table['table_name']}")
            if table.get("semantic", {}).get("business_summary"):
                lines.append(f"- Summary: {table['semantic']['business_summary']}")
            if table.get("semantic", {}).get("likely_usage"):
                lines.append("- Likely usage:")
                for item in table["semantic"]["likely_usage"]:
                    lines.append(f"  - {item}")
            if table.get("semantic", {}).get("possible_questions"):
                lines.append("- Possible questions:")
                for item in table["semantic"]["possible_questions"]:
                    lines.append(f"  - {item}")
            lines.append("")
    return "\n".join(lines)


def _csv_from_schema(package: Dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "schema_name",
        "table_name",
        "table_type",
        "row_count",
        "business_summary",
        "likely_usage",
        "important_columns",
        "business_keywords",
        "possible_questions",
        "embedding_status",
        "embedding_model",
    ])
    for schema in package.get("schemas", []):
        for table in schema.get("tables", []):
            semantic = table.get("semantic", {})
            embedding = table.get("embedding", {})
            writer.writerow([
                schema["schema_name"],
                table["table_name"],
                table.get("table_type", ""),
                table.get("row_count", ""),
                semantic.get("business_summary", ""),
                " | ".join(semantic.get("likely_usage", [])),
                " | ".join(semantic.get("important_columns", [])),
                " | ".join(semantic.get("business_keywords", [])),
                " | ".join(semantic.get("possible_questions", [])),
                embedding.get("status", ""),
                embedding.get("model", ""),
            ])
    return buffer.getvalue()


def _csv_from_graph(package: Dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "source_schema",
        "source_table",
        "target_schema",
        "target_table",
        "relationship_type",
        "relationship_strength",
        "join_columns",
    ])
    for edge in package.get("edges", []):
        writer.writerow([
            edge.get("source_schema_name", ""),
            edge.get("source_table_name", ""),
            edge.get("target_schema_name", ""),
            edge.get("target_table_name", ""),
            edge.get("relationship_type", ""),
            edge.get("relationship_strength", ""),
            " | ".join(
                f"{item.get('source_column')}={item.get('target_column')}"
                for item in edge.get("join_columns", [])
            ),
        ])
    return buffer.getvalue()


def _as_markdown_embeddings(package: Dict[str, Any]) -> str:
    lines = [
        "# Embeddings Metadata Export",
        "",
        f"- Database: {package['database_name']}",
        f"- Indexed tables: {package.get('indexed_tables', 0)}",
        "",
    ]
    for record in package.get("records", []):
        lines.append(f"## {record['schema_name']}.{record['table_name']}")
        lines.append(f"- Status: {record.get('embedding_status', '')}")
        if record.get("embedding_model"):
            lines.append(f"- Model: {record['embedding_model']}")
        if record.get("vector_id"):
            lines.append(f"- Vector ID: {record['vector_id']}")
        if record.get("description"):
            lines.append(f"- Description: {record['description']}")
        lines.append("")
    return "\n".join(lines)


def _csv_from_embeddings(package: Dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "schema_name",
        "table_name",
        "table_type",
        "embedding_status",
        "embedding_model",
        "vector_id",
        "generated_at",
        "row_count",
        "description",
    ])
    for record in package.get("records", []):
        writer.writerow([
            record.get("schema_name", ""),
            record.get("table_name", ""),
            record.get("table_type", ""),
            record.get("embedding_status", ""),
            record.get("embedding_model", ""),
            record.get("vector_id", ""),
            record.get("generated_at", ""),
            record.get("row_count", ""),
            record.get("description", ""),
        ])
    return buffer.getvalue()


@router.get(
    "/schema/{db_id}",
    summary="Export schema intelligence package",
)
@router.get(
    "/export/schema/{db_id}",
    include_in_schema=False,
)
async def export_schema(
    db_id: int,
    format: str = Query(default="json", pattern="^(json|markdown|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    database = await _fetch_database(db, db_id)
    tables = await _fetch_tables(db, db_id)
    semantics = await _fetch_semantics(db, db_id)
    embeddings = await _fetch_embeddings(db, db_id)
    package = _build_schema_package(database, tables, semantics, embeddings)
    fmt = _fmt_format(format)

    if fmt == "json":
        content = json.dumps(package, default=str, indent=2)
        mime = "application/json"
        filename = f"schema-intelligence-{db_id}.json"
    elif fmt == "markdown":
        content = _as_markdown_schema(package)
        mime = "text/markdown"
        filename = f"schema-intelligence-{db_id}.md"
    else:
        content = _csv_from_schema(package)
        mime = "text/csv"
        filename = f"schema-intelligence-{db_id}.csv"

    return {"format": fmt, "filename": filename, "mime": mime, "content": content, "package": package}


@router.get(
    "/prompts/{db_id}",
    summary="Export prompt context package",
)
@router.get(
    "/export/prompts/{db_id}",
    include_in_schema=False,
)
async def export_prompts(
    db_id: int,
    format: str = Query(default="json", pattern="^(json|markdown|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    database = await _fetch_database(db, db_id)
    builder = PromptBuilder(db)
    context = await builder.build_semantic_context(db_id)
    semantics = await _fetch_semantics(db, db_id)
    package = _build_prompt_package(database, context, semantics)
    fmt = _fmt_format(format)

    if fmt == "json":
        content = json.dumps(package, default=str, indent=2)
        mime = "application/json"
        filename = f"prompt-context-{db_id}.json"
    elif fmt == "markdown":
        content = f"# Prompt Context\n\n{context}"
        mime = "text/markdown"
        filename = f"prompt-context-{db_id}.md"
    else:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["database_name", "token_estimate", "prompt_length", "prompt_context"])
        writer.writerow([
            package["database_name"],
            max(1, len(context.split()) * 1.33),
            len(context),
            context,
        ])
        content = buffer.getvalue()
        mime = "text/csv"
        filename = f"prompt-context-{db_id}.csv"

    return {"format": fmt, "filename": filename, "mime": mime, "content": content, "package": package}


@router.get(
    "/graph/{db_id}",
    summary="Export relationship graph package",
)
@router.get(
    "/export/graph/{db_id}",
    include_in_schema=False,
)
async def export_graph(
    db_id: int,
    format: str = Query(default="json", pattern="^(json|markdown|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    engine = RelationshipGraphEngine(db)
    snapshot = await engine.get_relationship_graph(db_id)
    package = _build_graph_package(snapshot)
    fmt = _fmt_format(format)

    if fmt == "json":
        content = json.dumps(package, default=str, indent=2)
        mime = "application/json"
        filename = f"relationship-graph-{db_id}.json"
    elif fmt == "markdown":
        export_bundle = engine.export_graph(snapshot, export_format="markdown")
        content = export_bundle.content
        mime = "text/markdown"
        filename = export_bundle.filename
    else:
        content = _csv_from_graph(package)
        mime = "text/csv"
        filename = f"relationship-graph-{db_id}.csv"

    return {"format": fmt, "filename": filename, "mime": mime, "content": content, "package": package}


@router.get(
    "/embeddings/{db_id}",
    summary="Export embeddings metadata package",
)
@router.get(
    "/export/embeddings/{db_id}",
    include_in_schema=False,
)
async def export_embeddings(
    db_id: int,
    format: str = Query(default="json", pattern="^(json|markdown|csv)$"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    database = await _fetch_database(db, db_id)
    tables = await _fetch_tables(db, db_id)
    embeddings = await _fetch_embeddings(db, db_id)
    package = _build_embeddings_package(database, tables, embeddings)
    fmt = _fmt_format(format)

    if fmt == "json":
        content = json.dumps(package, default=str, indent=2)
        mime = "application/json"
        filename = f"embeddings-metadata-{db_id}.json"
    elif fmt == "markdown":
        content = _as_markdown_embeddings(package)
        mime = "text/markdown"
        filename = f"embeddings-metadata-{db_id}.md"
    else:
        content = _csv_from_embeddings(package)
        mime = "text/csv"
        filename = f"embeddings-metadata-{db_id}.csv"

    return {"format": fmt, "filename": filename, "mime": mime, "content": content, "package": package}
