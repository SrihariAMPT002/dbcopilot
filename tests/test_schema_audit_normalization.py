from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, String, Table, UniqueConstraint

from app.db.schema_audit import normalize_column, normalize_constraint, normalize_fk, normalize_index


def test_normalize_index_supports_inspector_dict():
    index = {"name": "ix_demo_name", "column_names": ["name"], "unique": True}
    assert normalize_index(index) == ("ix_demo_name", ("name",), True)


def test_normalize_index_supports_orm_index():
    metadata = MetaData()
    table = Table("demo", metadata, Column("id", Integer), Column("name", String))
    index = Index("ix_demo_name", table.c.name, unique=True)
    assert normalize_index(index) == ("ix_demo_name", ("name",), True)


def test_normalize_column_supports_inspector_dict_and_orm_column():
    assert normalize_column({"name": "name", "type": String(50), "nullable": False}) == ("name", "String(50)", False)

    column = Column("age", Integer, nullable=True)
    assert normalize_column(column) == ("age", "Integer", True)


def test_normalize_fk_supports_dict_and_orm_foreign_key():
    fk_dict = {
        "name": "fk_demo_parent",
        "constrained_columns": ["parent_id"],
        "referred_table": "parent",
        "referred_columns": ["id"],
    }
    assert normalize_fk(fk_dict) == ("fk_demo_parent", ("parent_id",), "parent", ("id",))

    metadata = MetaData()
    parent = Table("parent", metadata, Column("id", Integer, primary_key=True))
    child = Table("child", metadata, Column("parent_id", Integer, ForeignKey(parent.c.id)))
    fk = next(iter(child.c.parent_id.foreign_keys))
    assert normalize_fk(fk) == ("", ("parent_id",), "parent", ("id",))


def test_normalize_constraint_supports_mixed_objects():
    metadata = MetaData()
    table = Table(
        "demo",
        metadata,
        Column("id", Integer),
        Column("name", String),
        UniqueConstraint("name", name="uq_demo_name"),
    )
    constraint = next(c for c in table.constraints if getattr(c, "name", None) == "uq_demo_name")
    assert normalize_constraint(constraint) == ("uq_demo_name", ("name",))
    assert normalize_constraint({"name": "uq_demo_name", "column_names": ["name"]}) == ("uq_demo_name", ("name",))


def test_normalize_helpers_handle_missing_keys_without_crashing():
    assert normalize_index(SimpleNamespace()) == ("", tuple(), False)
    assert normalize_column(SimpleNamespace()) == ("", "Unknown", True)
    assert normalize_fk(SimpleNamespace()) == ("", tuple(), "", tuple())
    assert normalize_constraint(SimpleNamespace()) == ("", tuple())
