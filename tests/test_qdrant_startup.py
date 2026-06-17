from __future__ import annotations

from types import SimpleNamespace

from app.services.qdrant_service import QdrantService


def test_qdrant_service_creates_missing_required_collections():
    created = []

    class FakeQdrantClient:
        def get_collection(self, name):
            raise RuntimeError("missing")

        def create_collection(self, collection_name, vectors_config):
            created.append((collection_name, vectors_config.size))

    service = QdrantService.__new__(QdrantService)
    service.client = FakeQdrantClient()
    service._qmodels = SimpleNamespace(
        VectorParams=lambda size, distance: SimpleNamespace(size=size, distance=distance),
        Distance=SimpleNamespace(COSINE="COSINE"),
    )

    service.ensure_required_collections(vector_size=1536)

    assert len(created) == 10
    assert created[0][0] == "schema_tables"
    assert created[-1][0] == "memory_vectors"
