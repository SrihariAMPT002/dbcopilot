"""
Semantic Intelligence page.

Database-level semantic profile workflow:
Select Connected Database -> Generate Semantics -> View Results -> Download
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.api_client import (
    export_semantic_profile,
    generate_semantics,
    get_connections,
    get_semantic_profile,
)
from components.sidebar import render_sidebar


st.set_page_config(
    page_title="Semantic Intelligence",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .hero {
        padding: 1.1rem 1.2rem;
        border-radius: 20px;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%);
        color: #e2e8f0;
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: 0 18px 40px rgba(15, 23, 42, 0.14);
    }
    .section-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
    }
    .status-pill {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .status-ready { background: #dcfce7; color: #166534; }
    .status-processing { background: #dbeafe; color: #1d4ed8; }
    .status-failed { background: #fee2e2; color: #b91c1c; }
    .status-pending { background: #f3f4f6; color: #374151; }
    .entity-pill {
        display: inline-block;
        margin: 0.25rem 0.35rem 0 0;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        background: #eef2ff;
        color: #3730a3;
        font-weight: 600;
        font-size: 0.84rem;
    }
    .use-case-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.7rem;
    }
    .label {
        color: #64748b;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.25rem;
    }
    .value {
        color: #0f172a;
        font-size: 0.95rem;
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()


def _safe_list(value):
    return value if isinstance(value, list) else []


def _format_timestamp(value):
    if isinstance(value, str) and value:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return "N/A"


def _format_duration(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2f} ms"
    except (TypeError, ValueError):
        return "N/A"


def _status_meta(profile: dict | None) -> tuple[str, str]:
    if not profile:
        return "Not Generated", "status-pending"
    status = (profile.get("generation_status") or "not_generated").lower()
    if status == "completed":
        return "Ready", "status-ready"
    if status == "processing":
        return "Processing", "status-processing"
    if status in {"failed", "error"}:
        return "Failed", "status-failed"
    if status == "no_metadata":
        return "Not Generated", "status-pending"
    return status.replace("_", " ").title(), "status-pending"


def _load_profile(db_id: int, force: bool = False):
    current_db = st.session_state.get("semantic_profile_db_id")
    if force or current_db != db_id or "semantic_profile" not in st.session_state:
        ok, payload = get_semantic_profile(db_id)
        if ok:
            st.session_state.semantic_profile = payload
            st.session_state.semantic_profile_db_id = db_id
            return payload, True
        st.session_state.semantic_profile = None
        st.session_state.semantic_profile_db_id = db_id
        return None, False
    return st.session_state.get("semantic_profile"), True


st.markdown(
    """
<div class="hero">
    <div style="font-size: 1.75rem; font-weight: 800; margin-bottom: 0.25rem;">Semantic Intelligence</div>
    <div style="font-size: 0.98rem; color: rgba(226,232,240,0.88);">
        Build one business semantic profile per database and use it to explain the schema in business language.
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")

ok_connections, connections_payload = get_connections()
connections = connections_payload if ok_connections and isinstance(connections_payload, list) else []
active_connections = [c for c in connections if c.get("status") == "active"]

if not active_connections:
    st.warning("No active connected databases found. Connect and activate a database first.")
    st.stop()

db_options = {
    f"{conn.get('name', 'Unnamed')} ({conn.get('db_type', '').upper()})": conn
    for conn in active_connections
}
selected_label = st.selectbox("Connected Database", options=list(db_options.keys()))
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]

profile, profile_ok = _load_profile(db_id)
status_text, status_class = _status_meta(profile if profile_ok else None)

