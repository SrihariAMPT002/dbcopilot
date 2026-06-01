"""
Schema Explorer page - database-agnostic metadata navigation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from components.api_client import (
    diagnose_connection,
    get_columns,
    get_connections,
    get_relationships,
    get_schemas,
    get_tables,
    mongodb_collections,
    mongodb_infer_schema,
    mongodb_relationships,
    mongodb_samples,
    mongodb_schema,
)
from components.sidebar import render_sidebar
from components.source_terms import badge_label, is_nosql, source_family, terminology


st.set_page_config(
    page_title="Schema Explorer",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .explorer-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 4px;
    }
    .col-badge {
        display: inline-block;
        padding: 1px 7px;
        border-radius: 8px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-left: 4px;
    }
    .pk-badge  { background: #fef3c7; color: #92400e; }
    .fk-badge  { background: #dbeafe; color: #1e40af; }
    .uq-badge  { background: #f3e8ff; color: #6b21a8; }
    .nn-badge  { background: #fee2e2; color: #991b1b; }
    .type-chip {
        background: #f1f5f9;
        color: #334155;
        border-radius: 6px;
        padding: 1px 8px;
        font-size: 0.78rem;
        font-family: monospace;
    }
    .table-card {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 12px;
        background: white;
    }
    .stats-pill {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 3px 12px;
        font-size: 0.8rem;
        color: #64748b;
        display: inline-block;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    .tree-line {
        color: #94a3b8;
        font-size: 0.9rem;
        margin-left: 8px;
    }
    .source-banner {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 12px 14px;
        background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
        margin-bottom: 14px;
    }
    .entity-card {
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px;
        background: white;
        margin-bottom: 12px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _match_text(value: str, needle: str) -> bool:
    return needle.lower() in (value or "").lower()


def _col_badges(col: dict) -> str:
    badges = []
    if col.get("is_primary_key"):
        badges.append("<span class='col-badge pk-badge'>PK</span>")
    if col.get("is_foreign_key"):
        badges.append("<span class='col-badge fk-badge'>FK</span>")
    if col.get("is_unique"):
        badges.append("<span class='col-badge uq-badge'>UQ</span>")
    if not col.get("is_nullable"):
        badges.append("<span class='col-badge nn-badge'>NN</span>")
    return " ".join(badges)


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_entity_name(db_type: str) -> Dict[str, str]:
    terms = terminology(db_type)
    return {
        "group_label": "Schema" if source_family(db_type) == "SQL" else "Database",
        "entity_label": terms["entity_label"],
        "field_label": terms["field_label"],
        "relationship_label": terms["relationship_label"],
    }


st.markdown("## Schema Explorer")
st.markdown("Browse database metadata with SQL and NoSQL-ready terminology.")
st.markdown("---")

ok, conns = get_connections()
if not ok or not conns:
    st.warning("No connected databases found. Connect one first.")
    st.stop()

connections = conns if isinstance(conns, list) else []
if not connections:
    st.info("No connections available.")
    st.stop()

source_filter = st.radio("Source Type Filter", options=["All Sources", "SQL", "NoSQL"], horizontal=True)
if source_filter == "SQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "SQL"]
elif source_filter == "NoSQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "NoSQL"]

if not connections:
    st.info(f"No {source_filter.lower()} connections found.")
    st.stop()

conn_map = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in connections}
selected_label = st.selectbox(
    "Select Database",
    options=list(conn_map.keys()),
    help="Choose a connected source to explore",
)
selected_conn = conn_map[selected_label]
db_id = selected_conn["id"]
db_type = selected_conn.get("db_type", "")
terms = _normalize_entity_name(db_type)
family = source_family(db_type)

status = selected_conn.get("status", "inactive")
status_icon = {"active": "🟢", "error": "🔴", "inactive": "⚪"}.get(status, "⚪")
st.markdown(
    f"""
    <div class="source-banner">
        <div class="explorer-header">{status_icon} {selected_conn.get('name')}</div>
        <div>
            <span class="stats-pill">{badge_label(db_type)}</span>
            <span class="stats-pill">{selected_conn.get('host')}:{selected_conn.get('port')}</span>
            <span class="stats-pill">{selected_conn.get('schema_count', 0)} units</span>
            <span class="stats-pill">{selected_conn.get('table_count', 0)} entities</span>
            <span class="stats-pill">{selected_conn.get('database_name')}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Diagnostic check ──────────────────────────────────────────────────────────
with st.expander("🔍 Diagnostic Info", expanded=False):
    ok_diag, diag_data = diagnose_connection(db_id)
    if ok_diag and isinstance(diag_data, dict):
        st.json(diag_data)
        
        # Show recommendation
        rec = diag_data.get("recommendation", "")
        if "Resync" in rec:
            st.warning(
                f"⚠️ **No schemas found yet.** "
                f"Click the **Resync** button on the Connected Sources page to discover schema metadata."
            )
        elif diag_data.get("schemas_count", 0) > 0 and diag_data.get("tables_count", 0) == 0:
            st.warning(
                f"⚠️ **Schema exists but no tables found.** "
                f"This might indicate an empty schema or a sync issue. Check the last sync status."
            )
    else:
        st.error(f"Diagnostic failed: {diag_data.get('error', 'Unknown error')}")

