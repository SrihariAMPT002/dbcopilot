"""Build normalized knowledge documents for embeddings."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.embedding_document import EmbeddingDocument
from app.models.metadata import ConnectedDatabase, DatabaseSchema, DatabaseTable, GovernancePackage, RelationshipPackage, SemanticPackage
from app.models.prompt_package import PromptPackage
from app.utils import now_utc


class EmbeddingDocumentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())

    async def _fetch_database(self, database_id: int) -> ConnectedDatabase:
        database = await self.db.get(ConnectedDatabase, database_id)
        if not database:
            raise ValueError(f"Database {database_id} not found")
        return database

    async def _fetch_tables(self, database_id: int) -> list[DatabaseTable]:
        result = await self.db.execute(
            select(DatabaseTable).join(DatabaseSchema).where(DatabaseSchema.connected_db_id == database_id)
        )
        return list(result.scalars().all())

    async def _fetch_packages(self, database_id: int) -> dict[str, list[Any]]:
        governance = (await self.db.execute(select(GovernancePackage).where(GovernancePackage.database_id == database_id))).scalars().all()
        semantic = (await self.db.execute(select(SemanticPackage).where(SemanticPackage.database_id == database_id))).scalars().all()
        relationship = (await self.db.execute(select(RelationshipPackage).where(RelationshipPackage.database_id == database_id))).scalars().all()
        prompts = (await self.db.execute(select(PromptPackage).where(PromptPackage.database_id == database_id))).scalars().all()
        return {
            "governance": list(governance),
            "semantic": list(semantic),
            "relationship": list(relationship),
            "prompt": list(prompts),
        }

    async def _package_signature(self, database_id: int, table_id: int | None = None) -> dict[str, str | None]:
        def _iso(value: datetime | None) -> str | None:
            return value.isoformat() if value else None

        governance_stmt = select(func.max(GovernancePackage.updated_at)).where(GovernancePackage.database_id == database_id)
        if table_id is not None:
            governance_stmt = governance_stmt.where(GovernancePackage.table_id == table_id)
        governance = await self.db.execute(governance_stmt)
        semantic = await self.db.execute(select(func.max(SemanticPackage.updated_at)).where(SemanticPackage.database_id == database_id))
        relationship = await self.db.execute(select(func.max(RelationshipPackage.updated_at)).where(RelationshipPackage.database_id == database_id))
        prompt = await self.db.execute(select(func.max(PromptPackage.updated_at)).where(PromptPackage.database_id == database_id))
        return {
            "governance": _iso(governance.scalar_one_or_none()),
            "semantic": _iso(semantic.scalar_one_or_none()),
            "relationship": _iso(relationship.scalar_one_or_none()),
            "prompt": _iso(prompt.scalar_one_or_none()),
        }

    async def _existing_documents_for_table(self, database_id: int, table: DatabaseTable) -> list[EmbeddingDocument]:
        result = await self.db.execute(
            select(EmbeddingDocument).where(EmbeddingDocument.database_id == database_id).order_by(EmbeddingDocument.created_at.desc())
        )
        rows = list(result.scalars().all())
        matched: list[EmbeddingDocument] = []
        for row in rows:
            try:
                metadata = json.loads(row.metadata_json or "{}")
            except Exception:
                metadata = {}
            if metadata.get("table_id") == table.id:
                matched.append(row)
                continue
            if metadata.get("schema_name") == table.schema.name and metadata.get("table_name") == table.name:
                matched.append(row)
        return matched

    @staticmethod
    def _doc_signature(metadata_json: str) -> dict[str, str | None]:
        try:
            payload = json.loads(metadata_json or "{}")
        except Exception:
            payload = {}
        signature = payload.get("package_signature")
        return signature if isinstance(signature, dict) else {}

    def _build_table_documents(
        self,
        database: ConnectedDatabase,
        table: DatabaseTable,
        packages: dict[str, list[Any]],
        package_signature: dict[str, str | None],
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        governance = next((p for p in packages["governance"] if getattr(p, "table_id", None) == table.id), None)
        relationship = packages["relationship"][0] if packages["relationship"] else None
        semantic = packages["semantic"][0] if packages["semantic"] else None

        table_lines = [
            f"Database: {database.display_name or database.name}",
            f"Schema: {table.schema.name}",
            f"Table: {table.name}",
            f"Type: {table.table_type.value}",
        ]
        if table.description:
            table_lines.append(f"Description: {table.description}")
        table_lines.append("Columns:")
        for column in sorted(table.columns or [], key=lambda item: item.ordinal_position or 0):
            flags = []
            if column.is_primary_key:
                flags.append("PK")
            if column.is_foreign_key:
                flags.append("FK")
            if not column.is_nullable:
                flags.append("NN")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            table_lines.append(f"- {column.name}: {column.data_type}{suffix}")

        if governance:
            table_lines.extend(
                [
                    f"Governance summary: {getattr(governance, 'table_summary', '') or ''}",
                    f"Business purpose: {getattr(governance, 'business_purpose', '') or ''}",
                ]
            )
        if semantic:
            table_lines.extend(
                [
                    f"Semantic domain: {getattr(semantic, 'business_domain', '') or ''}",
                    f"Semantic summary: {getattr(semantic, 'semantic_summary', '') or ''}",
                ]
            )
        if relationship:
            table_lines.extend(
                [
                    f"Relationship summary: {getattr(relationship, 'cluster_summary', '') or ''}",
                    f"Entity graph: {getattr(relationship, 'entity_graph', [])}",
                ]
            )

        documents.append(
            {
                "table_id": table.id,
                "document_type": "table_knowledge",
                "source_package": "metadata+governance+semantic+relationship+prompt",
                "content": self._normalize("\n".join(table_lines)),
                "metadata_json": self._json(
                {
                    "database_id": database.id,
                    "table_id": table.id,
                    "schema_name": table.schema.name,
                    "table_name": table.name,
                    "generated_at": now_utc().isoformat(),
                    "package_signature": package_signature,
                }
                ),
            }
        )

        if packages["prompt"]:
            for prompt in packages["prompt"]:
                documents.append(
                    {
                        "table_id": table.id,
                        "document_type": "prompt_knowledge",
                        "source_package": "prompt",
                        "content": self._normalize(getattr(prompt, "generated_prompt", "")),
                        "metadata_json": self._json(
                        {
                            "database_id": database.id,
                            "table_id": table.id,
                            "artifact_type": getattr(prompt, "artifact_type", ""),
                            "template_id": getattr(prompt, "template_id", None),
                            "package_signature": package_signature,
                        }
                        ),
                    }
                )

        return documents

    async def build_documents(self, database_id: int) -> list[EmbeddingDocument]:
        database = await self._fetch_database(database_id)
        tables = await self._fetch_tables(database_id)
        packages = await self._fetch_packages(database_id)
        package_signature = await self._package_signature(database_id)

        created: list[EmbeddingDocument] = []
        for table in tables:
            existing = await self._existing_documents_for_table(database_id, table)
            if existing:
                existing_signature = self._doc_signature(existing[0].metadata_json)
                if existing_signature == package_signature:
                    created.extend(existing)
                    continue
                for row in existing:
                    await self.db.delete(row)
            for payload in self._build_table_documents(database, table, packages, package_signature):
                row = EmbeddingDocument(
                    database_id=database.id,
                    document_type=payload["document_type"],
                    source_package=payload["source_package"],
                    content=payload["content"],
                    metadata_json=payload["metadata_json"],
                    embedding_model=settings.azure_openai_embedding_deployment,
                    vector_id=None,
                    trace_id=None,
                )
                self.db.add(row)
                created.append(row)

        await self.db.flush()
        return created

    async def build_documents_for_table(self, database_id: int, table_id: int) -> list[EmbeddingDocument]:
        database = await self._fetch_database(database_id)
        packages = await self._fetch_packages(database_id)
        package_signature = await self._package_signature(database_id, table_id)
        result = await self.db.execute(
            select(DatabaseTable).join(DatabaseSchema).where(
                DatabaseSchema.connected_db_id == database_id,
                DatabaseTable.id == table_id,
            )
        )
        table = result.scalars().first()
        if not table:
            raise ValueError(f"Table {table_id} not found")
        created: list[EmbeddingDocument] = []
        existing = await self._existing_documents_for_table(database_id, table)
        if existing:
            existing_signature = self._doc_signature(existing[0].metadata_json)
            if existing_signature == package_signature:
                return existing
            for row in existing:
                await self.db.delete(row)
        for payload in self._build_table_documents(database, table, packages, package_signature):
            row = EmbeddingDocument(
                database_id=database.id,
                document_type=payload["document_type"],
                source_package=payload["source_package"],
                content=payload["content"],
                metadata_json=payload["metadata_json"],
                embedding_model=settings.azure_openai_embedding_deployment,
                vector_id=None,
                trace_id=None,
            )
            self.db.add(row)
            created.append(row)
        await self.db.flush()
        return created
