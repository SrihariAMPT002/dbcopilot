"""
Prompt Studio page.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import generate_prompt, get_connections, get_prompt_context
from components.sidebar import render_sidebar
from components.source_terms import source_family, terminology


st.set_page_config(
    page_title="Prompt Studio",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .studio-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.05);
    }
    .studio-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .studio-meta {
        font-size: 0.83rem;
        color: #64748b;
        margin-bottom: 10px;
    }
    .prompt-viewer {
        background: #0f172a;
        color: #e2e8f0;
        border-radius: 12px;
        padding: 18px;
        font-family: monospace;
        white-space: pre-wrap;
        line-height: 1.55;
        min-height: 260px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


st.markdown("## Prompt Studio")
st.markdown("Your differentiator. Generate AI-ready schema context packages.")
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
db_type = selected_conn.get("db_type", "")
terms = terminology(db_type)

template = st.radio(
    "Prompt Template",
    options=["default", "concise", "detailed", "analytics", "retrieval"],
    horizontal=True,
)

left, right = st.columns([2, 1])
with left:
    if st.button("Regenerate Prompt", type="primary", use_container_width=True):
        with st.spinner("Generating prompt package..."):
            ok_gen, prompt_payload = generate_prompt({"database_id": db_id, "template": template})
        if ok_gen:
            st.session_state["current_prompt"] = prompt_payload.get("prompt", "")
            st.session_state["prompt_meta"] = prompt_payload
            st.success("Prompt package generated.")
        else:
            st.error(prompt_payload.get("error", "Prompt generation failed"))
with right:
    if st.button("Refresh Prompt", use_container_width=True):
        st.rerun()

prompt_meta = st.session_state.get("prompt_meta", {})
current_prompt = st.session_state.get("current_prompt", "")

if not current_prompt:
    ok_context, context_payload = get_prompt_context(db_id)
    if ok_context and isinstance(context_payload, dict):
        current_prompt = context_payload.get("context", "")
        st.session_state["current_prompt"] = current_prompt
        st.session_state["prompt_meta"] = {
            "token_estimate": max(1, len(current_prompt.split()) * 1.33),
            "prompt_length": len(current_prompt),
            "template": template,
        }

download_cols = st.columns(3)
download_cols[0].download_button(
    "Export Prompt",
    data=current_prompt,
    file_name=f"prompt-context-{db_id}-{template}.txt",
    mime="text/plain",
    use_container_width=True,
)
download_cols[1].button(
    "Copy Prompt",
    use_container_width=True,
    disabled=True,
    help="Use the export button to download; browser clipboard support varies.",
)
download_cols[2].caption("Prompt regeneration is template-driven, not chat-driven.")

st.markdown("---")

metrics = st.columns(4)
metrics[0].metric("Schemas", selected_conn.get("schema_count", 0))
metrics[1].metric("Entities", selected_conn.get("table_count", 0))
metrics[2].metric("Token Estimate", int(prompt_meta.get("token_estimate", max(1, len(current_prompt.split()) * 1.33))))
metrics[3].metric("Prompt Length", prompt_meta.get("prompt_length", len(current_prompt)))

st.markdown("### Prompt Viewer")
st.markdown(f"<div class='prompt-viewer'>{current_prompt or 'No prompt generated yet.'}</div>", unsafe_allow_html=True)

st.markdown("---")
st.markdown("### Prompt Templates")
template_cols = st.columns(2)

with template_cols[0]:
    st.markdown(
        """
        <div class="studio-card">
            <div class="studio-title">Concise</div>
            <div class="studio-meta">Schema summary, core relationships, and top questions in a compact package.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Best for shorter context windows.")

    st.markdown(
        """
        <div class="studio-card">
            <div class="studio-title">Analytics</div>
            <div class="studio-meta">Emphasizes business context, metrics, and analytics use cases.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Best for BI-style prompt packages.")

with template_cols[1]:
    st.markdown(
        """
        <div class="studio-card">
            <div class="studio-title">Detailed</div>
            <div class="studio-meta">Full schema context with descriptions, relationships, and semantic enrichment.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Best for deeper schema reasoning.")

    st.markdown(
        """
        <div class="studio-card">
            <div class="studio-title">Retrieval</div>
            <div class="studio-meta">Optimized for schema search and prompt-context reuse.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Best for prompt retrieval workflows.")

st.markdown("---")
if source_family(db_type) == "NoSQL":
    st.info(
        f"NoSQL prompt mode is UI-ready for {terms['entity_label'].lower()}s and inferred fields. "
        "Backend prompt generation for inferred structures is not implemented yet."
    )

st.markdown(
    """
    **About Prompt Studio**

    This module generates AI-ready schema context packages for downstream retrieval and reasoning.
    It supports relational schemas now and is prepared to describe inferred NoSQL structures in the UI.
    It is not a chatbot UI. It is a prompt engineering workbench for schema intelligence.
    """
)
