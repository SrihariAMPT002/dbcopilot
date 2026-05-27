"""
Unit tests for metadata normalization and flush safety.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.connectors.base import ColumnInfo
from app.models.metadata import DatabaseColumn
from app.services.sync_service import SyncService
from app.utils import (
    INT32_MAX,
    normalize_column_max_length,
    safe_flush,
)


def test_normalize_column_max_length_text_types_return_none():
    assert normalize_column_max_length("longtext", 4294967295) is None
    assert normalize_column_max_length("TEXT", 65535) is None


def test_normalize_column_max_length_preserves_varchar_length():
    assert normalize_column_max_length("varchar", 255) == 255
    assert normalize_column_max_length("character varying", 128) == 128
    assert normalize_column_max_length("varchar", INT32_MAX) == INT32_MAX


@pytest.mark.asyncio
async def test_safe_flush_rolls_back_on_failure():
    session = AsyncMock()
    session.flush = AsyncMock(side_effect=RuntimeError("boom"))
    session.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="boom"):
        await safe_flush(session)

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_columns_normalizes_external_metadata():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    service = SyncService(session)
    columns = [
        ColumnInfo(name="body", data_type="longtext", max_length=4294967295),
        ColumnInfo(name="title", data_type="varchar", max_length=255),
    ]

    count = await service._persist_columns(table_id=1, columns=columns)

    assert count == 2
    added_columns = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], DatabaseColumn)
    ]
    assert [col.max_length for col in added_columns] == [None, 255]