header_cols = st.columns([2, 1, 1])
with header_cols[0]:
    st.markdown(
        f"""
        <div class="section-card">
            <div class="label">Selected Database</div>
            <div class="value">{selected_conn.get('name', 'Unnamed')}</div>
            <div style="margin-top: 0.4rem; color: #64748b;">
                {selected_conn.get('display_name') or selected_conn.get('name')} · {selected_conn.get('db_type', '').upper()}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_cols[1]:
    st.markdown(
        f"""
        <div class="section-card">
            <div class="label">Status</div>
            <div class="status-pill {status_class}">{status_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_cols[2]:
    confidence_value = float(profile.get("confidence_score", 0.0)) if profile else 0.0
    st.markdown(
        f"""
        <div class="section-card">
            <div class="label">Confidence</div>
            <div class="value">{confidence_value:.0%}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

action_cols = st.columns([1.4, 1, 1, 1])
if "semantic_generate_busy" not in st.session_state:
    st.session_state.semantic_generate_busy = False
if "semantic_last_duration_ms" not in st.session_state:
    st.session_state.semantic_last_duration_ms = None

with action_cols[0]:
    if st.button(
        "Generate Semantics",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.semantic_generate_busy,
    ):
        st.session_state.semantic_generate_busy = True
        with st.spinner("Generating business semantic profile..."):
            ok_generate, result = generate_semantics(db_id)
        st.session_state.semantic_generate_busy = False

        if ok_generate:
            st.session_state.semantic_last_duration_ms = result.get("duration_ms")
            _load_profile(db_id, force=True)
            st.success(result.get("message", "Semantic profile generated."))
            st.rerun()
        else:
            st.error(result.get("error", result.get("detail", "Semantic generation failed")))

with action_cols[1]:
    if st.button("Refresh", use_container_width=True):
        _load_profile(db_id, force=True)
        st.rerun()

with action_cols[2]:
    ok_export_json, export_json = (export_semantic_profile(db_id, "json") if profile else (False, {}))
    if ok_export_json:
        st.download_button(
            label="Download JSON",
            data=export_json.get("content", ""),
            file_name=export_json.get("filename", f"{selected_conn.get('name', 'database')}_semantics.json"),
            mime="application/json",
            use_container_width=True,
            key="download_semantics_json",
        )
    else:
        st.button("Download JSON", use_container_width=True, disabled=True)

with action_cols[3]:
    ok_export_md, export_md = (export_semantic_profile(db_id, "markdown") if profile else (False, {}))
    if ok_export_md:
        st.download_button(
            label="Download Markdown",
            data=export_md.get("content", ""),
            file_name=export_md.get("filename", f"{selected_conn.get('name', 'database')}_semantics.md"),
            mime="text/markdown",
            use_container_width=True,
            key="download_semantics_markdown",
        )
    else:
        st.button("Download Markdown", use_container_width=True, disabled=True)

if not profile:
    st.info("No semantic profile has been generated for this database yet.")
    st.stop()

st.write("")

summary = profile
status_text, status_class = _status_meta(summary)

st.markdown(
    f"""
    <div class="section-card">
        <div class="label">Generation Status</div>
        <div class="status-pill {status_class}">{status_text}</div>
        <div style="height: 0.7rem;"></div>
        <div class="label">Business Domain</div>
        <div class="value">{summary.get('business_domain') or 'Not determined'}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

st.markdown(
    f"""
    <div class="section-card">
        <div class="label">Business Summary</div>
        <div style="height: 0.7rem;"></div>
        <div class="value">{summary.get('business_summary') or 'No summary available.'}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")
st.markdown(
    f"""
    <div class="section-card">
        <div class="label">Analysis Notes</div>
        <div style="height: 0.7rem;"></div>
        <div class="value">{summary.get('analysis_notes') or 'No analysis notes available.'}</div>  
    </div>
    """,
    unsafe_allow_html=True,
)


st.write("")

st.markdown('<div>', unsafe_allow_html=True)
st.markdown("### Key Entities")
entities = _safe_list(summary.get("key_entities"))
if entities:
    st.markdown(" ".join(f"<span class='entity-pill'>{entity}</span>" for entity in entities), unsafe_allow_html=True)
else:
    st.caption("No key entities identified.")
st.markdown("</div>", unsafe_allow_html=True)

st.write("")

st.markdown('<div>', unsafe_allow_html=True)
st.markdown("### Business Glossary")
glossary_items = _safe_list(summary.get("business_glossary"))
if glossary_items:
    rows = []
    for item in glossary_items:
        if isinstance(item, dict):
            rows.append({"Term": item.get("term", ""), "Definition": item.get("definition", "")})
        else:
            rows.append({"Term": str(item), "Definition": ""})
    st.table(rows)
else:
    st.caption("No glossary entries available.")
st.markdown("</div>", unsafe_allow_html=True)

st.write("")

st.markdown('<div>', unsafe_allow_html=True)
st.markdown("### Suggested Use Cases")
use_cases = _safe_list(summary.get("suggested_use_cases"))
if use_cases:
    for use_case in use_cases:
        st.markdown(f"<div class='use-case-card'>{use_case}</div>", unsafe_allow_html=True)
else:
    st.caption("No suggested use cases available.")
st.markdown("</div>", unsafe_allow_html=True)

st.write("")

details_cols = st.columns(3)
details_cols[0].markdown(
    f"""
    <div class="section-card">
        <div class="label">Generated Timestamp</div>
        <div class="value">{_format_timestamp(summary.get('generated_at'))}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
details_cols[1].markdown(
    f"""
    <div class="section-card">
        <div class="label">Duration</div>
        <div class="value">{_format_duration(st.session_state.semantic_last_duration_ms)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
details_cols[2].markdown(
    f"""
    <div class="section-card">
        <div class="label">Stored Status</div>
        <div class="value">{summary.get('generation_status', 'unknown').replace('_', ' ').title()}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
