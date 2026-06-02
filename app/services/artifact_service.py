"""
Artifact registry service for versioned AI context packages.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

# from app.api.routes import exports as exports_route
from app.models.artifact_manifest import ArtifactManifest, ArtifactType, ExportStatus
from app.models.metadata import ConnectedDatabase


class ArtifactService:
    """Create and track versioned semantic artifact exports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # /tmp is writable in containerized environments where app code volume is read-only.
        self.registry_root = Path("/tmp/artifacts_registry")

    async def list_artifacts(self, database_id: int) -> list[ArtifactManifest]:
        await self._ensure_database(database_id)
        result = await self.db.execute(
            select(ArtifactManifest)
            .where(ArtifactManifest.database_id == database_id)
            .order_by(desc(ArtifactManifest.generated_at))
        )
        return result.scalars().all()

    async def get_manifest(self, database_id: int) -> dict[str, Any]:
        records = await self.list_artifacts(database_id)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            grouped.setdefault(item.artifact_type.value, []).append(self._as_manifest_item(item))
        latest = {k: v[0] for k, v in grouped.items() if v}
        return {
            "database_id": database_id,
            "artifact_count": len(records),
            "latest": latest,
            "history": grouped,
        }

    async def export_artifacts(self, database_id: int) -> list[dict[str, Any]]:
        await self._ensure_database(database_id)
        self.registry_root.mkdir(parents=True, exist_ok=True)

        bundles = [
            (
                ArtifactType.semantic_summary,
                await exports_route.export_schema(database_id=db_id_or(database_id), format="json", db=self.db),
            ),
            (
                ArtifactType.embeddings,
                await exports_route.export_embeddings(database_id=db_id_or(database_id), format="json", db=self.db),
            ),
            (
                ArtifactType.relationship_graph,
                await exports_route.export_graph(database_id=db_id_or(database_id), format="json", db=self.db),
            ),
            (
                ArtifactType.prompt_context,
                await exports_route.export_prompts(database_id=db_id_or(database_id), format="markdown", db=self.db),
            ),
        ]

        created: list[dict[str, Any]] = []
        for artifact_type, payload in bundles:
            content = payload.get("content", "")
            schema_hash = self._schema_hash(payload.get("package") or content)
            version = await self._next_version(database_id, artifact_type)
            filename = f"db_{database_id}_{artifact_type.name}_v{version}{self._suffix_for_type(artifact_type)}"
            path = self.registry_root / filename

            manifest = ArtifactManifest(
                database_id=database_id,
                artifact_type=artifact_type,
                version=version,
                schema_hash=schema_hash,
                export_status=ExportStatus.running,
                artifact_path=str(path),
            )
            self.db.add(manifest)
            await self.db.flush()

            try:
                path.write_text(content, encoding="utf-8")
                manifest.export_status = ExportStatus.completed
                created.append(
                    {
                        "id": manifest.id,
                        "artifact_type": artifact_type.value,
                        "version": manifest.version,
                        "schema_hash": manifest.schema_hash,
                        "export_status": manifest.export_status.value,
                        "artifact_path": manifest.artifact_path,
                        "generated_at": manifest.generated_at,
                        "filename": path.name,
                        "mime": payload.get("mime", "text/plain"),
                        "content": content,
                    }
                )
            except Exception as exc:
                manifest.export_status = ExportStatus.failed
                created.append(
                    {
                        "id": manifest.id,
                        "artifact_type": artifact_type.value,
                        "version": manifest.version,
                        "schema_hash": manifest.schema_hash,
                        "export_status": manifest.export_status.value,
                        "artifact_path": manifest.artifact_path,
                        "generated_at": manifest.generated_at,
                        "error": str(exc),
                    }
                )
        await self.db.flush()
        return created

    async def record_artifact(
        self,
        database_id: int,
        artifact_type: ArtifactType,
        content: str,
        *,
        mime: str = "text/plain",
        extension: str | None = None,
        schema_hash_payload: Any | None = None,
    ) -> dict[str, Any]:
        """Persist an artifact manifest row and write its content to the registry root."""
        await self._ensure_database(database_id)
        self.registry_root.mkdir(parents=True, exist_ok=True)

        schema_hash = self._schema_hash(schema_hash_payload if schema_hash_payload is not None else content)
        version = await self._next_version(database_id, artifact_type)
        suffix = extension or self._suffix_for_type(artifact_type)
        filename = f"db_{database_id}_{artifact_type.name}_v{version}{suffix}"
        path = self.registry_root / filename

        manifest = ArtifactManifest(
            database_id=database_id,
            artifact_type=artifact_type,
            version=version,
            schema_hash=schema_hash,
            export_status=ExportStatus.running,
            artifact_path=str(path),
        )
        self.db.add(manifest)
        await self.db.flush()

        try:
            path.write_text(content, encoding="utf-8")
            manifest.export_status = ExportStatus.completed
        except Exception:
            manifest.export_status = ExportStatus.failed
            raise
        finally:
            await self.db.flush()

        return {
            "id": manifest.id,
            "artifact_type": artifact_type.value,
            "version": manifest.version,
            "schema_hash": manifest.schema_hash,
            "export_status": manifest.export_status.value,
            "artifact_path": manifest.artifact_path,
            "generated_at": manifest.generated_at,
            "filename": path.name,
            "mime": mime,
            "content": content,
        }

    @staticmethod
    def _schema_hash(payload: Any) -> str:
        raw = payload if isinstance(payload, str) else json.dumps(payload, default=str, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _next_version(self, database_id: int, artifact_type: ArtifactType) -> int:
        result = await self.db.execute(
            select(ArtifactManifest)
            .where(
                ArtifactManifest.database_id == database_id,
                ArtifactManifest.artifact_type == artifact_type,
            )
            .order_by(desc(ArtifactManifest.version))
            .limit(1)
        )
        latest = result.scalars().first()
        return 1 if latest is None else int(latest.version) + 1

    async def _ensure_database(self, database_id: int) -> None:
        result = await self.db.execute(
            select(ConnectedDatabase.id).where(ConnectedDatabase.id == database_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Database {database_id} not found")

    @staticmethod
    def _suffix_for_type(artifact_type: ArtifactType) -> str:
        if artifact_type in {
            ArtifactType.prompt_context,
            ArtifactType.database_context,
            ArtifactType.system_prompt,
            ArtifactType.rag_context,
            ArtifactType.text_to_sql_context,
        }:
            return ".md"
        if artifact_type == ArtifactType.agent_context:
            return ".json"
        return ".json"

    @staticmethod
    def _as_manifest_item(item: ArtifactManifest) -> dict[str, Any]:
        return {
            "id": item.id,
            "artifact_type": item.artifact_type.value,
            "version": item.version,
            "schema_hash": item.schema_hash,
            "export_status": item.export_status.value,
            "artifact_path": item.artifact_path,
            "generated_at": item.generated_at,
        }


def db_id_or(value: int) -> int:
    """Tiny helper to keep explicit casts in service call sites."""
    return int(value)
