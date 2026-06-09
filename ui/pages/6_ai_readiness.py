"""
AI Readiness page.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import (
    get_connections,
    get_readiness_breakdown,
    recompute_readiness,
)
from components.sidebar import render_sidebar
from components.source_terms import source_family


st.set_page_config(
    page_title="AI Readiness",
    page_icon="",
    layout="wide",
)

render_sidebar()

st.markdown("## AI Readiness")
st.markdown("Deterministic orchestration intelligence for AI schema infrastructure.")
st.markdown("---")

ok, conns = get_connections()
if not ok or not isinstance(conns, list) or not conns:
    st.warning("No connected databases found. Connect one first.")
    st.stop()

connections = [c for c in conns if c.get("status") == "active"]
if not connections:
    st.warning("No active databases found. Activate a connection first.")
    st.stop()

source_filter = st.radio("Source Type Filter", options=["All Sources", "SQL", "NoSQL"], horizontal=True)
if source_filter == "SQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "SQL"]
elif source_filter == "NoSQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "NoSQL"]

if not connections:
    st.warning("No databases match the selected filter.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in connections}
selected_label = st.selectbox("Select Database", list(db_options.keys()))
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]

action_cols = st.columns([1, 4])
with action_cols[0]:
    if st.button("Recompute", type="primary", use_container_width=True):
        with st.spinner("Recomputing readiness snapshot..."):
            ok_recompute, payload = recompute_readiness(db_id)
        if ok_recompute:
            st.success("Readiness snapshot recomputed.")
            st.rerun()
        st.error(payload.get("error", "Readiness recompute failed"))
with action_cols[1]:
    st.info("Readiness checks metadata, semantics, embeddings, relationships, and prompt context.")

ok_breakdown, breakdown = get_readiness_breakdown(db_id)
if not ok_breakdown:
    st.error(breakdown.get("error", "Readiness data unavailable"))
    st.stop()

scores = breakdown.get("scores", {})
category_scores = breakdown.get("category_scores", {})
if not category_scores:
    category_scores = {
        "metadata_readiness_score": int(scores.get("metadata_score", 0)),
        "semantic_readiness_score": int(scores.get("semantic_score", 0)),
        "relationship_readiness_score": int(scores.get("relationship_score", 0)),
        "ai_context_readiness_score": int(scores.get("prompt_score", 0)),
        "governance_readiness_score": int(scores.get("embeddings_score", 0)),
        "overall_score": int(scores.get("overall_score", 0)),
    }
status = breakdown.get("readiness_status", "NOT_READY")
overall = int(category_scores.get("overall_score", scores.get("overall_score", 0)))

status_color = {
    "READY": "green",
    "PARTIAL": "orange",
    "NOT_READY": "red",
    "STALE": "gray",
}.get(status, "gray")

st.markdown(f"### Status: :{status_color}[{status}]")
top = st.columns(6)
top[0].metric("Overall", f"{overall}%")
top[1].metric("Metadata", f"{int(category_scores.get('metadata_readiness_score', 0))}%")
top[2].metric("Semantic", f"{int(category_scores.get('semantic_readiness_score', 0))}%")
top[3].metric("Relationship", f"{int(category_scores.get('relationship_readiness_score', 0))}%")
top[4].metric("AI Context", f"{int(category_scores.get('ai_context_readiness_score', 0))}%")
top[5].metric("Governance", f"{int(category_scores.get('governance_readiness_score', 0))}%")

st.progress(overall / 100.0, text=f"Overall Readiness: {overall}%")

st.markdown("### Stage Progress")
stage_cols = st.columns(5)
stage_scores = [
    ("Metadata", int(category_scores.get("metadata_readiness_score", 0))),
    ("Semantic", int(category_scores.get("semantic_readiness_score", 0))),
    ("Relationship", int(category_scores.get("relationship_readiness_score", 0))),
    ("AI Context", int(category_scores.get("ai_context_readiness_score", 0))),
    ("Governance", int(category_scores.get("governance_readiness_score", 0))),
]
for idx, (name, value) in enumerate(stage_scores):
    with stage_cols[idx]:
        st.markdown(f"**{name}**")
        st.progress(value / 100.0)
        st.caption(f"{value}%")

missing = breakdown.get("missing_stages", [])
hints = breakdown.get("remediation_hints", [])
details = breakdown.get("details", {})

st.markdown("---")
left, right = st.columns([1, 1])
with left:
    st.markdown("### Missing Stages")
    if missing:
        for item in missing:
            st.warning(item.replace("_", " ").title())
    else:
        st.success("No missing stages detected.")

with right:
    st.markdown("### Remediation Actions")
    if hints:
        for hint in hints:
            st.info(hint)
    else:
        st.success("No remediation required.")

st.markdown("### Pipeline Coverage Details")
detail_cols = st.columns(4)
metadata_details = details.get("metadata", {})
semantic_details = details.get("semantic", {})
relationship_details = details.get("relationships", {})
ai_context_details = details.get("ai_context", {})
governance_details = details.get("governance", {})
embedding_details = details.get("embeddings", {})

detail_cols[0].metric("Schemas", metadata_details.get("schemas", 0))
detail_cols[1].metric("Tables/Entities", metadata_details.get("tables", 0))
detail_cols[2].metric("Columns/Fields", metadata_details.get("columns", 0))
detail_cols[3].metric("Relationships", metadata_details.get("relationships", 0))

detail_cols2 = st.columns(3)
detail_cols2[0].metric("Schema Docs", metadata_details.get("schemas_with_description", 0))
detail_cols2[1].metric("Table Docs", metadata_details.get("tables_with_description", 0))
detail_cols2[2].metric("Column Docs", metadata_details.get("columns_with_description", 0))

st.markdown("### Coverage Signals")
signal_cols = st.columns(4)
signal_cols[0].metric("Semantic Tables", semantic_details.get("schema_semantics", 0))
signal_cols[1].metric("Graph Edges", relationship_details.get("graph_edges", 0))
signal_cols[2].metric("Prompt Artifacts", ai_context_details.get("prompt_artifacts_rendered", 0))
signal_cols[3].metric("Column Semantics", governance_details.get("column_semantics", 0))

st.markdown("### Governance & AI Context")
governance_cols = st.columns(4)
governance_cols[0].metric("PII Columns", governance_details.get("pii_columns", 0))
governance_cols[1].metric("PII Risk Tagged", governance_details.get("pii_risk_tagged_columns", 0))
governance_cols[2].metric("Prompt Context Len", ai_context_details.get("prompt_context_length", 0))
governance_cols[3].metric("Embedding Coverage", embedding_details.get("completed_tables", 0))

st.markdown("### Coverage Breakdown")
coverage_cols = st.columns(2)
with coverage_cols[0]:
    st.markdown("#### Metadata")
    st.json(metadata_details)
with coverage_cols[1]:
    st.markdown("#### Semantic / AI Context")
    st.json({
        "semantic": semantic_details,
        "ai_context": ai_context_details,
        "governance": governance_details,
    })
