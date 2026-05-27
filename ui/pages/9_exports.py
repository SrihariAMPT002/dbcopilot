"""
Exports page.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.api_client import export_embeddings, export_graph, export_prompts, export_schema, get_connections
from components.sidebar import render_sidebar
from components.source_terms import source_family, terminology


st.set_page_config(
    page_title="Exports",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .export-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.05);
    }
    .export-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .export-meta {
        color: #64748b;
        font-size: 0.83rem;
        margin-bottom: 10px;
    }
    .preview-box {
        background: #0f172a;
        color: #e2e8f0;
        border-radius: 12px;
        padding: 18px;
        white-space: pre-wrap;
        font-family: monospace;
        line-height: 1.55;
        min-height: 220px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _append_history(entry: dict) -> None:
    history = st.session_state.get("export_history", [])
    history.insert(0, entry)
    st.session_state["export_history"] = history[:20]


def _fmt_dt(value):
    if not value:
        return "n/a"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _render_export_block(title: str, helper, db_id: int, export_key: str, default_format: str = "json") -> None:
    st.markdown(
        f"""
        <div class="export-card">
            <div class="export-title">{title}</div>
            <div class="export-meta">Formats: JSON, Markdown, CSV</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    format_choice = st.radio(
        f"{title} format",
        options=["json", "markdown", "csv"],
        horizontal=True,
        index=["json", "markdown", "csv"].index(default_format),
        key=f"format_{export_key}",
        label_visibility="collapsed",
    )

    preview_key = f"preview_{export_key}"
    payload_key = f"payload_{export_key}"

    cols = st.columns([1, 1, 4])
    with cols[0]:
        if st.button(f"Generate {title}", key=f"gen_{export_key}", type="primary", use_container_width=True):
            ok, payload = helper(db_id, format_choice)
            if ok:
                st.session_state[payload_key] = payload
                st.session_state[preview_key] = payload.get("content", "")
                _append_history(
                    {
                        "title": title,
                        "format": format_choice,
                        "filename": payload.get("filename"),
                        "generated_at": _fmt_dt(datetime.now()),
                    }
                )
                st.success(f"{title} export generated.")
            else:
                st.error(payload.get("error", "Export failed"))
    with cols[1]:
        if st.button(f"Refresh {title}", key=f"refresh_{export_key}", use_container_width=True):
            st.rerun()
    with cols[2]:
        st.caption("Preview updates after generation. Download is available from the button below.")

    preview = st.session_state.get(preview_key, "")
    payload = st.session_state.get(payload_key, {})
    if preview:
        st.markdown(f"<div class='preview-box'>{preview[:5000]}</div>", unsafe_allow_html=True)
        download_mime = payload.get("mime", "text/plain")
        st.download_button(
            f"Download {title}",
            data=preview,
            file_name=payload.get("filename", f"{export_key}.{format_choice}"),
            mime=download_mime,
            use_container_width=True,
            key=f"download_{export_key}",
        )
    else:
        st.info(f"No {title.lower()} export generated yet.")


st.markdown("## Exports")
st.markdown("Very enterprise-style export workspace for AI schema intelligence packages.")
if source_family(selected_conn.get("db_type", "")) == "NoSQL":
    st.info(
        f"NoSQL export mode is UI-ready for {terms['entity_label'].lower()} metadata. "
        "The backend export endpoints currently surface relational metadata."
    )
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
    st.warning("No active databases. Activate a connection first.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in active_conns}
selected_label = st.selectbox("Select Database", options=list(db_options.keys()))
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]
terms = terminology(selected_conn.get("db_type", ""))

summary_cols = st.columns(4)
summary_cols[0].metric("Database", selected_conn.get("name", "Unnamed"))
summary_cols[1].metric("Schemas", selected_conn.get("schema_count", 0))
summary_cols[2].metric(f"{terms['entity_label']}s", selected_conn.get("table_count", 0))
summary_cols[3].metric("Export History", len(st.session_state.get("export_history", [])))

st.markdown("---")

schema_tab, prompt_tab, graph_tab, embeddings_tab = st.tabs(
    ["Schema Graph", "Semantic Summaries", "Prompt Context", "Embeddings Metadata"]
)

with schema_tab:
    _render_export_block("Schema Graph", export_graph, db_id, "graph")

with prompt_tab:
    _render_export_block("Prompt Context", export_prompts, db_id, "prompts")

with graph_tab:
    _render_export_block("Semantic Summaries", export_schema, db_id, "schema")

with embeddings_tab:
    _render_export_block("Embeddings Metadata", export_embeddings, db_id, "embeddings")

st.markdown("---")
st.markdown("### Export History")
history = st.session_state.get("export_history", [])
if history:
    for entry in history[:10]:
        h1, h2, h3 = st.columns([2, 1, 2])
        h1.markdown(f"**{entry['title']}**")
        h2.markdown(f"`{entry['format']}`")
        h3.caption(f"{entry.get('generated_at', 'n/a')} · {entry.get('filename', '')}")
else:
    st.info("Export history will appear here after you generate downloads.")

st.markdown("---")
st.markdown(
    """
    **About Exports**

    Export AI schema intelligence artifacts in enterprise-friendly formats:
    JSON, Markdown, and CSV.
    """
)
