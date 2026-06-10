"""
Pipeline Jobs Dashboard.
"""

from __future__ import annotations

from collections import Counter

import streamlit as st

from components.api_client import (
    cancel_pipeline_job,
    generate_embeddings,
    generate_semantics,
    get_connections,
    get_pipeline_job,
    get_pipeline_jobs,
    retry_pipeline_job,
)
from components.job_utils import render_job_status
from components.sidebar import render_sidebar


st.set_page_config(page_title="Jobs Dashboard", page_icon="", layout="wide")
render_sidebar()

with st.sidebar:
    st.markdown("### Batch Controls")
    st.caption("Queue the main intelligence stages from one place.")
    ok_sidebar, sidebar_conns = get_connections()
    sidebar_connections = sidebar_conns if ok_sidebar and isinstance(sidebar_conns, list) else []
    sidebar_db_options = {"Select database": None}
    sidebar_db_options.update({f"{c['name']} ({c.get('db_type', '').upper()})": c for c in sidebar_connections})
    sidebar_selection = st.selectbox("Target database", list(sidebar_db_options.keys()), key="jobs_sidebar_db")
    sidebar_db = sidebar_db_options[sidebar_selection]

    if sidebar_db:
        db_id = int(sidebar_db["id"])
        if st.button("Run Semantics", use_container_width=True):
            ok_sem, payload = generate_semantics(db_id)
            if ok_sem:
                st.success(f"Semantic generation queued for database #{db_id}.")
            else:
                st.error(payload.get("error", "Failed to queue semantic generation"))
        if st.button("Run Embeddings", use_container_width=True):
            ok_emb, payload = generate_embeddings(db_id)
            if ok_emb:
                st.success(f"Embedding generation queued for database #{db_id}.")
            else:
                st.error(payload.get("error", "Failed to queue embedding generation"))
    else:
        st.info("Pick a database to queue batch jobs.")

st.markdown("## Jobs Dashboard")
st.markdown("Live visibility into queued, running, failed, and completed pipeline work.")
st.markdown("---")

ok, conns = get_connections()
connections = conns if ok and isinstance(conns, list) else []
db_options = {"All Databases": None}
db_options.update({f"{c['name']} ({c.get('db_type', '').upper()})": c for c in connections})
selected = st.selectbox("Database", list(db_options.keys()))
selected_db = db_options[selected]

status_filter = st.selectbox("Status", ["ALL", "QUEUED", "RUNNING", "FAILED", "COMPLETED", "CANCELLED"], index=0)
job_type_filter = st.selectbox(
    "Job Type",
    ["ALL", "SYNC", "SEMANTIC_ENRICHMENT", "EMBEDDINGS", "RELATIONSHIP_GRAPH", "PROMPT_GENERATION", "READINESS", "ARTIFACT_PACKAGING", "AI_CONTEXT"],
    index=0,
)

ok_jobs, jobs_payload = get_pipeline_jobs(limit=300, status=None if status_filter == "ALL" else status_filter)
if not ok_jobs:
    st.error(jobs_payload.get("error", "Failed to load jobs"))
    st.stop()

jobs = jobs_payload if isinstance(jobs_payload, list) else []
if selected_db:
    jobs = [j for j in jobs if int(j.get("database_id", -1)) == int(selected_db["id"])]
if job_type_filter != "ALL":
    jobs = [j for j in jobs if j.get("job_type") == job_type_filter]

counts = Counter(j.get("status", "UNKNOWN") for j in jobs)
metrics = st.columns(5)
metrics[0].metric("Queued", counts.get("QUEUED", 0))
metrics[1].metric("Running", counts.get("RUNNING", 0))
metrics[2].metric("Failed", counts.get("FAILED", 0))
metrics[3].metric("Completed", counts.get("COMPLETED", 0))
metrics[4].metric("Cancelled", counts.get("CANCELLED", 0))

active_jobs = [j for j in jobs if j.get("status") in {"QUEUED", "RUNNING"}]
if active_jobs:
    st.info("Active jobs are auto-refreshing this page.")
    st.markdown("<meta http-equiv='refresh' content='8'>", unsafe_allow_html=True)

st.markdown("### Active Jobs")
if active_jobs:
    for job in active_jobs:
        with st.container(border=True):
            st.markdown(f"**Job #{job.get('id')}** · `{job.get('job_type')}`")
            render_job_status(job.get("id"), label="Pipeline Job", refresh_seconds=8)
else:
    st.success("No active jobs right now.")

st.markdown("### Recent Jobs")
if not jobs:
    st.info("No jobs found for the selected filters.")
else:
    rows = []
    for job in jobs:
        rows.append(
            {
                "job_id": job.get("id"),
                "database_id": job.get("database_id"),
                "job_type": job.get("job_type"),
                "status": job.get("status"),
                "progress": f"{job.get('progress_percentage', 0)}%",
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "failure_reason": job.get("failure_reason"),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.markdown("### Actions")
job_id = st.number_input("Job ID", min_value=1, step=1)
act_cols = st.columns(3)
with act_cols[0]:
    if st.button("Inspect Job", use_container_width=True):
        ok_job, job_payload = get_pipeline_job(int(job_id))
        if ok_job:
            st.session_state["inspected_job"] = job_payload
        else:
            st.error(job_payload.get("error", "Failed to inspect job"))
with act_cols[1]:
    if st.button("Retry Job", use_container_width=True):
        ok_retry, retry_payload = retry_pipeline_job(int(job_id), triggered_by="streamlit-jobs")
        if ok_retry:
            st.success(f"Retry queued as job #{retry_payload.get('id')}.")
        else:
            st.error(retry_payload.get("error", "Retry failed"))
with act_cols[2]:
    if st.button("Cancel Job", use_container_width=True):
        ok_cancel, cancel_payload = cancel_pipeline_job(int(job_id))
        if ok_cancel:
            st.success(f"Cancelled job #{cancel_payload.get('id')}.")
        else:
            st.error(cancel_payload.get("error", "Cancel failed"))

if "inspected_job" in st.session_state:
    st.markdown("### Job Details")
    st.json(st.session_state["inspected_job"])
