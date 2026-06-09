"""
Settings page for infrastructure and AI configuration visibility.

This page positions the product as an AI Schema Intelligence Platform, not a
database chatbot.
"""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

from components.api_client import get_connections, get_embedding_status, health_check
from components.sidebar import render_sidebar
from components.source_terms import source_family


st.set_page_config(
    page_title="Settings",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .hero {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%);
        color: white;
        border-radius: 20px;
        padding: 28px 30px;
        margin-bottom: 22px;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.22);
    }
    .hero h1 {
        margin: 0 0 8px 0;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        color: white;2
    }
    .hero p {
        margin: 0;
        max-width: 960px;
        color: rgba(226, 232, 240, 0.95);
        line-height: 1.6;
    }
    .status-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 18px 18px 16px 18px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
        margin-bottom: 14px;
    }
    .status-label {
        color: #64748b;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
    }
    .status-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: #0f172a;
    }
    .subtle {
        color: #64748b;
        font-size: 0.92rem;
    }
    .panel {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 18px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        margin-bottom: 16px;
    }
</style>
""",
    unsafe_allow_html=True,
)


render_sidebar()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _status_text(ok: bool) -> str:
    return "Healthy" if ok else "Unavailable"


st.markdown(
    """
<div class="hero">
  <h1>AI Schema Intelligence Platform</h1>
  <p>
    Infrastructure and AI configuration center for converting raw schemas into
    AI-understandable semantic intelligence. This platform is intentionally not
    a database chatbot.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

refresh_col, _ = st.columns([1, 5])
with refresh_col:
    if st.button("Refresh Status", use_container_width=True):
        st.rerun()

ok, health = health_check()
api_status = ok and health.get("status") == "healthy"
db_status = ok and health.get("db_healthy", False)
timestamp = health.get("timestamp", datetime.now().isoformat()) if ok else datetime.now().isoformat()

connections_ok, connections_payload = get_connections()
connections = connections_payload if connections_ok and isinstance(connections_payload, list) else []
active_connections = [conn for conn in connections if conn.get("status") == "active"]
selected_conn = active_connections[0] if active_connections else (connections[0] if connections else None)

embedding_status_payload = {}
embedding_ok = False
qdrant_ok = False
indexed_tables = 0
vector_total = 0
selected_db_id = None
if selected_conn:
    selected_db_id = selected_conn.get("id")
    ok_embedding, embedding_status_payload = get_embedding_status(selected_db_id)
    if ok_embedding:
        embedding_ok = bool(embedding_status_payload.get("embedding_health"))
        qdrant_ok = bool(embedding_status_payload.get("qdrant_health"))
        indexed_tables = int(embedding_status_payload.get("indexed_tables", 0))
        vector_total = int(embedding_status_payload.get("vectors_total", 0))

azure_configured = bool(os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_KEY"))
embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
llm_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
langsmith_enabled = _env_bool("LANGSMITH_TRACING", False)

st.markdown("### Platform Status")
cards = st.columns(6)
cards[0].metric("API Status", _status_text(api_status))
cards[1].metric("Metadata DB", _status_text(db_status))
cards[2].metric("Azure OpenAI", _status_text(azure_configured))
cards[3].metric("Qdrant Health", _status_text(qdrant_ok) if selected_conn else "No DB Selected")
cards[4].metric("Embeddings", _status_text(embedding_ok) if selected_conn else "No DB Selected")
cards[5].metric("LangSmith", "Enabled" if langsmith_enabled else "Disabled")

st.caption(f"Last checked: {timestamp}")

left, right = st.columns([1.25, 1])

with left:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("#### AI Configuration")
    ai_rows = [
        ("Azure OpenAI status", "Configured" if azure_configured else "Missing"),
        ("Embedding model", embedding_model),
        ("LLM deployment", llm_deployment),
        ("LangSmith tracing", "Enabled" if langsmith_enabled else "Disabled"),
        ("Core purpose", "AI Schema Intelligence Platform"),
    ]
    for label, value in ai_rows:
        st.markdown(f"- **{label}**: {value}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("#### What this platform does")
    st.markdown(
        """
        - Converts raw schemas into semantic intelligence
        - Indexes tables, relationships, and prompt contexts
        - Produces exportable AI-ready schema artifacts
        - Supports semantic retrieval and graph-aware schema reasoning
        """
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("#### Vector & Retrieval Health")
    if selected_conn and embedding_status_payload:
        st.metric("Indexed Tables", indexed_tables)
        st.metric("Vector Count", vector_total)
        st.metric(
            "Embedding Health",
            _status_text(embedding_ok),
        )
        st.metric(
            "Qdrant Health",
            _status_text(qdrant_ok),
        )
        st.markdown("**Collections**")
        for item in embedding_status_payload.get("collections", []):
            st.markdown(
                f"- `{item.get('collection_name')}`: {item.get('vectors', 0)} vectors"
            )
    else:
        st.info("Connect and sync a database to view embeddings and retrieval health.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("#### Connected Platform Context")
    if connections:
        for conn in connections[:5]:
            st.markdown(
                f"- **{conn.get('name', 'Unnamed')}** "
                f"`{conn.get('db_type', '').upper()}` "
                f"{conn.get('host', '')}:{conn.get('port', '')}"
            )
    else:
        st.info("No connected databases yet.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("### Infrastructure Notes")
notes = st.columns(3)
notes[0].metric("Embedding Model", embedding_model)
notes[1].metric("LLM Deployment", llm_deployment)
notes[2].metric("LangSmith", "Enabled" if langsmith_enabled else "Disabled")

st.markdown("### NoSQL Support Status")
nosql_sources = [c for c in connections if source_family(c.get("db_type", "")) == "NoSQL"]
nosql_cols = st.columns(3)
nosql_cols[0].metric("MongoDB Support", "Enabled")
nosql_cols[1].metric("NoSQL Sources", len(nosql_sources))
nosql_cols[2].metric("Inference Engine", "UI-ready / backend pending")

st.markdown(
    """
    - MongoDB sources are treated as NoSQL-ready in the UI.
    - The interface supports inferred collections, fields, nested structures, and array-aware presentation.
    - NoSQL inference backend is not implemented yet.
    """
)

st.markdown(
    """
**Final positioning**

AI Schema Intelligence Platform

Not a database chatbot.
The core value is converting raw schemas into AI-understandable semantic intelligence.
"""
)