schema_search = st.text_input(
    f"Search {terms['group_label'].lower()}s, {terms['entity_label'].lower()}s, or {terms['field_label'].lower()}s",
    placeholder="Type a schema, table, collection, or field name...",
)
field_search = st.text_input(
    f"Search {terms['field_label'].lower()}s",
    placeholder="Optional field filter...",
)

if is_nosql(db_type):
    st.info(
        "NoSQL view enabled. Collections, sampled documents, inferred fields, and nested structures will be shown "
        "when the backend surfaces NoSQL metadata."
    )

ok2, schemas = get_schemas(db_id)
schemas = schemas if ok2 and isinstance(schemas, list) else []

if family == "SQL" and not schemas:
    st.info(
        "📌 **No schemas found yet.** "
        "\n\nTo discover and sync schema metadata:"
        "\n1. Go to **Connected Sources** page"
        "\n2. Find this database"
        "\n3. Click the **Resync** button"
        "\n\nThis will introspect your database and load all schemas, tables, and columns."
    )
    st.stop()

schema_hits = 0
entity_hits = 0
field_hits = 0

if family == "SQL":
    for schema in schemas:
        schema_id = schema["id"]
        schema_name = schema["name"]

        ok3, tables = get_tables(schema_id)
        if not ok3:
            st.error(
                f"**Failed to load entities for {schema_name}**"
                f"\n\nError: {tables.get('error', 'Unknown error')}"
                f"\n\n💡 Try refreshing the page or re-syncing the database from Connected Sources."
            )
            continue

        filtered_tables = []
        for table in _safe_list(tables):
            entity_name = table.get("name", "")
            if schema_search and not (
                _match_text(schema_name, schema_search)
                or _match_text(entity_name, schema_search)
            ):
                matched_fields = False
                if field_search:
                    ok_cols, columns_for_match = get_columns(table["id"])
                    if ok_cols and isinstance(columns_for_match, list):
                        matched_fields = any(_match_text(c.get("name", ""), field_search) for c in columns_for_match)
                if not matched_fields:
                    continue
            filtered_tables.append(table)

        if schema_search and not filtered_tables and not _match_text(schema_name, schema_search):
            continue

        schema_hits += 1

        with st.expander(f"**{schema_name}**  |  {len(filtered_tables)} {terms['entity_label'].lower()}(s)", expanded=(len(schemas) == 1)):
            st.markdown(f"<div class='tree-line'>{terms['group_label']} → {terms['entity_label']} → {terms['field_label']}</div>", unsafe_allow_html=True)

            if not filtered_tables:
                st.caption("No entities match the current search.")
                continue

            for table in filtered_tables:
                entity_id = table["id"]
                entity_name = table["name"]
                ttype = table.get("table_type", "table")
                row_count = table.get("row_count")
                col_count = table.get("column_count", 0)

                entity_hits += 1

                with st.container(border=True):
                    row_str = f" · ~{row_count:,} rows" if row_count is not None else ""
                    type_icon = {"table": "🗃", "view": "👁", "materialized_view": "🪞"}.get(ttype, "📄")
                    st.markdown(
                        f"{type_icon} **{entity_name}**  "
                        f"<span class='stats-pill'>{ttype}</span>"
                        f"<span class='stats-pill'>{col_count} {terms['field_label'].lower()}s</span>"
                        f"<span class='stats-pill'>row count{row_str}</span>",
                        unsafe_allow_html=True,
                    )

                    ok4, columns = get_columns(entity_id)
                    if not ok4:
                        st.error(
                            f"Failed to load {terms['field_label'].lower()}s: "
                            f"{columns.get('error', 'Unknown error')}"
                        )
                        continue

                    if not columns:
                        st.caption(f"No {terms['field_label'].lower()}s found.")
                        continue

                    if field_search:
                        columns = [c for c in columns if _match_text(c.get("name", ""), field_search)]

                    if not columns:
                        st.caption(f"No {terms['field_label'].lower()}s match the current filter.")
                        continue

                    field_hits += len(columns)

                    header = st.columns([3, 2, 1, 1, 1, 2])
                    header[0].markdown(f"**{terms['field_label']}**")
                    header[1].markdown("**Datatype**")
                    header[2].markdown("**Nullable**")
                    header[3].markdown("**PK/FK**")
                    header[4].markdown("**Indexes**")
                    header[5].markdown("**Row Count**")
                    st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

                    for col in columns:
                        row = st.columns([3, 2, 1, 1, 1, 2])
                        row[0].markdown(f"`{col['name']}` {_col_badges(col)}", unsafe_allow_html=True)
                        row[1].markdown(
                            f"<span class='type-chip'>{col.get('data_type', '?')}"
                            + (f"({col['max_length']})" if col.get("max_length") else "")
                            + "</span>",
                            unsafe_allow_html=True,
                        )
                        row[2].markdown("Yes" if col.get("is_nullable") else "No")
                        row[3].markdown("PK" if col.get("is_primary_key") else ("FK" if col.get("is_foreign_key") else ""))

                        extras = []
                        if col.get("is_unique"):
                            extras.append("UQ")
                        if col.get("is_indexed"):
                            extras.append("IDX")
                        row[4].markdown(" · ".join(extras) if extras else "—")
                        row[5].markdown(str(row_count) if row_count is not None else "Optional")

                    ok5, rels = get_relationships(entity_id)
                    if ok5 and rels:
                        st.markdown(f"**{terms['relationship_label']}s**")
                        for rel in rels:
                            ref_schema = f"{rel.get('referenced_schema')}." if rel.get("referenced_schema") else ""
                            st.markdown(
                                f"- `{rel.get('column_name')}` → **{ref_schema}{rel.get('referenced_table_name')}**"
                                f".`{rel.get('referenced_column_name')}`"
                            )

