"""
Artifact Registry page.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.api_client import (
    export_artifacts,
    get_artifact_manifest,
    get_connections,
    list_artifacts,
)
from components.sidebar import render_sidebar
from components.source_terms import source_family, terminology


st.set_page_config(page_title="Artifact Registry", page_icon="", layout="wide")
render_sidebar()

st.markdown("## Artifact Registry")
st.markdown("Versioned AI context packages for semantic intelligence, embeddings, graph intelligence, and prompt context.")
st.markdown("---")


def _fmt_dt(value: str | datetime | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value).replace("T", " ")[:19]


ok, conns = get_connections()
if not ok or not isinstance(conns, list) or not conns:
    st.warning("No connected databases found. Connect one first.")
    st.stop()

connections = [c for c in conns if c.get("status") == "active"]
source_filter = st.radio("Source Type Filter", options=["All Sources", "SQL", "NoSQL"], horizontal=True)
if source_filter == "SQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "SQL"]
elif source_filter == "NoSQL":
    connections = [c for c in connections if source_family(c.get("db_type", "")) == "NoSQL"]

if not connections:
    st.warning("No active sources in selected filter.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in connections}
selected = st.selectbox("Select Database", options=list(db_options.keys()))
selected_conn = db_options[selected]
db_id = selected_conn["id"]
terms = terminology(selected_conn.get("db_type", ""))

if source_family(selected_conn.get("db_type", "")) == "NoSQL":
    st.info(
        f"NoSQL artifact packaging is enabled for {terms['entity_label'].lower()} metadata. "
        "Coverage currently reflects backend semantic extraction parity."
    )

top_cols = st.columns([1, 1, 1, 1])
top_cols[0].metric("Database", selected_conn.get("name", "Unknown"))
top_cols[1].metric("Schemas", selected_conn.get("schema_count", 0))
top_cols[2].metric(f"{terms['entity_label']}s", selected_conn.get("table_count", 0))

ok_list, artifacts_payload = list_artifacts(db_id)
artifacts = artifacts_payload.get("artifacts", []) if ok_list and isinstance(artifacts_payload, dict) else []
top_cols[3].metric("Artifact Versions", len(artifacts))

action_cols = st.columns([1, 1, 4])
with action_cols[0]:
    if st.button("Generate Versioned Package", type="primary", use_container_width=True):
        ok_export, payload = export_artifacts(db_id)
        if ok_export:
            st.session_state["latest_artifact_export"] = payload
            st.success(payload.get("message", "Versioned artifacts generated."))
            st.rerun()
        else:
            st.error(payload.get("error", "Artifact export failed"))
with action_cols[1]:
    if st.button("Refresh Registry", use_container_width=True):
        st.rerun()
with action_cols[2]:
    st.caption("Generates semantic_summary.json, embeddings.json, relationship_graph.json, and prompt_context.md as versioned AI context packages.")

st.markdown("---")

ok_manifest, manifest_payload = get_artifact_manifest(db_id)
if ok_manifest:
    latest = manifest_payload.get("latest", {}) if isinstance(manifest_payload, dict) else {}
    st.markdown("### Latest Manifest")
    if latest:
        rows = []
        for artifact_type, item in latest.items():
            rows.append(
                {
                    "artifact_type": artifact_type,
                    "version": item.get("version"),
                    "status": item.get("export_status"),
                    "schema_hash": str(item.get("schema_hash", ""))[:16],
                    "generated_at": _fmt_dt(item.get("generated_at")),
                    "path": item.get("artifact_path"),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No artifact manifests available yet.")
else:
    st.warning(manifest_payload.get("error", "Could not load manifest."))

latest_export = st.session_state.get("latest_artifact_export", {})
latest_manifests = latest_export.get("manifests", []) if isinstance(latest_export, dict) else []
if latest_manifests:
    st.markdown("### Latest Generated Package (Download)")
    for item in latest_manifests:
        cols = st.columns([3, 2, 2, 2])
        cols[0].markdown(f"**{item.get('artifact_type')}**")
        cols[1].markdown(f"v{item.get('version', '?')}")
        cols[2].markdown(f"`{item.get('export_status', '')}`")
        cols[3].caption(_fmt_dt(item.get("generated_at")))
        if item.get("content"):
            default_name = item.get("artifact_type", "artifact").replace("/", "_")
            st.download_button(
                f"Download {item.get('artifact_type')}",
                data=item.get("content", ""),
                file_name=item.get("filename", default_name),
                mime=item.get("mime", "text/plain"),
                key=f"download_latest_{item.get('id')}",
            )

st.markdown("### Generation History")
if artifacts:
    history_rows = []
    for entry in artifacts:
        history_rows.append(
            {
                "id": entry.get("id"),
                "artifact_type": entry.get("artifact_type"),
                "version": entry.get("version"),
                "status": entry.get("export_status"),
                "schema_hash": str(entry.get("schema_hash", ""))[:16],
                "generated_at": _fmt_dt(entry.get("generated_at")),
                "artifact_path": entry.get("artifact_path"),
            }
        )
    st.dataframe(history_rows, use_container_width=True, hide_index=True)
else:
    st.info("No artifacts generated yet.")
