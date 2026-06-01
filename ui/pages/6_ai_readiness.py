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
status = breakdown.get("readiness_status", "NOT_READY")
overall = int(scores.get("overall_score", 0))

status_color = {
    "READY": "green",
    "PARTIAL": "orange",
    "NOT_READY": "red",
    "STALE": "gray",
}.get(status, "gray")

st.markdown(f"### Status: :{status_color}[{status}]")
top = st.columns(6)
top[0].metric("Overall", f"{overall}%")
top[1].metric("Metadata", f"{int(scores.get('metadata_score', 0))}%")
top[2].metric("Semantic", f"{int(scores.get('semantic_score', 0))}%")
top[3].metric("Embeddings", f"{int(scores.get('embeddings_score', 0))}%")
top[4].metric("Relationships", f"{int(scores.get('relationship_score', 0))}%")
top[5].metric("Prompt", f"{int(scores.get('prompt_score', 0))}%")

st.progress(overall / 100.0, text=f"Overall Readiness: {overall}%")

st.markdown("### Stage Progress")
stage_cols = st.columns(5)
stage_scores = [
    ("Metadata", int(scores.get("metadata_score", 0))),
    ("Semantic", int(scores.get("semantic_score", 0))),
    ("Embeddings", int(scores.get("embeddings_score", 0))),
    ("Relationships", int(scores.get("relationship_score", 0))),
    ("Prompt", int(scores.get("prompt_score", 0))),
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
            st.warning(item)
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
detail_cols[0].metric("Schemas", details.get("schemas", 0))
detail_cols[1].metric("Tables/Entities", details.get("tables", 0))
detail_cols[2].metric("Columns/Fields", details.get("columns", 0))
detail_cols[3].metric("Relationships", details.get("relationships", 0))

detail_cols2 = st.columns(3)
detail_cols2[0].metric("Semantic Coverage", details.get("semantic_tables", 0))
detail_cols2[1].metric("Embedding Coverage", details.get("embedding_completed", 0))
detail_cols2[2].metric("Prompt Coverage", details.get("tables_with_prompt_context", 0))
