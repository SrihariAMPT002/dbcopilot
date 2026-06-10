"""AI Readiness page."""

from __future__ import annotations

import json

import streamlit as st

from components.api_client import get_connections, get_readiness_breakdown, recompute_readiness
from components.sidebar import render_sidebar
from components.source_terms import source_family


st.set_page_config(page_title="AI Readiness", page_icon="", layout="wide")
render_sidebar()

st.markdown("## AI Readiness")
st.markdown("Executive view of AI readiness across metadata, semantics, relationships, governance, and KPI intelligence.")
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
    st.info("This page blends deterministic scores with an AI-written assessment and roadmap.")

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
        "governance_readiness_score": int(scores.get("governance_score", scores.get("embeddings_score", 0))),
        "kpi_readiness_score": int(scores.get("kpi_score", 0)),
        "overall_score": int(scores.get("overall_score", 0)),
    }
status = breakdown.get("readiness_status", "NOT_READY")
overall = int(category_scores.get("overall_score", scores.get("overall_score", 0)))
ai_summary = breakdown.get("ai_summary") or "No AI assessment has been generated yet."
ai_recommendations = breakdown.get("ai_recommendations", [])
ai_risks = breakdown.get("ai_risks", [])
ai_roadmap = breakdown.get("ai_roadmap", [])
ai_confidence = float(breakdown.get("ai_confidence", 0.0))

status_color = {
    "READY": "green",
    "PARTIAL": "orange",
    "NOT_READY": "red",
    "STALE": "gray",
}.get(status, "gray")

st.markdown(f"### Status: :{status_color}[{status}]")
score_cards = st.columns(6)
score_cards[0].metric("Overall", f"{overall}%")
score_cards[1].metric("Metadata", f"{int(category_scores.get('metadata_readiness_score', 0))}%")
score_cards[2].metric("Semantic", f"{int(category_scores.get('semantic_readiness_score', 0))}%")
score_cards[3].metric("Relationships", f"{int(category_scores.get('relationship_readiness_score', 0))}%")
score_cards[4].metric("KPI", f"{int(category_scores.get('kpi_readiness_score', 0))}%")
score_cards[5].metric("Confidence", f"{int(round(ai_confidence * 100))}%")

st.progress(overall / 100.0, text=f"Overall Readiness: {overall}%")

left, right = st.columns([1.2, 0.8])
with left:
    st.markdown("### Executive Assessment")
    st.success(ai_summary)
    st.markdown("#### Strengths")
    strengths = breakdown.get("details", {}).get("ai_context", {})
    st.write(
        [
            "Metadata, semantic, relationship, governance, and KPI signals are computed from current catalogued intelligence.",
            "The deterministic score remains the primary readiness baseline.",
            "AI assessment summarizes the state for leadership review.",
        ]
    )
with right:
    st.markdown("### Readiness Snapshot")
    st.metric("Governance", f"{int(category_scores.get('governance_readiness_score', 0))}%")
    st.metric("AI Context", f"{int(category_scores.get('ai_context_readiness_score', 0))}%")
    st.metric("KPI", f"{int(category_scores.get('kpi_readiness_score', 0))}%")
    st.metric("Status", status)

domain_rows = [
    ("Metadata", int(category_scores.get("metadata_readiness_score", 0))),
    ("Semantic", int(category_scores.get("semantic_readiness_score", 0))),
    ("Relationship", int(category_scores.get("relationship_readiness_score", 0))),
    ("AI Context", int(category_scores.get("ai_context_readiness_score", 0))),
    ("Governance", int(category_scores.get("governance_readiness_score", 0))),
    ("KPI", int(category_scores.get("kpi_readiness_score", 0))),
]

st.markdown("### Domain Score Table")
for name, value in domain_rows:
    cols = st.columns([2, 1, 4])
    cols[0].write(name)
    cols[1].write(f"{value}%")
    cols[2].progress(value / 100.0)

details = breakdown.get("details", {})
missing = breakdown.get("missing_stages", [])
hints = breakdown.get("remediation_hints", [])

panel_left, panel_right = st.columns([1, 1])
with panel_left:
    st.markdown("### AI Assessment Panel")
    st.markdown("**Risks**")
    if ai_risks:
        for item in ai_risks:
            st.warning(item)
    else:
        st.info("No major AI risks identified.")
    st.markdown("**Recommendations**")
    if ai_recommendations:
        for item in ai_recommendations:
            st.info(item)
    else:
        st.info("No AI recommendations returned.")
with panel_right:
    st.markdown("### Readiness Roadmap Panel")
    if ai_roadmap:
        for item in ai_roadmap:
            st.write(f"- {item}")
    else:
        st.info("No roadmap returned yet.")
    st.caption("Roadmap is guided by deterministic coverage gaps and AI-written prioritization.")

st.markdown("### Remediation Recommendations")
if hints:
    for hint in hints:
        st.info(hint)
else:
    st.success("No remediation required.")

st.markdown("### Missing Stages")
if missing:
    for item in missing:
        st.warning(item.replace("_", " ").title())
else:
    st.success("No missing stages detected.")

st.markdown("### Raw Snapshot Preview")
st.code(
    json.dumps(
        {
            "database_id": db_id,
            "overall_score": overall,
            "ai_confidence": ai_confidence,
            "status": status,
        },
        indent=2,
    ),
    language="json",
)
