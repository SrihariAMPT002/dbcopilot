"""
Operations control plane page.
"""

from __future__ import annotations

from collections import Counter
from collections import defaultdict

import streamlit as st

from components.api_client import (
    cancel_pipeline_job,
    get_connections,
    get_pipeline_jobs,
    generate_ai_context,
    retry_pipeline_job,
    run_pipeline,
)
from components.sidebar import render_sidebar


st.set_page_config(
    page_title="Operations Control Plane",
    page_icon="",
    layout="wide",
)

render_sidebar()

st.markdown("## Operations Control Plane")
st.markdown("Operational visibility for sync, semantics, embeddings, graph, and export jobs.")
st.markdown("---")

ok, conns = get_connections()
if not ok or not isinstance(conns, list) or not conns:
    st.warning("No connected databases found. Connect one first.")
    st.stop()

active_connections = [c for c in conns if c.get("status") == "active"]
if not active_connections:
    st.warning("No active databases found.")
    st.stop()

db_options = {f"{c['name']} ({c.get('db_type', '').upper()})": c for c in active_connections}
selected_db_label = st.selectbox("Database", list(db_options.keys()))
selected_db = db_options[selected_db_label]
selected_db_id = selected_db["id"]

run_col, ai_col, refresh_col = st.columns([1, 1, 1])
with run_col:
    if st.button("Run Full Pipeline", type="primary", use_container_width=True):
        ok_run, run_result = run_pipeline(selected_db_id, triggered_by="streamlit-operations")
        if ok_run:
            st.success(run_result.get("message", "Pipeline jobs queued."))
        else:
            st.error(run_result.get("error", "Failed to queue pipeline run"))
with ai_col:
    if st.button("Generate AI Context", use_container_width=True):
        ok_ctx, ctx_payload = generate_ai_context(selected_db_id, triggered_by="streamlit-operations")
        if ok_ctx:
            st.success(ctx_payload.get("message", "AI context pipeline queued."))
            st.caption(f"Parent job: {ctx_payload.get('parent_job_id')}")
        else:
            st.error(ctx_payload.get("error", "Failed to queue AI context pipeline"))
with refresh_col:
    if st.button("Refresh", use_container_width=True):
        st.session_state["operations_refresh_requested"] = True

status_filter = st.selectbox(
    "Job State Filter",
    ["ALL", "QUEUED", "RUNNING", "FAILED", "COMPLETED", "CANCELLED"],
)
status_value = None if status_filter == "ALL" else status_filter

ok_jobs, jobs_payload = get_pipeline_jobs(limit=300, status=status_value)
if not ok_jobs:
    st.error(jobs_payload.get("error", "Failed to load pipeline jobs"))
    st.stop()

jobs = jobs_payload if isinstance(jobs_payload, list) else []
db_jobs = [job for job in jobs if int(job.get("database_id", -1)) == int(selected_db_id)]

counts = Counter(job.get("status", "UNKNOWN") for job in db_jobs)
metrics = st.columns(5)
metrics[0].metric("Active", counts.get("QUEUED", 0) + counts.get("RUNNING", 0))
metrics[1].metric("Running", counts.get("RUNNING", 0))
metrics[2].metric("Failures", counts.get("FAILED", 0))
metrics[3].metric("Completed", counts.get("COMPLETED", 0))
metrics[4].metric("Cancelled", counts.get("CANCELLED", 0))

st.markdown("---")
st.markdown("### AI Context Runs")

ai_runs = [j for j in db_jobs if j.get("job_type") == "AI_CONTEXT"]
if not ai_runs:
    st.info("No AI Context runs yet. Click **Generate AI Context** to start one.")
