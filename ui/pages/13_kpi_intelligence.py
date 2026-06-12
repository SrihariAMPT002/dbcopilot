"""KPI Intelligence page."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from components.api_client import generate_kpi_intelligence, get_connections, get_kpi_intelligence
from components.sidebar import render_sidebar


st.set_page_config(page_title="KPI Intelligence", page_icon="", layout="wide")
render_sidebar()

st.markdown("## KPI Intelligence")
st.markdown("Discover KPI catalog entries, lineage, coverage, and readiness from existing metadata.")
st.markdown("---")

ok, conns = get_connections()
connections = conns if ok and isinstance(conns, list) else []
active = [c for c in connections if c.get("status") == "active"]
if not active:
    st.warning("No active databases found.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in active}
selected_label = st.selectbox("Select Database", list(db_options.keys()))
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("Generate KPI Intelligence", type="primary"):
        with st.spinner("Generating KPI intelligence..."):
            success, result = generate_kpi_intelligence(db_id)
            if success:
                st.success("KPI intelligence generated.")
            else:
                st.error(result.get("error", "Failed to generate KPI intelligence"))
with col2:
    if st.button("Refresh"):
        st.session_state["kpi_intelligence_refresh_requested"] = True
with col3:
    st.caption("KPI Intelligence is package-driven and appears only when the KPI package is enabled.")

ok, package = get_kpi_intelligence(db_id)
package_data = package if ok and isinstance(package, dict) else {"latest": {}, "history": {}, "artifact_count": 0}
latest = package_data.get("latest", {})
history = package_data.get("history", {})

catalog, lineage, coverage, readiness = st.tabs(["KPI Catalog", "KPI Lineage", "KPI Coverage", "KPI Readiness"])

with catalog:
    st.caption("Canonical KPIs discovered from semantic and relationship intelligence.")
    if latest.get("kpi_catalog.json"):
        st.json(json.loads(Path(latest["kpi_catalog.json"]["artifact_path"]).read_text(encoding="utf-8")))
    else:
        st.info("No KPI catalog has been generated yet.")

with lineage:
    st.caption("Metric provenance and source path information.")
    if latest.get("kpi_lineage.json"):
        st.json(json.loads(Path(latest["kpi_lineage.json"]["artifact_path"]).read_text(encoding="utf-8")))
    else:
        st.info("No KPI lineage has been generated yet.")

with coverage:
    st.caption("Coverage and confidence across the current database.")
    catalog_items = latest.get("kpi_catalog.json", {})
    if catalog_items:
        st.metric("KPI Coverage", "See artifact")
    else:
        st.metric("KPI Coverage", "0%")
    st.metric("Artifact Count", package_data.get("artifact_count", 0))
    st.write("Latest artifacts:")
    st.json(latest or {})

with readiness:
    st.caption("KPI readiness contributes to AI readiness as a separate signal.")
    if latest.get("kpi_context.md"):
        st.text_area(
            "KPI Context",
            value=Path(latest["kpi_context.md"]["artifact_path"]).read_text(encoding="utf-8"),
            height=280,
        )
    else:
        st.info("No KPI readiness snapshot is available yet.")

st.markdown("---")
st.code(json.dumps({"database_id": db_id, "kpi_package": "enabled", "artifact_count": package_data.get("artifact_count", 0)}, indent=2), language="json")
