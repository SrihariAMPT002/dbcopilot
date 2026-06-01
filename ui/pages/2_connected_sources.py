"""
Connected Sources page - manage all connected database sources.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.api_client import (
    delete_connection,
    generate_ai_context,
    generate_embeddings,
    get_connection,
    get_connections,
    get_embedding_status,
    regenerate_semantics,
    sync_schema,
)
from components.sidebar import render_sidebar
from components.source_terms import badge_label, source_family, source_mode_text, terminology


st.set_page_config(
    page_title="Connected Sources",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .db-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .db-card-title { font-size: 1.1rem; font-weight: 700; color: #1a1a2e; }
    .db-meta       { font-size: 0.84rem; color: #64748b; }
    .badge {
        display: inline-block;
        padding: 2px 9px;
        border-radius: 10px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-active   { background: #d4edda; color: #155724; }
    .badge-error    { background: #f8d7da; color: #721c24; }
    .badge-inactive { background: #e2e8f0; color: #4a5568; }
    .badge-sql      { background: #e0e7ff; color: #3730a3; }
    .badge-nosql    { background: #dcfce7; color: #166534; }
    .mode-chip {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        background: #f8fafc;
        color: #475569;
        font-size: 0.75rem;
        margin-right: 6px;
        margin-bottom: 4px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _fmt_dt(value):
    if not value:
        return "Never"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(value)


st.markdown("## Connected Sources")
st.markdown("Manage every connected database source from one place.")

if st.button("Refresh Page", use_container_width=False):
    st.rerun()

ok, data = get_connections()
if not ok:
    st.error(f"Failed to load connections: {data.get('error', 'Unknown error')}")
    st.stop()

all_connections = data if isinstance(data, list) else []
if not all_connections:
    st.info("No databases connected yet. Go to Connect Database to add one.")
    st.stop()

source_filter = st.radio(
    "Source Type Filter",
    options=["All Sources", "SQL", "NoSQL"],
    horizontal=True,
)

if source_filter == "SQL":
    connections = [c for c in all_connections if source_family(c.get("db_type", "")) == "SQL"]
elif source_filter == "NoSQL":
    connections = [c for c in all_connections if source_family(c.get("db_type", "")) == "NoSQL"]
else:
    connections = list(all_connections)

if not connections:
    st.info(f"No {source_filter.lower()} connections found.")
    st.stop()

total_active = sum(1 for c in connections if c.get("status") == "active")
total_schemas = sum(c.get("schema_count", 0) for c in connections)
total_tables = sum(c.get("table_count", 0) for c in connections)
total_embeddings = 0
total_sql = sum(1 for c in connections if source_family(c.get("db_type", "")) == "SQL")
total_nosql = sum(1 for c in connections if source_family(c.get("db_type", "")) == "NoSQL")

metrics = st.columns(4)
metrics[0].metric("Total Connections", len(connections))
metrics[1].metric("Active", total_active)
metrics[2].metric("Total Schemas", total_schemas)
metrics[3].metric("Total Tables", total_tables)

type_metrics = st.columns(2)
type_metrics[0].metric("SQL Sources", total_sql)
type_metrics[1].metric("NoSQL Sources", total_nosql)

st.markdown("---")

TYPE_BADGES = {
    "postgresql": "badge-sql",
    "mysql": "badge-sql",
    "sqlserver": "badge-sql",
    "mongodb": "badge-nosql",
}
STATUS_BADGES = {
    "active": "badge-active",
    "error": "badge-error",
    "inactive": "badge-inactive",
}

for conn in connections:
    db_id = conn["id"]
    db_type = conn.get("db_type", "").lower()
    status = conn.get("status", "inactive")
    name = conn.get("name", "Unnamed")
    terms = terminology(db_type)

    type_class = TYPE_BADGES.get(db_type, "badge-inactive")
    status_class = STATUS_BADGES.get(status, "badge-inactive")
    source_label = badge_label(db_type)
    source_mode = source_mode_text(db_type)
    inference_mode = terms["inference_mode"]
    extraction_mode = terms["extraction_mode"]

    ok_status, embedding_status = get_embedding_status(db_id)
    if ok_status and isinstance(embedding_status, dict):
        total_embeddings += embedding_status.get("vectors_total", 0)
        embedding_health = (
            "Healthy"
            if embedding_status.get("embedding_health") and embedding_status.get("qdrant_health")
            else "Needs attention"
        )
        indexed_tables = embedding_status.get("indexed_tables", 0)
        vector_total = embedding_status.get("vectors_total", 0)
    else:
        embedding_health = "Unavailable"
        indexed_tables = 0
        vector_total = 0

    last_sync = conn.get("last_sync_at")
    last_sync_str = _fmt_dt(last_sync)

    st.markdown(
        f"""
        <div class="db-card">
          <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <span class="db-card-title">{name}</span>
            <span class="badge {type_class}">{source_label}</span>
            <span class="badge {status_class}">{status}</span>
          </div>
          <div class="db-meta" style="margin-top:8px;">
             Host: {conn.get('host','?')}:{conn.get('port','?')} &nbsp;·&nbsp;
             {terms['database_label']}: {conn.get('database_name','?')} &nbsp;·&nbsp;
             Source type: {source_label} &nbsp;·&nbsp;
             Schema extraction: {extraction_mode} &nbsp;·&nbsp;
             Last sync: {last_sync_str} &nbsp;·&nbsp;
             {conn.get('schema_count',0)} schemas · {conn.get('table_count',0)} entities
          </div>
          <div style="margin-top:8px;">
             <span class="mode-chip">{source_mode}</span>
             <span class="mode-chip">Inference mode: {inference_mode}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    detail_cols = st.columns(4)
    detail_cols[0].metric("Embedding Status", embedding_health)
    detail_cols[1].metric("Indexed Entities", indexed_tables)
    detail_cols[2].metric("Vector Count", vector_total)
    detail_cols[3].metric("Last Sync", last_sync_str)

    if conn.get("last_error"):
        st.warning(f"Last error: {conn['last_error']}")

    action_cols = st.columns([1, 1, 1, 1, 1, 1])

    with action_cols[0]:
        if st.button("Resync", key=f"sync_{db_id}", use_container_width=True):
            with st.spinner(f"Syncing {name}..."):
                ok_sync, sync_result = sync_schema(db_id)
            if ok_sync and sync_result.get("success"):
                st.success(
                    f"Sync complete: {sync_result.get('schemas_discovered', 0)} schemas, "
                    f"{sync_result.get('tables_discovered', 0)} entities"
                )
                st.rerun()
            else:
                msg = sync_result.get("message") or sync_result.get("error") or "Sync failed"
                st.error(msg)

    with action_cols[1]:
        if st.button("Refresh Metadata", key=f"refresh_{db_id}", use_container_width=True):
            ok_ref, refreshed = get_connection(db_id)
            if ok_ref and refreshed:
                st.session_state[f"refreshed_{db_id}"] = refreshed
                st.success("Metadata refreshed from backend.")
                st.rerun()
            else:
                st.error(refreshed.get("error", "Refresh failed"))

    with action_cols[2]:
        if st.button("Generate AI Context", key=f"aictx_{db_id}", type="primary", use_container_width=True):
            with st.spinner("Queuing AI context pipeline..."):
                ok_ctx, ctx_payload = generate_ai_context(db_id, triggered_by="streamlit-connected-sources")
            if ok_ctx:
                st.success(ctx_payload.get("message", "AI context pipeline queued."))
                st.caption(f"Parent job: {ctx_payload.get('parent_job_id')}")
                st.rerun()
            else:
                st.error(ctx_payload.get("error", "Failed to queue AI context pipeline"))

    with action_cols[3]:
        if st.button("Regenerate Semantics", key=f"sem_{db_id}", use_container_width=True):
            with st.spinner("Regenerating semantic enrichment..."):
                ok_sem, sem_result = regenerate_semantics(db_id)
            if ok_sem:
                st.success("Semantic enrichment regenerated.")
                st.rerun()
            else:
                st.error(sem_result.get("error", "Semantic regeneration failed"))

    with action_cols[4]:
        if st.button("Regen Embeddings", key=f"emb_{db_id}", use_container_width=True):
            with st.spinner("Regenerating embeddings..."):
                ok_emb, emb_result = generate_embeddings(db_id)
            if ok_emb:
                st.success(emb_result.get("message", "Embeddings regenerated."))
                st.rerun()
            else:
                st.error(emb_result.get("error", "Embedding regeneration failed"))

    with action_cols[5]:
        if st.button("Disconnect", key=f"del_{db_id}", use_container_width=True):
            st.session_state[f"confirm_delete_{db_id}"] = True

    if st.session_state.get(f"confirm_delete_{db_id}"):
        st.warning(f"Delete **{name}** and all its metadata?")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Yes, delete", key=f"yes_{db_id}", type="primary"):
                ok_del, result_del = delete_connection(db_id)
                if ok_del:
                    st.success(f"Deleted {name}")
                    del st.session_state[f"confirm_delete_{db_id}"]
                    st.rerun()
                else:
                    st.error(f"Delete failed: {result_del.get('error')}")
        with cc2:
            if st.button("Cancel", key=f"cancel_{db_id}"):
                del st.session_state[f"confirm_delete_{db_id}"]
                st.rerun()

    st.markdown("---")

st.caption(f"Total embeddings across sources: {total_embeddings}")
