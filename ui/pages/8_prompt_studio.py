"""
Database Intelligence Studio page.
"""

from __future__ import annotations

import json

import streamlit as st

from components.api_client import generate_prompt_artifacts, get_connections
from components.sidebar import render_sidebar
from components.source_terms import source_family, terminology


st.set_page_config(page_title="Database Intelligence Studio", page_icon="", layout="wide")

st.markdown(
    """
<style>
    .artifact-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #dbe4f0;
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 14px;
        box-shadow: 0 10px 30px rgba(15,23,42,0.05);
    }
    .artifact-title {
        font-size: 1.08rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 6px;
    }
    .artifact-meta {
        font-size: 0.83rem;
        color: #64748b;
        margin-bottom: 10px;
    }
    .section-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 14px;
    }
    .section-heading {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b;
        margin-bottom: 8px;
        font-weight: 700;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()

st.markdown("## Database Intelligence Studio")
st.markdown("AI-generated executive, business, relationship, governance, and usage guidance for every connected database.")
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

if "prompt_studio_bundle" not in st.session_state:
    st.session_state.prompt_studio_bundle = None

action_cols = st.columns([1, 1, 3])
with action_cols[0]:
    if st.button("Generate Intelligence", type="primary", use_container_width=True):
        with st.spinner("Generating database intelligence through Azure OpenAI..."):
            ok_gen, bundle_payload = generate_prompt_artifacts(db_id)
        if ok_gen:
            st.session_state.prompt_studio_bundle = bundle_payload
            st.success(bundle_payload.get("message", "Database intelligence generated."))
        else:
            st.error(bundle_payload.get("error", "Database intelligence generation failed"))
with action_cols[1]:
    if st.button("Refresh", use_container_width=True):
        st.session_state["prompt_studio_refresh_requested"] = True
with action_cols[2]:
    st.caption("Generated intelligence is persisted to artifact_manifests and traced in Langfuse.")

bundle_payload = st.session_state.prompt_studio_bundle or {}
artifacts = bundle_payload.get("artifacts", []) if isinstance(bundle_payload, dict) else []
selected_artifact = next(
    (item for item in artifacts if item.get("artifact_type") == "database_context.md"),
    artifacts[0] if artifacts else None,
)

top_cols = st.columns(5)
top_cols[0].metric("Artifacts", len(artifacts))
top_cols[1].metric("Database", selected_conn.get("name", "Unknown"))
top_cols[2].metric("Schemas", selected_conn.get("schema_count", 0))
top_cols[3].metric(f"{terms['entity_label']}s", selected_conn.get("table_count", 0))
top_cols[4].metric("Intelligence", "Ready" if artifacts else "Pending")

st.markdown("---")
st.markdown("### Intelligence Viewer")

if selected_artifact:
    content = selected_artifact.get("content", "")
    manifest = selected_artifact.get("manifest", {}) or {}
    stats = st.columns(5)
    stats[0].metric("Prompt Name", selected_artifact.get("prompt_id", ""))
    stats[1].metric("Prompt Version", selected_artifact.get("prompt_version", ""))
    stats[2].metric("Model Used", selected_artifact.get("model_name", ""))
    stats[3].metric("Quality Score", f"{selected_artifact.get('context_quality_score', 0.0):.2f}")
    stats[4].metric("Governance Coverage", f"{selected_artifact.get('governance_coverage', 0.0):.2f}")

    st.markdown(
        f"""
        <div class="artifact-card">
            <div class="artifact-title">Database Intelligence Package</div>
            <div class="artifact-meta">Prompt: {selected_artifact.get("prompt_id", "")} · Version: {selected_artifact.get("prompt_version", "")}</div>
            <div class="artifact-meta">Model: {selected_artifact.get("model_name", "")} · Generated: {selected_artifact.get("generated_at")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-box'><div class='section-heading'>Generated Intelligence</div>", unsafe_allow_html=True)
    st.markdown(content, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if manifest:
        st.markdown("### Artifact Manifest")
        st.code(json.dumps(manifest, indent=2, default=str), language="json")

    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Download Intelligence Package",
        data=content,
        file_name=selected_artifact.get("filename", "database_intelligence.md"),
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
else:
    st.info("Generate intelligence to produce the executive summary, domain analysis, process analysis, relationship intelligence, governance summary, and AI guidance.")

st.markdown("---")
st.markdown(
    """
    **Foundation First**

    Database Intelligence Studio produces the core intelligence package first.
    KPI Intelligence can be layered on later once the foundation is complete.
    """
)
