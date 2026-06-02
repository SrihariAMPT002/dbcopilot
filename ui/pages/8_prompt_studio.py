"""
Prompt Studio page.
"""

from __future__ import annotations

import json

import streamlit as st

from components.api_client import (
    generate_prompt_artifacts,
    get_connections,
    list_prompt_templates,
)
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
    .artifact-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.05);
    }
    .artifact-title {
        font-size: 1.05rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .artifact-meta {
        font-size: 0.83rem;
        color: #64748b;
        margin-bottom: 10px;
    }
    .preview-box {
        background: #0f172a;
        color: #e2e8f0;
        border-radius: 14px;
        padding: 18px;
        font-family: monospace;
        white-space: pre-wrap;
        line-height: 1.55;
        min-height: 220px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()

st.markdown("## Prompt Studio")
st.markdown("Generate versioned prompt artifacts from semantic intelligence, relationship graphs, metadata, and embeddings.")
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

if source_family(selected_conn.get("db_type", "")) == "NoSQL":
    st.info(
        f"NoSQL prompt artifacts are UI-ready for {terms['entity_label'].lower()} metadata. "
        "Artifact rendering uses inferred structure where available."
    )

templates_ok, templates_payload = list_prompt_templates()
templates = templates_payload.get("templates", []) if templates_ok and isinstance(templates_payload, dict) else []

if "prompt_studio_bundle" not in st.session_state:
    st.session_state.prompt_studio_bundle = None

top_cols = st.columns(4)
top_cols[0].metric("Templates", len(templates))
top_cols[1].metric("Database", selected_conn.get("name", "Unknown"))
top_cols[2].metric("Schemas", selected_conn.get("schema_count", 0))
top_cols[3].metric(f"{terms['entity_label']}s", selected_conn.get("table_count", 0))

action_cols = st.columns([1, 1, 4])
with action_cols[0]:
    if st.button("Generate Artifact Bundle", type="primary", use_container_width=True):
        with st.spinner("Rendering Prompt Studio artifacts..."):
            ok_gen, bundle_payload = generate_prompt_artifacts(db_id)
        if ok_gen:
            st.session_state.prompt_studio_bundle = bundle_payload
            st.success(bundle_payload.get("message", "Prompt Studio artifacts generated."))
            st.rerun()
        else:
            st.error(bundle_payload.get("error", "Prompt Studio generation failed"))
with action_cols[1]:
    if st.button("Refresh", use_container_width=True):
        st.rerun()
with action_cols[2]:
    st.caption("All prompt content is rendered from YAML templates via the shared PromptRegistry.")

st.markdown("---")
st.markdown("### Available Templates")
if templates:
    template_cols = st.columns(2)
    for idx, template in enumerate(templates):
        with template_cols[idx % 2]:
            st.markdown(
                f"""
                <div class="artifact-card">
                    <div class="artifact-title">{template.get('name', template.get('id', 'Template'))}</div>
                    <div class="artifact-meta">{template.get('description', '')}</div>
                    <div class="artifact-meta">`{template.get('path', '')}`</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("No YAML templates found in app/prompts/system.")

bundle_payload = st.session_state.prompt_studio_bundle or {}
artifacts = bundle_payload.get("artifacts", []) if isinstance(bundle_payload, dict) else []

st.markdown("---")
st.markdown("### Artifact Preview")

if artifacts:
    selected_artifact_type = st.selectbox(
        "Preview Artifact",
        options=[item.get("artifact_type", "") for item in artifacts],
        format_func=lambda value: value.replace("_", " ").title(),
    )
    selected_artifact = next(
        (item for item in artifacts if item.get("artifact_type") == selected_artifact_type),
        artifacts[0],
    )

    st.markdown(
        f"""
        <div class="artifact-card">
            <div class="artifact-title">{selected_artifact_type.replace("_", " ").title()}</div>
            <div class="artifact-meta">{selected_artifact.get('filename', '')} · {selected_artifact.get('mime', '')}</div>
            <div class="artifact-meta">Generated at {selected_artifact.get('generated_at')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    content = selected_artifact.get("content", "")
    if selected_artifact.get("mime") == "application/json":
        try:
            st.json(json.loads(content))
        except Exception:
            st.code(content, language="json")
    else:
        st.markdown(f"<div class='preview-box'>{content}</div>", unsafe_allow_html=True)

    download_cols = st.columns(2)
    download_cols[0].download_button(
        f"Download {selected_artifact_type.replace('_', ' ').title()}",
        data=content,
        file_name=selected_artifact.get("filename", f"{selected_artifact_type}.txt"),
        mime=selected_artifact.get("mime", "text/plain"),
        use_container_width=True,
    )
    download_cols[1].download_button(
        "Download Bundle",
        data=bundle_payload.get("content", ""),
        file_name=bundle_payload.get("bundle_filename", f"prompt_studio_bundle_{db_id}.json"),
        mime=bundle_payload.get("bundle_mime", "application/json"),
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("### Artifact Details")
    detail_rows = []
    for artifact in artifacts:
        detail_rows.append(
            {
                "artifact_type": artifact.get("artifact_type"),
                "filename": artifact.get("filename"),
                "mime": artifact.get("mime"),
                "generated_at": artifact.get("generated_at"),
            }
        )
    st.dataframe(detail_rows, use_container_width=True, hide_index=True)
else:
    st.info("Generate an artifact bundle to preview Database Context, System Prompt, RAG Context, Agent Context, and Text-to-SQL Context.")

st.markdown("---")
st.markdown(
    """
    **About Prompt Studio**

    Prompt Studio turns semantic intelligence and metadata into reusable artifact packages.
    It is designed for prompt engineering, RAG packaging, and agent orchestration.
    """
)
