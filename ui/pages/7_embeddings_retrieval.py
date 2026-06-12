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
from components.job_utils import render_job_status
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


def _get_result_value(item: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", []):
            return value
    return default


def _normalize_search_results(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []

    results = payload.get("results")
    if isinstance(results, list):
        return results

    fallback_sections = []
    for section_name in ("tables", "relationships", "prompt_contexts"):
        section = payload.get(section_name)
        if isinstance(section, list):
            fallback_sections.extend(section)
    return fallback_sections


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

top_cols = st.columns(4)
top_cols[0].metric(f"Indexed {terms['entity_label']}s", status_payload.get("indexed_tables", 0) if status_ok else 0)
top_cols[1].metric("Embedding Health", "Healthy" if status_payload.get("embedding_health") else "Needs attention")
top_cols[2].metric("Qdrant Collections", len(status_payload.get("collections", [])) if status_ok else 0)
top_cols[3].metric("Vector Count", status_payload.get("vectors_total", 0) if status_ok else 0)

st.markdown("---")

top_k = st.slider("Top K", min_value=1, max_value=10, value=5)

action_cols = st.columns([1, 1, 4])
with action_cols[0]:
    if st.button("Generate Embeddings", type="primary", use_container_width=True):
        with st.spinner("Generating embeddings for semantic schema intelligence..."):
            ok_gen, result_gen = generate_embeddings(db_id)
        if ok_gen:
            status = str(result_gen.get("status", "")).upper()
            if status == "QUEUED":
                st.success(result_gen.get("message", "Embedding generation queued."))
                render_job_status(result_gen.get("job_id"), label="Embedding Job")
            else:
                st.success(result_gen.get("message", "Embeddings generated successfully."))
        else:
            st.error(result_gen.get("error", "Embedding generation failed"))

with action_cols[1]:
    if st.button("Refresh Status", use_container_width=True):
        st.session_state["embeddings_status_refresh"] = True

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

if "semantic_search_query" not in st.session_state:
    st.session_state.semantic_search_query = ""

search_collection = st.selectbox(
    "Search Collection",
    options=["all", "schema_tables", "schema_relationships", "schema_prompts"],
    index=0,
    help="Choose a single Qdrant collection or search across all of them.",
)

with st.form("semantic_search_form", clear_on_submit=False):
    search_query = st.text_input(
        "Semantic Search Query",
        placeholder="Enter a business query to search (e.g., call summary)...",
        value=st.session_state.semantic_search_query,
        help="Enter a business query to retrieve relevant tables, relationships, and prompt context.",
    )
    run_search = st.form_submit_button("Search", type="primary", use_container_width=True)

if run_search:
    st.session_state.semantic_search_query = search_query.strip()

if st.session_state.semantic_search_query.strip():
    with st.spinner("Retrieving semantic matches..."):
        ok_search, search_payload = semantic_search(
            {
                "db_id": db_id,
                "query": st.session_state.semantic_search_query.strip(),
                "top_k": top_k,
                "collection": search_collection,
            }
        )

    if ok_search:
        results = sorted(_normalize_search_results(search_payload), key=lambda x: float(x.get("score", 0.0)), reverse=True)
        total_results = search_payload.get("total_results", len(results))
        top_score = results[0].get("score", 0.0) if results else 0.0
        collection_hits = sorted({item.get("collection_name") or item.get("collection") or "" for item in results if item})

        st.success(f"Found {total_results} matches for `{st.session_state.semantic_search_query.strip()}`")

        search_stats = st.columns(4)
        search_stats[0].metric("Results", total_results)
        search_stats[1].metric("Top Score", _fmt_score(float(top_score)))
        search_stats[2].metric("Collections", len(collection_hits))
        search_stats[3].metric("Top K", top_k)

        if results:
            st.markdown("#### Search Results")
            for item in results:
                entity_name = f"{_get_result_value(item, 'schema_name')}.{_get_result_value(item, 'table_name')}"
                collection_name = _get_result_value(item, "collection_name", "collection", "_collection")
                matched_context = _get_result_value(item, "text", "matched_text", "semantic_summary")
                entity_type = _get_result_value(item, "table_type", default="table")
                columns = item.get("column_names") or item.get("columns") or []
                relationships = item.get("relationships") or []

                with st.container(border=True):
                    header_cols = st.columns([3, 1, 1, 1])
                    header_cols[0].markdown(f"**Entity Name:** `{entity_name}`")
                    header_cols[1].markdown(f"**Entity Type:** `{entity_type}`")
                    header_cols[2].markdown(f"**Similarity Score:** `{_fmt_score(float(item.get('score', 0.0)))}`")
                    header_cols[3].markdown(f"**Collection:** `{collection_name}`")

                    if matched_context:
                        st.markdown("**Matched Context**")
                        st.write(matched_context)

                    if columns:
                        st.markdown(f"**Relevant {terms['field_label']}s**")
                        st.markdown(
                            " ".join(
                                f"<span class='badge'>{col}</span>" for col in list(columns)[:12]
                            ),
                            unsafe_allow_html=True,
                        )

                    if relationships:
                        st.markdown("**Relevant Relationships**")
                        if isinstance(relationships, list):
                            for rel in relationships[:5]:
                                st.markdown(f"- {rel}")
                        else:
                            st.markdown(f"- {relationships}")

                    extra = item.get("extra") or {}
                    if extra:
                        with st.expander("Raw Hit Details", expanded=False):
                            st.json(extra)
        else:
            st.info("The search completed successfully, but returned no results.")
    else:
        st.error(search_payload.get("error", "Semantic search failed"))
else:
    st.info(
        "Enter a phrase into the semantic search field above to search the vector store."
    )

st.markdown("---")
st.markdown(
    """
    **About Embeddings & Retrieval**

    This module turns semantic intelligence into vector-searchable schema intelligence.
    It powers semantic search across table summaries, relationships, prompts, and business questions.
    """
)
