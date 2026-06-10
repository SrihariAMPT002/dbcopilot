"""
Helpers for rendering and polling background pipeline jobs in Streamlit.
"""

from __future__ import annotations

import streamlit as st

from components.api_client import get_pipeline_job


def render_job_status(job_id: int | None, label: str = "Job", refresh_seconds: int = 8) -> dict | None:
    if not job_id:
        st.info(f"{label} has been queued, but no job id was returned.")
        return None

    ok, payload = get_pipeline_job(int(job_id))
    if not ok or not isinstance(payload, dict):
        st.warning(payload.get("error", f"Unable to load {label.lower()} status."))
        return None

    status = str(payload.get("status", "")).upper()
    progress = int(payload.get("progress_percentage", 0) or 0)
    st.markdown(f"**{label} #{payload.get('id')}**")
    st.caption(f"Status: `{status}` · Progress: `{progress}%`")
    st.progress(max(0, min(100, progress)) / 100.0)

    failure_reason = payload.get("failure_reason")
    if failure_reason:
        st.error(failure_reason)

    if status in {"QUEUED", "RUNNING"}:
        st.caption(f"Auto-refreshing every {refresh_seconds}s while the job is active.")
        st.markdown(
            f"<meta http-equiv='refresh' content='{refresh_seconds}'>",
            unsafe_allow_html=True,
        )

    return payload
