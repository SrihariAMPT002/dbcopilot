"""
Embeddings & Retrieval page.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import (
    generate_embeddings,
    get_connections,
    get_embedding_status,
    semantic_search,
)
from components.sidebar import render_sidebar
from components.source_terms import source_family, terminology


st.set_page_config(
    page_title="Embeddings & Retrieval",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .metric-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: white;
        padding: 16px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(15,23,42,0.14);
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 800;
        margin-top: 6px;
    }
    .metric-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        opacity: 0.8;
    }
    .result-card {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        background: white;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
    }
    .result-title {
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .result-meta {
        color: #64748b;
        font-size: 0.83rem;
        margin-bottom: 8px;
    }
    .badge {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 999px;
        background: #eff6ff;
        color: #1d4ed8;
        margin-right: 6px;
        margin-bottom: 4px;
        font-size: 0.78rem;
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _fmt_score(value: float) -> str:
    return f"{value:.3f}"


st.markdown("## Embeddings & Retrieval")
st.markdown("Very important AI engineering module. Convert semantic intelligence into vector-searchable schema intelligence.")
st.markdown("---")

ok, conns = get_connections()
if not ok or not conns:
    st.warning("No connected databases found. Connect one first.")
    st.stop()

connections = conns if isinstance(conns, list) else []
source_filter = st.radio("Source Type Filter", options=["All Sources", "SQL", "NoSQL"], horizontal=True)
if source_filter == "SQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "SQL"]
elif source_filter == "NoSQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "NoSQL"]

active_conns = [c for c in connections if c.get("status") == "active"]
if not active_conns:
    st.warning("No active databases found. Activate a connection first.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in active_conns}
selected_label = st.selectbox("Select Database", options=list(db_options.keys()))
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]
terms = terminology(selected_conn.get("db_type", ""))

status_ok, status_payload = get_embedding_status(db_id)

top_cols = st.columns(5)
top_cols[0].metric(f"Indexed {terms['entity_label']}s", status_payload.get("indexed_tables", 0) if status_ok else 0)
top_cols[1].metric("Embedding Health", "Healthy" if status_payload.get("embedding_health") else "Needs attention")
top_cols[2].metric("Qdrant Collections", len(status_payload.get("collections", [])) if status_ok else 0)
top_cols[3].metric("Retrieval Latency", f"{status_payload.get('latency_ms', 0):.0f} ms" if status_ok and status_payload.get("latency_ms") else "n/a")
top_cols[4].metric("Vector Count", status_payload.get("vectors_total", 0) if status_ok else 0)

st.markdown("---")

left, right = st.columns([2, 1])
with left:
    search_query = st.text_input(
        "Semantic Search Box",
        placeholder="customer revenue",
        help="Enter a business query to retrieve relevant tables, columns, and semantic matches.",
    )
with right:
    top_k = st.slider("Top K", min_value=1, max_value=10, value=5)

action_cols = st.columns([1, 1, 4])
with action_cols[0]:
    if st.button("Generate Embeddings", type="primary", use_container_width=True):
        with st.spinner("Generating embeddings for semantic schema intelligence..."):
            ok_gen, result_gen = generate_embeddings(db_id)
        if ok_gen:
            st.success(result_gen.get("message", "Embeddings generated successfully."))
            st.rerun()
        else:
            st.error(result_gen.get("error", "Embedding generation failed"))

with action_cols[1]:
    if st.button("Refresh Status", use_container_width=True):
        st.rerun()

with action_cols[2]:
    st.info(
        "This page indexes semantic summaries, relationships, entity descriptions, generated prompts, and business questions into Qdrant."
    )

if source_family(selected_conn.get("db_type", "")) == "NoSQL":
    st.info(
        f"NoSQL retrieval mode is UI-ready for {terms['entity_label'].lower()}s and inferred fields. "
        "Backend vector generation currently surfaces relational metadata."
    )

if status_ok:
    st.markdown("### Embedding Health")
    health_cols = st.columns(4)
    health_cols[0].metric("Indexed Tables", status_payload.get("indexed_tables", 0))
    health_cols[1].metric("Completed", status_payload.get("completed_tables", 0))
    health_cols[2].metric("Failed", status_payload.get("failed_tables", 0))
    health_cols[3].metric("Qdrant Health", "Healthy" if status_payload.get("qdrant_health") else "Unavailable")

    vector_counts = status_payload.get("vector_counts", {}) or {}
    if vector_counts:
        st.markdown("**Qdrant Collections**")
        collection_cols = st.columns(3)
        for idx, name in enumerate(("schema_tables", "schema_relationships", "schema_prompts")):
            with collection_cols[idx % 3]:
                st.markdown(
                    f"<div class='metric-card'><div class='metric-label'>{name}</div><div class='metric-value'>{vector_counts.get(name, 0)}</div></div>",
                    unsafe_allow_html=True,
                )

    collections = status_payload.get("collections", [])
    if collections:
        st.markdown("**Collection Details**")
        for item in collections:
            st.markdown(
                f"- `{item.get('collection_name')}` · {item.get('vectors', 0)} vectors · "
                f"{item.get('indexed_tables', 0)} indexed table(s)"
            )
else:
    st.warning(status_payload.get("error", "Embedding status unavailable"))

st.markdown("---")
st.markdown("### Semantic Search")

if search_query.strip():
    with st.spinner("Retrieving semantic matches..."):
        ok_search, search_payload = semantic_search(
            {"db_id": db_id, "query": search_query.strip(), "top_k": top_k}
        )

    if ok_search:
        latency_ms = search_payload.get("latency_ms", 0.0)
        st.success(
            f"Found {search_payload.get('total_hits', 0)} matches in {_fmt_score(latency_ms)} ms"
        )

        search_stats = st.columns(4)
        search_stats[0].metric(f"{terms['entity_label']}s", len(search_payload.get("tables", [])))
        search_stats[1].metric("Relationships", len(search_payload.get("relationships", [])))
        search_stats[2].metric("Prompt Contexts", len(search_payload.get("prompt_contexts", [])))
        search_stats[3].metric("Retrieval Latency", f"{latency_ms:.1f} ms")

        def _render_section(title: str, items: list[dict], show_columns: bool = True) -> None:
            if not items:
                return
            st.markdown(f"### {title}")
            for item in items:
                with st.container(border=True):
                    st.markdown(
                        f"<div class='result-title'>{item.get('schema_name')}.{item.get('table_name')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<div class='result-meta'>score {_fmt_score(item.get('score', 0.0))} · "
                        f"{item.get('table_type', 'table')} · collection `{item.get('collection', '')}`</div>",
                        unsafe_allow_html=True,
                    )
                    if item.get("matched_text"):
                        st.write(item["matched_text"])
                    if show_columns and item.get("columns"):
                        st.markdown(f"**Relevant {terms['field_label']}s**")
                        st.markdown(" ".join(f"<span class='badge'>{col}</span>" for col in item["columns"]), unsafe_allow_html=True)
                    if item.get("relationships"):
                        st.markdown("**Relevant Relationships**")
                        for rel in item["relationships"][:5]:
                            st.markdown(f"- {rel}")
                    if item.get("prompt_context"):
                        st.markdown("**Semantic Match**")
                        st.caption(item["prompt_context"])

        _render_section("Relevant Tables", search_payload.get("tables", []))
        _render_section("Relevant Relationships", search_payload.get("relationships", []), show_columns=False)
        _render_section("Semantic Matches", search_payload.get("prompt_contexts", []))
    else:
        st.error(search_payload.get("error", "Semantic search failed"))
else:
    st.info(
        f"Enter a search phrase like `customer revenue` to retrieve relevant {terms['entity_label'].lower()}s, "
        f"{terms['field_label'].lower()}s, and semantic matches."
    )

st.markdown("---")
st.markdown(
    """
    **About Embeddings & Retrieval**

    This module turns semantic intelligence into vector-searchable schema intelligence.
    It powers semantic search across table summaries, relationships, prompts, and business questions.
    """
)
