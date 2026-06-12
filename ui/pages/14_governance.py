"""
Governance intelligence page — metadata-driven PII and governance packages.
"""

from __future__ import annotations

import json

import streamlit as st

from components.api_client import get_connections, get_governance_package, list_column_semantics, rescan_column_semantics
from components.sidebar import render_sidebar

st.set_page_config(page_title="Governance", page_icon="", layout="wide")
render_sidebar()

st.title("Governance Intelligence")
st.caption("Metadata-driven PII classification, risk tagging, and governance packages.")

ok, connections = get_connections()
if not ok:
    st.error(connections.get("error", "Failed to load databases"))
    st.stop()

options = {f"{item.get('display_name') or item.get('name')} (ID {item.get('id')})": item.get("id") for item in connections}
if not options:
    st.info("Connect a database to view governance intelligence.")
    st.stop()

selected_label = st.selectbox("Database", list(options.keys()))
db_id = options[selected_label]

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Rescan governance", type="primary"):
        with st.spinner("Running metadata-driven governance classification..."):
            ok_rescan, result = rescan_column_semantics(db_id, force=True)
        if ok_rescan:
            st.success(f"Classified {len(result)} column semantics.")
            st.rerun()
        else:
            st.error(result.get("error", "Governance rescan failed"))

ok_pkg, package = get_governance_package(db_id)
ok_cols, columns = list_column_semantics(db_id)

if not ok_pkg:
    st.error(package.get("error", "Failed to load governance package"))
    st.stop()

summary_cols = st.columns(4)
summary_cols[0].metric("Tables covered", package.get("table_count", 0))
summary_cols[1].metric("Column semantics", len(columns) if ok_cols else 0)
pii_total = sum(len(item.get("pii_columns", [])) for item in package.get("packages", []))
risk_total = sum(len(item.get("risk_columns", [])) for item in package.get("packages", []))
summary_cols[2].metric("PII columns", pii_total)
summary_cols[3].metric("High-risk columns", risk_total)

st.subheader("Governance packages")
for item in package.get("packages", []):
    with st.expander(f"{item.get('schema_name')}.{item.get('table_name')}", expanded=False):
        st.write(item.get("table_purpose") or item.get("business_meaning") or "No table purpose recorded.")
        if item.get("pii_columns"):
            st.markdown("**PII columns**")
            st.dataframe(item["pii_columns"], use_container_width=True, hide_index=True)
        if item.get("risk_columns"):
            st.markdown("**Risk columns**")
            st.dataframe(item["risk_columns"], use_container_width=True, hide_index=True)

with st.expander("Raw governance package JSON"):
    st.code(json.dumps(package, indent=2, default=str), language="json")
