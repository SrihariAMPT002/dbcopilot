"""
Tests for database-level semantic intelligence.

Tests:
- DatabaseSemanticService metadata extraction
- Semantic generation with mock Azure OpenAI
- Confidence score calculation
- API endpoints
- Export functionality
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metadata import (
    ConnectedDatabase,
    DatabaseColumn,
    DatabaseRelationship,
    DatabaseSchema,
    DatabaseSemantic,
    DatabaseTable,
    DatabaseType,
    SemanticGenerationStatus,
    TableType,
)
from app.services.database_semantic_service import DatabaseSemanticService, DatabaseSemanticEnrichment
from app.utils import now_utc


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Create a mock AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_database():
    """Create a sample database with metadata."""
    db = ConnectedDatabase(
        id=1,
        name="test_db",
        display_name="Test Database",
        db_type=DatabaseType.postgresql,
        host="localhost",
        port=5432,
        database_name="testdb",
        username="testuser",
        encrypted_password="encrypted_pwd",
        ssl_enabled=False,
    )
    
    # Create schema
    schema = DatabaseSchema(
        id=1,
        connected_db_id=1,
        name="public",
        description="Public schema",
    )
    
    # Create tables
    customers_table = DatabaseTable(
        id=1,
        schema_id=1,
        name="customers",
        table_type=TableType.table,
        row_count=1000,
        description="Customer master data",
    )
    
    orders_table = DatabaseTable(
        id=2,
        schema_id=1,
        name="orders",
        table_type=TableType.table,
        row_count=50000,
        description="Order transactions",
    )
    
    # Create columns for customers
    customer_id_col = DatabaseColumn(
        id=1,
        table_id=1,
        name="customer_id",
        data_type="INTEGER",
        is_primary_key=True,
        is_nullable=False,
        description="Unique customer identifier",
    )
    
    customer_name_col = DatabaseColumn(
        id=2,
        table_id=1,
        name="customer_name",
        data_type="VARCHAR(255)",
        is_nullable=False,
    )
    
    # Create columns for orders
    order_id_col = DatabaseColumn(
        id=3,
        table_id=2,
        name="order_id",
        data_type="INTEGER",
        is_primary_key=True,
        is_nullable=False,
    )
    
    customer_id_fk_col = DatabaseColumn(
        id=4,
        table_id=2,
        name="customer_id",
        data_type="INTEGER",
        is_foreign_key=True,
        is_nullable=False,
    )
    
    amount_col = DatabaseColumn(
        id=5,
        table_id=2,
        name="amount",
        data_type="DECIMAL(10,2)",
        is_nullable=False,
    )
    
    # Create relationship
    relationship = DatabaseRelationship(
        id=1,
        table_id=2,
        column_name="customer_id",
        referenced_table_id=1,
        referenced_table_name="customers",
        referenced_column_name="customer_id",
    )
    
    # Wire up relationships
    schema.tables = [customers_table, orders_table]
    customers_table.schema = schema
    customers_table.columns = [customer_id_col, customer_name_col]
    customers_table.relationships_from = []
    
    orders_table.schema = schema
    orders_table.columns = [order_id_col, customer_id_fk_col, amount_col]
    orders_table.relationships_from = [relationship]
    
    db.schemas = [schema]
    
    return db


class _FakeSemanticResult:
    def __init__(self, obj):
        self._obj = obj

    def scalars(self):
        return self

    def first(self):
        return self._obj


class _ConcurrentSemanticSession:
    """Minimal async session double that simulates a duplicate insert race."""

    def __init__(self):
        self.store = {}
        self.pending = {}
        self.add_calls = 0
        self.flush_calls = 0
        self.rollback_calls = 0
        self.refresh_calls = 0
        self._execute_calls = 0
        self._barrier = asyncio.Event()

    async def execute(self, statement):
        self._execute_calls += 1
        if self._execute_calls < 2:
            await self._barrier.wait()
        else:
            self._barrier.set()
        return _FakeSemanticResult(self.store.get(1))

    def add(self, obj):
        self.add_calls += 1
        self.pending[obj.source_id] = obj

    async def flush(self):
        self.flush_calls += 1
        for source_id, obj in list(self.pending.items()):
            existing = self.store.get(source_id)
            if existing is not None and existing is not obj:
                raise IntegrityError("insert", {"source_id": source_id}, Exception("duplicate key"))
            self.store[source_id] = obj
            self.pending.pop(source_id, None)

    async def rollback(self):
        self.rollback_calls += 1
        self.pending.clear()

    async def refresh(self, obj):
        self.refresh_calls += 1

    async def delete(self, obj):
        self.store.pop(obj.source_id, None)


# ── DatabaseSemanticService Tests ─────────────────────────────────────────────

class TestDatabaseSemanticServiceMetadataAggregation:
    """Test metadata aggregation and summarization."""

    @pytest.mark.asyncio
    async def test_build_metadata_summary(self, mock_db, sample_database):
        """Test building compact metadata summary."""
        service = DatabaseSemanticService(mock_db)
        
        payload = await service._build_metadata_summary(sample_database)
        
        # Verify payload structure
        assert payload["database_name"] == "test_db"
        assert payload["database_type"] == "postgresql"
        assert len(payload["schemas"]) == 1
        assert payload["total_tables"] == 2
        assert payload["total_relationships"] == 1
        
        # Verify schema structure
        schema_info = payload["schemas"][0]
        assert schema_info["name"] == "public"
        assert schema_info["description"] == "Public schema"
        assert schema_info["table_count"] == 2
        assert len(schema_info["tables"]) == 2
        
        # Verify table structure
        table_info = schema_info["tables"][0]
        assert table_info["name"] == "customers"
        assert table_info["type"] == "table"
        assert table_info["description"] == "Customer master data"
        assert len(table_info["columns"]) == 2
        assert table_info["columns"][0]["name"] == "customer_id"
        assert table_info["columns"][0]["is_pk"] is True
        assert table_info["columns"][0]["description"] == "Unique customer identifier"
        assert "description" not in table_info["columns"][1]

    def test_analyze_naming_patterns_good_names(self, sample_database):
        """Test analyzing good naming patterns."""
        service = DatabaseSemanticService(AsyncMock())
        
        patterns = service._analyze_naming_patterns(sample_database)
        
        assert patterns["has_poor_naming"] is False
        assert patterns.get("poor_naming_ratio", 0) == 0

    def test_analyze_naming_patterns_poor_names(self):
        """Test analyzing poor naming patterns."""
        # Create database with poor names
        db = MagicMock()
        db.schemas = [
            MagicMock(
                tables=[
                    MagicMock(name="tbl_001"),
                    MagicMock(name="tbl_002"),
                    MagicMock(name="col_a"),
                    MagicMock(name="test_table"),
                    MagicMock(name="good_table"),
                ]
            )
        ]
        
        service = DatabaseSemanticService(AsyncMock())
        patterns = service._analyze_naming_patterns(db)
        
        assert patterns["has_poor_naming"] is True
        assert patterns["poor_naming_ratio"] >= 0.6

    def test_is_poor_name(self):
        """Test identification of poor names."""
        service = DatabaseSemanticService(AsyncMock())
        
        # Poor names
        assert service._is_poor_name("tbl_001")
        assert service._is_poor_name("col_a")
        assert service._is_poor_name("d_001")
        assert service._is_poor_name("tmp_data")
        
        # Good names
        assert not service._is_poor_name("customers")
        assert not service._is_poor_name("order_items")
        assert not service._is_poor_name("user_profile")

    def test_validate_payload_size(self):
        """Test payload size validation."""
        service = DatabaseSemanticService(AsyncMock())
        
        # Small payload
        small_payload = {"tables": [{"name": f"table_{i}"} for i in range(10)]}
        assert service._validate_payload_size(small_payload) is True
        
        # Large payload
        large_payload = {"tables": [{"name": f"table_{i}", "data": "x" * 10000} for i in range(100)]}
        assert service._validate_payload_size(large_payload) is False

    def test_build_schema_prompt_parts_includes_descriptions(self):
        """Test LLM schema summary includes catalog descriptions."""
        service = DatabaseSemanticService(AsyncMock())
        metadata = {
            "schemas": [
                {
                    "name": "public",
                    "description": "Main application schema",
                    "tables": [
                        {
                            "name": "customers",
                            "type": "table",
                            "row_count": 100,
                            "description": "Customer master data",
                            "columns": [
                                {
                                    "name": "customer_id",
                                    "type": "INTEGER",
                                    "description": "Unique customer identifier",
                                },
                                {"name": "customer_name", "type": "VARCHAR(255)"},
                            ],
                            "relationships": [],
                        }
                    ],
                }
            ]
        }

        schema_lines, _ = service._build_schema_prompt_parts(metadata)
        joined = "\n".join(schema_lines)

        assert "Schema description: Main application schema" in joined
        assert "Table description: Customer master data" in joined
        assert "customer_id(INTEGER) — Unique customer identifier" in joined
        assert "customer_name(VARCHAR(255))" in joined
        assert "customer_name(VARCHAR(255)) —" not in joined

    def test_sample_large_schema(self):
        """Test schema sampling for large databases."""
        service = DatabaseSemanticService(AsyncMock())
        
        # Create large payload
        payload = {
            "database_name": "test",
            "schemas": [
                {
                    "name": "public",
                    "tables": [{"name": f"table_{i}"} for i in range(100)],
                }
            ],
        }
        
        sampled = service._sample_large_schema(payload)
        
        # Verify sampling
        assert "_sampling_note" in sampled
        assert len(sampled["schemas"][0]["tables"]) <= 50  # MAX_ENTITIES_TO_SAMPLE


class TestDatabaseSemanticServiceConfidenceScoring:
    """Test confidence score calculation."""

    def test_confidence_no_penalty(self, sample_database):
        """Test confidence score with good schema."""
        service = DatabaseSemanticService(AsyncMock())
        
        enrichment = DatabaseSemanticEnrichment(
            source_id=1,
            business_domain="E-Commerce",
            business_summary="Customer and order management",
            key_entities=["customers", "orders"],
            business_glossary=[],
            suggested_use_cases=[],
            confidence_score=1.0,
        )
        
        confidence = service._calculate_confidence_score(sample_database, enrichment)
        
        # Good schema should have high confidence
        assert confidence >= 0.75

    def test_confidence_poor_naming_penalty(self):
        """Test confidence penalty for poor naming."""
        db = MagicMock()
        db.schemas = [
            MagicMock(
                tables=[
                    MagicMock(name="tbl_001", relationships_from=[]),
                    MagicMock(name="tbl_002", relationships_from=[]),
                    MagicMock(name="customers", relationships_from=[]),
                ]
            )
        ]
        
        service = DatabaseSemanticService(AsyncMock())
        enrichment = DatabaseSemanticEnrichment(
            source_id=1,
            business_domain="Unknown",
            business_summary="",
            key_entities=[],
            business_glossary=[],
            suggested_use_cases=[],
            confidence_score=1.0,
        )
        
        confidence = service._calculate_confidence_score(db, enrichment)
        
        # Should have penalty applied
        assert confidence < 1.0
        assert confidence > 0.5


class TestDatabaseSemanticServiceResponseParsing:
    """Test Azure OpenAI response parsing."""

    def test_parse_enrichment_response_valid_json(self):
        """Test parsing valid JSON response."""
        service = DatabaseSemanticService(AsyncMock())
        
        response_text = json.dumps({
            "business_domain": "E-Commerce",
            "business_summary": "Customer order management system",
            "key_entities": ["customers", "orders", "products"],
            "business_glossary": [
                {"term": "SKU", "definition": "Stock keeping unit"},
            ],
            "suggested_use_cases": [
                "Customer lifetime value analysis",
                "Order fulfillment tracking",
            ],
            "analysis_notes": "Schema was sampled; some tables omitted.",
        })
        
        enrichment = service._parse_enrichment_response(1, response_text, {})
        
        assert enrichment.business_domain == "E-Commerce"
        assert len(enrichment.key_entities) == 3
        assert enrichment.confidence_score == 1.0
        assert enrichment.analysis_notes == "Schema was sampled; some tables omitted."

    def test_parse_enrichment_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        service = DatabaseSemanticService(AsyncMock())
        
        response_text = "This is not valid JSON {invalid"
        
        enrichment = service._parse_enrichment_response(1, response_text, {})
        
        assert enrichment.business_domain == "Unknown"
        assert enrichment.confidence_score == 0.0
        assert enrichment.analysis_notes is None
        assert enrichment.raw_response == response_text


class TestDatabaseSemanticServiceDatabaseOperations:
    """Test database persistence operations."""

    @pytest.mark.asyncio
    async def test_save_enrichment_new_record(self, mock_db):
        """Test saving new enrichment record."""
        mock_db.execute.return_value.scalars.return_value.first.return_value = None
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        service = DatabaseSemanticService(mock_db)
        
        enrichment = DatabaseSemanticEnrichment(
            source_id=1,
            business_domain="E-Commerce",
            business_summary="Order management system",
            key_entities=["customers", "orders"],
            business_glossary=[],
            suggested_use_cases=["Customer analysis"],
            confidence_score=0.85,
            analysis_notes="Limited FK metadata detected.",
        )
        
        result = await service.save_enrichment(enrichment)
        
        # Verify record was created
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_enrichment_updates_existing_record(self, mock_db):
        """Test regeneration updates the existing row instead of inserting a new one."""
        existing = DatabaseSemantic(
            id=7,
            source_id=1,
            generation_status=SemanticGenerationStatus.completed,
        )
        existing.business_domain = "Legacy"
        existing.business_summary = "Old summary"
        existing.analysis_notes = "Old notes"
        existing.key_entities = ["old"]
        existing.business_glossary = [{"term": "old", "definition": "old"}]
        existing.suggested_use_cases = ["old use case"]
        existing.confidence_score = 0.25
        existing.raw_ai_response = '{"legacy": true}'
        existing.generated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        mock_db.execute.return_value.scalars.return_value.first.return_value = existing
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = DatabaseSemanticService(mock_db)

        enrichment = DatabaseSemanticEnrichment(
            source_id=1,
            business_domain="E-Commerce",
            business_summary="Order management system",
            key_entities=["customers", "orders"],
            business_glossary=[{"term": "SKU", "definition": "Stock keeping unit"}],
            suggested_use_cases=["Customer analysis"],
            confidence_score=0.85,
            analysis_notes="Regenerated with full metadata.",
            raw_response='{"business_domain":"E-Commerce"}',
        )

        result = await service.save_enrichment(enrichment)

        assert result is existing
        assert existing.business_domain == "E-Commerce"
        assert existing.business_summary == "Order management system"
        assert existing.analysis_notes == "Regenerated with full metadata."
        assert existing.key_entities == ["customers", "orders"]
        assert existing.business_glossary[0]["term"] == "SKU"
        assert existing.suggested_use_cases == ["Customer analysis"]
        assert existing.confidence_score == 0.85
        assert existing.generation_status == SemanticGenerationStatus.completed
        assert existing.generated_at == enrichment.generated_at
        mock_db.add.assert_not_called()
        mock_db.flush.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_semantic(self, mock_db):
        """Test fetching semantic record."""
        mock_semantic = MagicMock(spec=DatabaseSemantic)
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_semantic
        
        service = DatabaseSemanticService(mock_db)
        result = await service.get_semantic(1)
        
        assert result == mock_semantic

    @pytest.mark.asyncio
    async def test_delete_semantic(self, mock_db):
        """Test deleting semantic record."""
        mock_semantic = MagicMock(spec=DatabaseSemantic)
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_semantic
        mock_db.delete = MagicMock()
        mock_db.flush = AsyncMock()
        
        service = DatabaseSemanticService(mock_db)
        result = await service.delete_semantic(1)
        
        assert result is True
        mock_db.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_enrichment_concurrent_requests(self):
        """Test that concurrent generation attempts converge on one row."""
        session = _ConcurrentSemanticSession()
        service = DatabaseSemanticService(session)

        enrichment_a = DatabaseSemanticEnrichment(
            source_id=1,
            business_domain="E-Commerce",
            business_summary="Order management system",
            key_entities=["customers", "orders"],
            business_glossary=[],
            suggested_use_cases=["Customer analysis"],
            confidence_score=0.85,
            raw_response='{"request":"a"}',
        )
        enrichment_b = DatabaseSemanticEnrichment(
            source_id=1,
            business_domain="Finance",
            business_summary="Billing and invoicing",
            key_entities=["invoices"],
            business_glossary=[],
            suggested_use_cases=["Revenue tracking"],
            confidence_score=0.91,
            raw_response='{"request":"b"}',
        )

        result_a, result_b = await asyncio.gather(
            service.save_enrichment(enrichment_a),
            service.save_enrichment(enrichment_b),
        )

        assert result_a.source_id == 1
        assert result_b.source_id == 1
        assert len(session.store) == 1
        assert session.rollback_calls >= 1
        assert session.store[1].business_domain in {"E-Commerce", "Finance"}
        assert session.store[1].business_summary in {"Order management system", "Billing and invoicing"}
        assert session.store[1].key_entities in (["customers", "orders"], ["invoices"])
        assert session.store[1].generation_status == SemanticGenerationStatus.completed


# ── Prompt Building Tests ─────────────────────────────────────────────────────

class TestDatabaseSemanticServicePrompts:
    """Test prompt building for Azure OpenAI."""

    @pytest.mark.asyncio
    async def test_build_prompt_variables_schema_summary(self, mock_db, sample_database):
        """Test schema_summary passed to the semantic prompt template."""
        service = DatabaseSemanticService(mock_db)
        metadata = await service._build_metadata_summary(sample_database)

        variables = service._build_prompt_variables(sample_database, metadata)
        schema_summary = variables["schema_summary"]

        assert "customers" in schema_summary
        assert "Schema description: Public schema" in schema_summary
        assert "Table description: Customer master data" in schema_summary
        assert "customer_id(INTEGER) — Unique customer identifier" in schema_summary
