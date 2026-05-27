"""
Semantic Intelligence page - core semantic layer for database entities.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import (
    call_api,
    get_connections,
    get_schemas,
    get_semantic_summary,
    get_tables,
    regenerate_semantics,
)
from components.sidebar import render_sidebar
from components.source_terms import source_family, terminology


st.set_page_config(
    page_title="Semantic Intelligence",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 16px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 8px 0;
    }
    .metric-label {
        font-size: 0.82rem;
        opacity: 0.92;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .summary-box {
        background: #f8fafc;
        border-left: 4px solid #667eea;
        padding: 12px 14px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .keyword-badge {
        display: inline-block;
        background: #dbeafe;
        color: #1e40af;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        margin: 4px 4px 0 0;
        font-weight: 600;
    }
    .question-item {
        background: #fef3c7;
        padding: 8px 12px;
        border-radius: 6px;
        margin: 6px 0;
        font-size: 0.9rem;
        border-left: 3px solid #f59e0b;
    }
    .usage-pill {
        display: inline-block;
        background: #ecfeff;
        color: #155e75;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.8rem;
        margin: 4px 4px 0 0;
        font-weight: 600;
    }
    .table-card {
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 14px;
        background: white;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
    }
    .table-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .table-meta {
        font-size: 0.83rem;
        color: #64748b;
        margin-bottom: 10px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _safe_list(value):
    return value if isinstance(value, list) else []


st.markdown("## Semantic Intelligence")
st.markdown("Most important module. Convert schemas and collections into business-aware semantic intelligence.")
st.markdown("---")

ok, conns = get_connections()
if not ok or not conns:
    st.warning("No connected databases found. Connect one first.")
    st.stop()

connections = conns if isinstance(conns, list) else []
if not connections:
    st.warning("No connections available.")
    st.stop()

source_filter = st.radio("Source Type Filter", options=["All Sources", "SQL", "NoSQL"], horizontal=True)
if source_filter == "SQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "SQL"]
elif source_filter == "NoSQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "NoSQL"]

if not connections:
    st.info(f"No {source_filter.lower()} connections found.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in connections if c.get("status") == "active"}
if not db_options:
    st.warning("No active databases. Activate a connection first.")
    st.stop()

selected_label = st.selectbox(
    "Select Database",
    options=list(db_options.keys()),
    help="Choose the source whose entities you want to enrich.",
)
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]
db_type = selected_conn.get("db_type", "")
terms = terminology(db_type)
family = source_family(db_type)

if st.button("Refresh Semantics", use_container_width=False):
    st.rerun()

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Database", selected_conn.get("name", "Unnamed"))
col_b.metric("Schemas", selected_conn.get("schema_count", 0))
col_c.metric("Entities", selected_conn.get("table_count", 0))
col_d.metric("Status", selected_conn.get("status", "inactive").title())

st.markdown("---")

top_left, top_right = st.columns([1, 1])
with top_left:
    if st.button("Generate Semantics", type="primary", use_container_width=True):
        with st.spinner("Generating semantics for all entities..."):
            ok_gen, result = regenerate_semantics(db_id)
        if ok_gen:
            st.success(f"Semantic generation completed for database {selected_conn.get('name', 'Unnamed')}.")
            if isinstance(result, dict):
                st.caption(f"Entities enriched: {result.get('tables_enriched', 0)}")
            st.rerun()
        else:
            st.error(result.get("error", "Semantic generation failed"))

with top_right:
    st.info(
        f"This module shows business summary, likely usage, important {terms['field_label'].lower()}s, "
        f"business keywords, analytics use cases, and possible questions for each {terms['entity_label'].lower()}."
    )

search_label = f"Search {terms['entity_label'].lower()}s"
schema_search = st.text_input(
    search_label,
    placeholder=f"Search by schema, {terms['entity_label'].lower()} name, or keyword...",
)

ok_schemas, schemas = get_schemas(db_id)
schemas = schemas if ok_schemas and isinstance(schemas, list) else []

if family == "SQL" and not schemas:
    st.info("No schemas found. Sync this database first.")
    st.stop()

if family == "NoSQL" and not schemas:
    st.info("No NoSQL semantic metadata has been surfaced yet. The UI is ready for collections and fields.")
    st.markdown("### NoSQL Visual States")
    a, b, c, d = st.columns(4)
    a.metric("Collections", "Pending")
    b.metric("Sampled Documents", "Pending")
    c.metric("Inferred Fields", "Pending")
    d.metric("Nested Structures", "Pending")
    st.markdown(
        """
        **NoSQL semantic view**

        - business summary
        - likely usage
        - analytics questions
        - inferred collection context
        """
    )
    st.stop()

entity_rows = []
for schema in schemas:
    ok_entities, entities = get_tables(schema["id"])
    if not ok_entities or not isinstance(entities, list):
        continue
    for entity in entities:
        label = f"{schema['name']}.{entity['name']}"
        if schema_search and schema_search.lower() not in label.lower():
            continue
        entity_rows.append(
            {
                "schema_id": schema["id"],
                "schema_name": schema["name"],
                "entity_id": entity["id"],
                "entity_name": entity["name"],
                "entity_type": entity.get("table_type", "table"),
                "row_count": entity.get("row_count"),
                "field_count": entity.get("column_count", 0),
            }
        )

if not entity_rows:
    st.info("No entities match the current search.")
    st.stop()

semantic_summary_count = 0
for row in entity_rows:
    ok_summary, summary = get_semantic_summary(row["entity_id"])
    if ok_summary:
        semantic_summary_count += 1
    row["summary_ok"] = ok_summary
    row["summary"] = summary

metric_cols = st.columns(4)
metric_cols[0].markdown(
    f"<div class='metric-card'><div class='metric-label'>Connected Entities</div><div class='metric-value'>{len(entity_rows)}</div></div>",
    unsafe_allow_html=True,
)
metric_cols[1].markdown(
    f"<div class='metric-card'><div class='metric-label'>Semantic Entities</div><div class='metric-value'>{semantic_summary_count}</div></div>",
    unsafe_allow_html=True,
)
metric_cols[2].markdown(
    f"<div class='metric-card'><div class='metric-label'>Business Coverage</div><div class='metric-value'>{round((semantic_summary_count / len(entity_rows)) * 100)}%</div></div>",
    unsafe_allow_html=True,
)
metric_cols[3].markdown(
    f"<div class='metric-card'><div class='metric-label'>Possible Questions</div><div class='metric-value'>{sum(len(_safe_list(r.get('summary', {}).get('possible_questions'))) for r in entity_rows if r.get('summary_ok'))}</div></div>",
    unsafe_allow_html=True,
)

st.markdown("---")
st.markdown("### Entity Semantics")

for row in entity_rows:
    summary = row.get("summary", {})
    label = f"{row['schema_name']}.{row['entity_name']}"
    with st.container(border=True):
        st.markdown(f"<div class='table-title'>{label}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='table-meta'>{row['entity_type']} · {row.get('field_count', 0)} {terms['field_label'].lower()}s · "
            f"{'~' if row.get('row_count') is not None else ''}{row.get('row_count', 'optional')} rows</div>",
            unsafe_allow_html=True,
        )

        action_cols = st.columns([1, 1, 4])
        with action_cols[0]:
            if st.button("Generate Semantics", key=f"generate_sem_{row['entity_id']}", use_container_width=True):
                with st.spinner(f"Generating semantics for {label}..."):
                    ok_tbl, result_tbl = call_api("POST", f"semantic/enrichment/table/{row['entity_id']}")
                if ok_tbl:
                    st.success(f"Generated semantics for {label}.")
                    st.rerun()
                else:
                    st.error(result_tbl.get("error", "Entity semantic generation failed"))
        with action_cols[1]:
            if st.button("Refresh Semantics", key=f"refresh_sem_{row['entity_id']}", use_container_width=True):
                st.rerun()
        with action_cols[2]:
            if row.get("summary_ok"):
                st.caption(f"Generated at: {summary.get('generated_at', 'n/a')}")
            else:
                st.caption("No semantic summary yet. Generate semantics to populate business intelligence.")

        if row.get("summary_ok"):
            st.markdown(
                f"""
                <div class="summary-box">
                    <strong>Business Summary:</strong><br>
                    {summary.get('business_summary', 'N/A')}
                </div>
                """,
                unsafe_allow_html=True,
            )

            if _safe_list(summary.get("likely_usage")):
                st.markdown("**Likely Usage**")
                st.markdown(
                    " ".join(f"<span class='usage-pill'>{item}</span>" for item in _safe_list(summary.get("likely_usage"))),
                    unsafe_allow_html=True,
                )

            if _safe_list(summary.get("likely_usage")):
                st.markdown("**Analytics Use Cases**")
                st.markdown("\n".join(f"- {item}" for item in _safe_list(summary.get("likely_usage"))))

            if _safe_list(summary.get("important_columns")):
                st.markdown("**Important Fields**")
                st.code(", ".join(summary["important_columns"]), language="text")

            if _safe_list(summary.get("business_keywords")):
                st.markdown("**Business Keywords**")
                st.markdown(
                    " ".join(f"<span class='keyword-badge'>{item}</span>" for item in summary["business_keywords"]),
                    unsafe_allow_html=True,
                )

            if _safe_list(summary.get("possible_questions")):
                st.markdown("**Possible Questions**")
                for question in summary["possible_questions"]:
                    st.markdown(f"<div class='question-item'>❓ {question}</div>", unsafe_allow_html=True)
        else:
            st.info(f"This {terms['entity_label'].lower()} has not been semantically enriched yet.")

st.markdown("---")
st.markdown(
    """
    **About Semantic Intelligence**

    This module converts raw metadata into business-aware semantic intelligence.
    The output is designed to help downstream retrieval, prompt building, and future query planning.
    """
)
