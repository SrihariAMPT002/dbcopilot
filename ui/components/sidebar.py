"""Shared sidebar navigation for AI Schema Intelligence Platform."""

import streamlit as st


NAV_LINKS = [
    ("app.py", "Home"),
    ("pages/1_connect_database.py", "Connect Database"),
    ("pages/2_connected_sources.py", "Connected Sources"),
    ("pages/3_schema_explorer.py", "Schema Explorer"),
    ("pages/4_relationship_graph.py", "Relationship Graph"),
    ("pages/5_semantic_intelligence.py", "Semantic Intelligence"),
    ("pages/7_embeddings_retrieval.py", "Embeddings & Retrieval"),
    ("pages/8_prompt_studio.py", "Prompt Studio"),
    ("pages/6_ai_readiness.py", "AI Readiness"),
    ("pages/9_exports.py", "Exports"),
    ("pages/11_settings.py", "Settings"),
]


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## AI Schema Intelligence Platform")
        st.markdown("---")

        for page_path, label in NAV_LINKS:
            st.page_link(page_path, label=label)
