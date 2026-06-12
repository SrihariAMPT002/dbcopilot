"""Shared sidebar navigation for AI Schema Intelligence Platform."""

import streamlit as st

from components.api_client import get_packages_config


def _package_visibility() -> dict[str, bool]:
    ok, payload = get_packages_config()
    if not ok or not isinstance(payload, dict):
        return {}
    packages = payload.get("packages", {})
    if not isinstance(packages, dict):
        return {}
    return {name: bool(data.get("ui_visibility", False)) for name, data in packages.items() if isinstance(data, dict)}


NAV_LINKS = [
    ("app.py", "Home"),
    ("pages/1_connect_database.py", "Connect Database"),
    ("pages/2_connected_sources.py", "Connected Sources"),
    ("pages/3_schema_explorer.py", "Schema Explorer"),
    ("pages/14_governance.py", "Governance"),
    ("pages/4_relationship_graph.py", "Relationship Graph"),
    ("pages/5_semantic_intelligence.py", "Semantic Intelligence"),
    ("pages/7_embeddings_retrieval.py", "Embeddings & Retrieval"),
    ("pages/8_prompt_studio.py", "Prompt Studio"),
    ("pages/13_kpi_intelligence.py", "KPI Intelligence"),
    ("pages/6_ai_readiness.py", "AI Readiness"),
    ("pages/9_exports.py", "Exports"),
    ("pages/12_jobs_dashboard.py", "Jobs"),
    ("pages/11_settings.py", "Settings"),
]

PACKAGE_NAV = {
    "pages/14_governance.py": "governance",
    "pages/5_semantic_intelligence.py": "semantic",
    "pages/4_relationship_graph.py": "relationship",
    "pages/7_embeddings_retrieval.py": "rag",
    "pages/8_prompt_studio.py": "agent",
    "pages/13_kpi_intelligence.py": "kpi",
    "pages/6_ai_readiness.py": "governance",
}


def render_sidebar() -> None:
    visibility = _package_visibility()
    with st.sidebar:
        st.markdown("## AI Schema Intelligence Platform")
        st.markdown("---")

        for page_path, label in NAV_LINKS:
            package_name = PACKAGE_NAV.get(page_path)
            if package_name and not visibility.get(package_name, False):
                continue
            st.page_link(page_path, label=label)