else:
    run_options = {
        f"Run #{j.get('id')} · {j.get('status')} · {j.get('progress_percentage', 0)}%": j
        for j in ai_runs
    }
    selected_run_label = st.selectbox("Select run", list(run_options.keys()))
    selected_run = run_options[selected_run_label]
    parent_job_id = int(selected_run.get("id"))

    st.markdown(
        f"**Run status**: `{selected_run.get('status')}` · "
        f"**Progress**: {int(selected_run.get('progress_percentage', 0))}%"
    )
    st.progress(max(0, min(100, int(selected_run.get("progress_percentage", 0)))) / 100.0)
    if selected_run.get("failure_reason"):
        st.error(selected_run.get("failure_reason"))

    # Collect jobs for this run (parent + children)
    run_jobs = [j for j in db_jobs if int(j.get("id", -1)) == parent_job_id or int(j.get("parent_job_id") or -1) == parent_job_id]
    children = [j for j in run_jobs if int(j.get("parent_job_id") or -1) == parent_job_id]

    # Group per entity and stage
    per_entity: dict[str, dict[str, dict]] = defaultdict(dict)
    db_stage_jobs: dict[str, dict] = {}
    for job in children:
        entity_name = job.get("entity_name") or ""
        if job.get("entity_table_id"):
            per_entity[entity_name][job.get("job_type", "")] = job
        else:
            db_stage_jobs[job.get("job_type", "")] = job

    st.markdown("#### Database-level Stages")
    stage_cols = st.columns(4)
    for idx, stage in enumerate(["RELATIONSHIP_GRAPH", "PROMPT_GENERATION", "READINESS", "ARTIFACT_PACKAGING"]):
        item = db_stage_jobs.get(stage)
        label = stage.replace("_", " ").title()
        if not item:
            stage_cols[idx].metric(label, "n/a")
            continue
        stage_cols[idx].metric(label, item.get("status"))
        stage_cols[idx].caption(f"Job #{item.get('id')} · {item.get('progress_percentage', 0)}%")

    st.markdown("#### Per-entity Progress")
    if not per_entity:
        st.info("No entity jobs found for this run.")
    else:
        header = st.columns([3, 2, 2, 2, 3])
        header[0].markdown("**Entity**")
        header[1].markdown("**Semantics**")
        header[2].markdown("**Embeddings**")
        header[3].markdown("**Status**")
        header[4].markdown("**Actions**")

        def _stage_text(job: dict | None) -> str:
            if not job:
                return "—"
            return f"{job.get('status')} ({job.get('progress_percentage', 0)}%)"

        for entity_name in sorted(per_entity.keys()):
            semantic_job = per_entity[entity_name].get("SEMANTIC_ENRICHMENT")
            embedding_job = per_entity[entity_name].get("EMBEDDINGS")

            statuses = [j.get("status") for j in [semantic_job, embedding_job] if j]
            overall = "QUEUED" if not statuses else ("FAILED" if "FAILED" in statuses else ("RUNNING" if "RUNNING" in statuses else ("CANCELLED" if "CANCELLED" in statuses else "COMPLETED")))

            row = st.columns([3, 2, 2, 2, 3])
            row[0].markdown(f"`{entity_name}`" if entity_name else "(db stage)")
            row[1].markdown(_stage_text(semantic_job))
            row[2].markdown(_stage_text(embedding_job))
            row[3].markdown(f"`{overall}`")

            actions = row[4].columns(2)
            retry_target = None
            if semantic_job and semantic_job.get("status") == "FAILED":
                retry_target = semantic_job
            elif embedding_job and embedding_job.get("status") == "FAILED":
                retry_target = embedding_job

            if retry_target:
                if actions[0].button("Retry", key=f"retry_child_{retry_target.get('id')}"):
                    ok_retry, retry_result = retry_pipeline_job(int(retry_target["id"]), triggered_by="streamlit-operations")
                    if ok_retry:
                        st.success(f"Retry queued as job #{retry_result.get('id')}.")
                    else:
                        st.error(retry_result.get("error", "Retry failed"))
            else:
                actions[0].button("Retry", key=f"retry_disabled_{entity_name}", disabled=True)

            running_target = None
            if semantic_job and semantic_job.get("status") in {"QUEUED", "RUNNING"}:
                running_target = semantic_job
            elif embedding_job and embedding_job.get("status") in {"QUEUED", "RUNNING"}:
                running_target = embedding_job

            if running_target:
                if actions[1].button("Cancel", key=f"cancel_child_{running_target.get('id')}"):
                    ok_cancel, cancel_result = cancel_pipeline_job(int(running_target["id"]))
                    if ok_cancel:
                        st.success(f"Cancelled job #{running_target['id']}.")
                    else:
                        st.error(cancel_result.get("error", "Cancel failed"))
            else:
                actions[1].button("Cancel", key=f"cancel_disabled_{entity_name}", disabled=True)

    st.markdown("#### Failures in this run")
    failed_children = [j for j in children if j.get("status") == "FAILED"]
    if not failed_children:
        st.success("No failures in this run.")
    else:
        for job in failed_children:
            with st.container(border=True):
                st.markdown(f"**{job.get('job_type')}** · Job #{job.get('id')}")
                if job.get("entity_name"):
                    st.caption(job.get("entity_name"))
                st.error(job.get("failure_reason") or "Job failed without a reason.")

st.markdown("---")
st.markdown("### Pipeline Timeline (All Jobs)")
if not db_jobs:
    st.info("No pipeline job history yet.")
else:
    timeline_rows = []
    for item in db_jobs:
        timeline_rows.append(
            {
                "job_id": item.get("id"),
                "parent_job_id": item.get("parent_job_id"),
                "entity": item.get("entity_name"),
                "job_type": item.get("job_type"),
                "status": item.get("status"),
                "progress": f"{item.get('progress_percentage', 0)}%",
                "started_at": item.get("started_at"),
                "completed_at": item.get("completed_at"),
                "triggered_by": item.get("triggered_by"),
                "failure_reason": item.get("failure_reason"),
            }
        )
    st.dataframe(timeline_rows, use_container_width=True, hide_index=True)