else:
    ok_collections, collections_payload = mongodb_collections(db_id)
    collection_rows = (
        collections_payload.get("collections", [])
        if ok_collections and isinstance(collections_payload, dict)
        else []
    )
    if schema_search:
        collection_rows = [
            item for item in collection_rows if _match_text(item.get("name", ""), schema_search)
        ]

    if collection_rows:
        schema_hits = 1
        entity_hits = len(collection_rows)
        st.markdown("### Collections")
        for item in collection_rows:
            collection_id = item.get("id")
            collection_name = item.get("name", "unknown")
            with st.container(border=True):
                st.markdown(
                    f"**{collection_name}** "
                    f"<span class='stats-pill'>Collection</span>"
                    f"<span class='stats-pill'>Confidence {float(item.get('schema_confidence', 0.0)):.2f}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"- Sampled documents: {item.get('sampled_documents', 0)} / approx {item.get('document_count', 'n/a')}"
                )

                controls = st.columns([1, 1, 1, 3])
                if controls[0].button("Infer Schema", key=f"infer_{collection_id}", use_container_width=True):
                    ok_infer, infer_payload = mongodb_infer_schema(collection_id, sample_size=100)
                    if ok_infer:
                        st.success(infer_payload.get("message", "Schema inference completed"))
                        st.rerun()
                    else:
                        st.error(infer_payload.get("error", "Schema inference failed"))
                if controls[1].button("View Fields", key=f"fields_{collection_id}", use_container_width=True):
                    st.session_state["nosql_selected_collection"] = collection_id
                if controls[2].button("View Samples", key=f"samples_{collection_id}", use_container_width=True):
                    st.session_state["nosql_selected_samples"] = collection_id

                ok_rel, rel_payload = mongodb_relationships(collection_id)
                rel_count = len(rel_payload.get("relationships", [])) if ok_rel and isinstance(rel_payload, dict) else 0
                st.caption(f"Inferred relationships: {rel_count}")

        selected_fields_collection = st.session_state.get("nosql_selected_collection")
        if selected_fields_collection:
            st.markdown("### Inferred Field Map")
            ok_schema, schema_payload = mongodb_schema(selected_fields_collection, limit=500, offset=0)
            if ok_schema and isinstance(schema_payload, dict):
                fields = schema_payload.get("fields", [])
                if field_search:
                    fields = [f for f in fields if _match_text(f.get("field_path", ""), field_search)]
                field_hits += len(fields)
                for field in fields:
                    depth_prefix = "  " * int(field.get("nested_depth", 0))
                    array_marker = "[] " if field.get("is_array") else ""
                    st.markdown(
                        f"- `{depth_prefix}{array_marker}{field.get('field_path')}` "
                        f"· {field.get('inferred_data_type')} "
                        f"· occ {float(field.get('occurrence_percentage', 0.0)):.1f}% "
                        f"· conf {float(field.get('schema_confidence', 0.0)):.2f}"
                    )
            else:
                st.error(schema_payload.get("error", "Failed to load inferred schema"))

        selected_samples_collection = st.session_state.get("nosql_selected_samples")
        if selected_samples_collection:
            st.markdown("### Document Samples")
            ok_samples, sample_payload = mongodb_samples(selected_samples_collection, limit=5, offset=0)
            if ok_samples and isinstance(sample_payload, dict):
                for sample in sample_payload.get("samples", []):
                    st.json(sample.get("sample_document", {}))
            else:
                st.error(sample_payload.get("error", "Failed to load samples"))
    else:
        st.info("No NoSQL collections surfaced yet. Sync first, then run Mongo schema inference.")

st.markdown("---")
st.caption(
    f"Search summary: {schema_hits} group(s), {entity_hits} {terms['entity_label'].lower()}(s), and {field_hits} field row(s) matched."
)
