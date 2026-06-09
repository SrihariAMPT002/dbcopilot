"""
AI Schema Intelligence Platform - Home page.
"""

from datetime import datetime

import streamlit as st

from components.api_client import (
    get_connections,
    get_embedding_status,
    get_sync_logs,
    health_check,
)
from components.sidebar import render_sidebar


st.set_page_config(
    page_title="AI Schema Intelligence Platform",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
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
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; }
    .status-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
        color: white;
    }
    .status-active   { background: #28a745; }
    .status-error    { background: #dc3545; }
    .status-inactive { background: #6c757d; }
    .hero-title { font-size: 2.4rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0; }
    .hero-sub   { font-size: 1.1rem; color: #555; margin-top: 4px; }
    .feature-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.04);
    }
    .feature-card h4 { margin: 0 0 6px 0; color: #1a1a2e; }
    .feature-card p  { margin: 0; color: #666; font-size: 0.9rem; }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _fmt_dt(value):
    dt = _parse_dt(value)
    if not dt:
        return "n/a"
    return dt.strftime("%Y-%m-%d %H:%M")


ok_health, health = health_check()
ok_conns, conns = get_connections()
connections = conns if ok_conns and isinstance(conns, list) else []
active_connections = [c for c in connections if c.get("status") == "active"]

total_schemas = sum(c.get("schema_count", 0) for c in connections)
total_tables = sum(c.get("table_count", 0) for c in connections)

embedding_tables = 0
embedding_vectors = 0
prompt_packages = 0
healthy_vector_indexes = 0
semantic_ready = 0
latest_sync = None
latest_sync_dt = None

for conn in active_connections:
    db_id = conn.get("id")
    if not db_id:
        continue

    ok_embed, embed_payload = get_embedding_status(db_id)
    if ok_embed and isinstance(embed_payload, dict):
        embedding_tables += embed_payload.get("indexed_tables", 0)
        embedding_vectors += embed_payload.get("vectors_total", 0)
        vector_counts = embed_payload.get("vector_counts", {}) or {}
        prompt_packages += vector_counts.get("schema_prompts", 0)
        if embed_payload.get("embedding_health") and embed_payload.get("qdrant_health"):
            healthy_vector_indexes += 1
        if embed_payload.get("indexed_tables", 0) > 0:
            semantic_ready += 1

    ok_sync, sync_logs = get_sync_logs(db_id, limit=1)
    if ok_sync and isinstance(sync_logs, list) and sync_logs:
        log = sync_logs[0]
        log_dt = _parse_dt(log.get("started_at") or log.get("completed_at"))
        if log_dt and (latest_sync_dt is None or log_dt > latest_sync_dt):
            latest_sync_dt = log_dt
            latest_sync = {
                "database": conn.get("name", "Unnamed"),
                "db_type": conn.get("db_type", "").upper(),
                "status": log.get("status", "unknown"),
                "started_at": log.get("started_at"),
                "completed_at": log.get("completed_at"),
                "schemas_synced": log.get("schemas_synced", 0),
                "tables_synced": log.get("tables_synced", 0),
                "columns_synced": log.get("columns_synced", 0),
                "relationships_synced": log.get("relationships_synced", 0),
            }

vector_health = "Healthy" if active_connections and healthy_vector_indexes == len(active_connections) else "Needs attention"
semantic_status = (
    f"{semantic_ready}/{len(active_connections)} databases ready"
    if active_connections
    else "No active databases"
)


st.markdown(
    """
<div class="hero">
  <h1>AI Schema Intelligence Platform</h1>
  <p>
    Convert raw schemas into AI-ready semantic intelligence. Get you AI ready context ready for building AI-driven data applications, without the overhead of manual data modeling or documentation.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

if ok_health:
    st.sidebar.success("API Online" if health.get("status") == "healthy" else "API Degraded")
else:
    st.sidebar.error("API Offline")

st.sidebar.caption(f"v1.0.0 · Schema intelligence platform")

st.markdown("---")

metric_cols = st.columns(5)
metric_cols[0].metric("Connected Databases", len(connections))
metric_cols[1].metric("Schemas Indexed", total_schemas)
metric_cols[2].metric("Tables Processed", total_tables)
metric_cols[3].metric("Embeddings Generated", embedding_vectors)
metric_cols[4].metric("Prompt Packages Created", prompt_packages)

status_cols = st.columns(3)
status_cols[0].metric("Semantic Generation Status", semantic_status)
status_cols[1].metric("Vector Indexing Health", vector_health)
status_cols[2].metric("Latest Sync Activity", _fmt_dt(latest_sync["started_at"]) if latest_sync else "n/a")

st.markdown("### Platform Overview")

overview_cols = st.columns(2)
with overview_cols[0]:
    st.markdown(
        f"""
        <div class="feature-card">
            <h4>Connected Databases</h4>
            <p>{len(connections)} connected database(s) across {total_schemas} schema(s).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="feature-card">
            <h4>Semantic Generation Status</h4>
            <p>{semantic_status}. Semantic summaries and prompt packages are ready for retrieval workflows.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with overview_cols[1]:
    st.markdown(
        f"""
        <div class="feature-card">
            <h4>Vector Indexing Health</h4>
            <p>{vector_health}. Qdrant-backed schema vectors are available for semantic search.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="feature-card">
            <h4>Recent Exports</h4>
            <p>Export history is shown here once graph or intelligence exports are generated.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("### Latest Sync Activity")
if latest_sync:
    sync_left, sync_right = st.columns([3, 1])
    with sync_left:
        st.markdown(
            f"**{latest_sync['database']}** `{latest_sync['db_type']}` "
            f"- {latest_sync['status']}  \n"
            f"{latest_sync['schemas_synced']} schemas, {latest_sync['tables_synced']} tables, "
            f"{latest_sync['columns_synced']} columns, {latest_sync['relationships_synced']} relationships"
        )
        st.caption(
            f"Started: {_fmt_dt(latest_sync['started_at'])} | Completed: {_fmt_dt(latest_sync['completed_at'])}"
        )
    with sync_right:
        st.metric("Latest Sync", _fmt_dt(latest_sync["started_at"]))
else:
    st.info("No sync activity found yet.")

st.markdown("### Recent Exports")
recent_exports = st.session_state.get("recent_exports", [])
if recent_exports:
    for export in recent_exports[:5]:
        left, right = st.columns([3, 1])
        with left:
            st.markdown(
                f"**{export.get('title', 'Export')}**  \n"
                f"{export.get('description', 'Schema export artifact')}"
            )
        with right:
            st.caption(_fmt_dt(export.get("generated_at")))
else:
    st.info("No export history recorded yet. Export artifacts will appear here once you create them.")

st.markdown("---")

connected = len(connections)
st.markdown("### Connected Sources")
if connected:
    for conn in connections[:5]:
        status = conn.get("status", "inactive")
        badge_class = {
            "active": "status-active",
            "error": "status-error",
            "inactive": "status-inactive",
        }.get(status, "status-inactive")

        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        c1.markdown(f"**{conn.get('name', '—')}**  `{conn.get('database_name', '')}`")
        c2.markdown(
            f"<span class='status-pill {badge_class}'>{status}</span>",
            unsafe_allow_html=True,
        )
        c3.markdown(f"`{conn.get('db_type', '').upper()}`")
        c4.markdown(f"{conn.get('schema_count', 0)} schemas · {conn.get('table_count', 0)} tables")
else:
    st.info("No databases connected yet. Go to Connect Database in the sidebar to add your first data source.")
