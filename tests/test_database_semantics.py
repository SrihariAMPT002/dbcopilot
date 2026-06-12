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
    """Test compact semantic package input construction."""

    @pytest.mark.asyncio
    async def test_build_semantic_input(self, mock_db, sample_database, monkeypatch: pytest.MonkeyPatch):
        """Test building metadata + governance package input without raw schema dumps."""
        service = DatabaseSemanticService(mock_db)
        monkeypatch.setattr(
            "app.services.database_semantic_service.ColumnSemanticService.build_governance_package",
            AsyncMock(return_value={"database_id": 1, "table_count": 2, "packages": []}),
        )
        monkeypatch.setattr(
            "app.services.database_semantic_service.ColumnSemanticService.get_pii_map",
            AsyncMock(return_value={}),
        )

        payload = await service._build_semantic_input(sample_database)

        metadata = payload["metadata"]
        assert metadata["database_name"] == "Test Database"
        assert metadata["database_type"] == "postgresql"
        assert metadata["table_count"] == 2
        assert metadata["relationship_count"] == 1
        assert len(metadata["tables"]) == 2
        assert metadata["tables"][0]["table_name"] == "customers"
        assert metadata["tables"][0]["description"] == "Customer master data"
        assert "columns" not in metadata["tables"][0]
        assert payload["governance_package"]["table_count"] == 2

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
            "semantic_summary": "Customer order management system",
            "business_entities": ["customers", "orders", "products"],
            "business_capabilities": [
                "Customer lifetime value analysis",
                "Order fulfillment tracking",
            ],
            "business_processes": ["Order capture", "Fulfillment"],
            "business_glossary": [
                {"term": "SKU", "definition": "Stock keeping unit"},
            ],
            "analysis_notes": "Governance-informed semantic package.",
        })
        
        enrichment = service._parse_enrichment_response(1, response_text)
        
        assert enrichment.business_domain == "E-Commerce"
        assert len(enrichment.key_entities) == 3
        assert enrichment.business_processes == ["Order capture", "Fulfillment"]
        assert enrichment.confidence_score == 1.0
        assert enrichment.analysis_notes == "Governance-informed semantic package."

    def test_parse_enrichment_response_invalid_json(self):
        """Test parsing invalid JSON response."""
        service = DatabaseSemanticService(AsyncMock())
        
        response_text = "This is not valid JSON {invalid"
        
        with pytest.raises(ValueError, match="invalid_json"):
            service._parse_enrichment_response(1, response_text)


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
    async def test_build_prompt_variables_semantic_package(self, mock_db, sample_database):
        """Test metadata and governance package passed to the semantic prompt template."""
        service = DatabaseSemanticService(mock_db)
        semantic_input = {
            "metadata": {"table_count": 2, "tables": [{"table_name": "customers"}]},
            "governance_package": {"table_count": 2, "packages": []},
        }

        variables = service._build_prompt_variables(sample_database, semantic_input)

        assert "metadata" in variables
        assert "governance_package" in variables
        assert variables["metadata"]["tables"][0]["table_name"] == "customers"
        assert "schema_summary" not in variables
