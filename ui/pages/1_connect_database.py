"""
Connect Database page - connection onboarding.
"""

import streamlit as st

from components.api_client import connect_database, sync_schema, test_connection
from components.job_utils import render_job_status
from components.sidebar import render_sidebar


st.set_page_config(
    page_title="Connect Database",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .section-header { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; margin-bottom: 8px; }
    .hint-text { font-size: 0.82rem; color: #64748b; }
    .support-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
        margin-bottom: 12px;
    }
    .result-box {
        background: #f0fdf4;
        border-left: 4px solid #16a34a;
        padding: 12px 16px;
        border-radius: 6px;
        margin-top: 12px;
    }
    .error-box {
        background: #fff5f5;
        border-left: 4px solid #dc3545;
        padding: 12px 16px;
        border-radius: 6px;
        margin-top: 12px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()

st.markdown("## Connect Database")
st.markdown("Connection onboarding for PostgreSQL, MySQL, SQL Server, and MongoDB.")
st.markdown("---")

DB_DEFAULTS = {
    "PostgreSQL": {"port": 5432, "type": "postgresql", "ssl_supported": True},
    "MySQL": {"port": 3306, "type": "mysql", "ssl_supported": True},
    "SQL Server": {"port": 1433, "type": "sqlserver", "ssl_supported": True},
    "MongoDB": {"port": 27017, "type": "mongodb", "ssl_supported": True},
}

left, right = st.columns([3, 2])

with left:
    with st.form("connect_form", clear_on_submit=False):
        st.markdown('<p class="section-header">1. Choose Database Type</p>', unsafe_allow_html=True)
        db_label = st.selectbox("Engine", options=list(DB_DEFAULTS.keys()), label_visibility="collapsed")
        db_meta = DB_DEFAULTS[db_label]

        st.markdown('<p class="section-header">2. Connection Details</p>', unsafe_allow_html=True)
        conn_name = st.text_input(
            "Connection Name *",
            placeholder="e.g. production-analytics",
            help="A memorable name for this source.",
        )

        c1, c2 = st.columns([3, 1])
        with c1:
            host = st.text_input("Host *", placeholder="localhost or IP")
        with c2:
            port = st.number_input("Port *", value=db_meta["port"], min_value=1, max_value=65535)

        database_name = st.text_input(
            "Database Name *",
            placeholder="my_database",
            help="Target database name for the selected source.",
        )

        st.markdown('<p class="section-header">3. Credentials</p>', unsafe_allow_html=True)
        username = st.text_input("Username *", placeholder="db_user")
        password = st.text_input("Password *", type="password", placeholder="••••••••")
        ssl_enabled = st.checkbox("Enable SSL/TLS", value=False, help="Use encrypted transport if the database supports it.")

        st.markdown("")
        btn1, btn2 = st.columns(2)
        with btn1:
            test_btn = st.form_submit_button("Test Connection", use_container_width=True)
        with btn2:
            connect_btn = st.form_submit_button("Connect & Sync", type="primary", use_container_width=True)

with right:
    st.markdown("### Supported Databases")
    for label, meta in DB_DEFAULTS.items():
        with st.container(border=True):
            st.markdown(
                f"**{label}**  \n"
                f"Default port: `{meta['port']}`  \n"
                f"Connector type: `{meta['type']}`"
            )

    st.markdown("### What happens next")
    st.info(
        "Test Connection validates credentials only. Connect & Sync saves the connection, "
        "then introspects schemas, tables, columns, and relationships."
    )
    # st.markdown("### SSL Note")
    # if db_meta["ssl_supported"]:
    #     st.caption("SSL/TLS is supported in the UI and persisted with the connection record.")
    # else:
    #     st.caption("This source type does not currently use an SSL toggle.")


def _validate() -> bool:
    missing = []
    if not conn_name.strip():
        missing.append("Connection Name")
    if not host.strip():
        missing.append("Host")
    if not database_name.strip():
        missing.append("Database Name")
    if not username.strip():
        missing.append("Username")
    if not password:
        missing.append("Password")
    if missing:
        st.error(f"Please fill in: {', '.join(missing)}")
        return False
    return True


def _payload() -> dict:
    return {
        "name": conn_name.strip(),
        "db_type": db_meta["type"],
        "host": host.strip(),
        "port": int(port),
        "database_name": database_name.strip(),
        "username": username.strip(),
        "password": password,
        "ssl_enabled": ssl_enabled,
    }


if test_btn:
    if _validate():
        with st.spinner("Testing connection..."):
            ok, result = test_connection(_payload())

        if ok and result.get("success"):
            st.success(f"Connection successful. {result.get('message', '')}")
            cols = st.columns(3)
            if result.get("server_version"):
                cols[0].metric("Server Version", result["server_version"][:40])
            if result.get("latency_ms") is not None:
                cols[1].metric("Latency", f"{result['latency_ms']} ms")
            if result.get("databases_accessible") is not None:
                cols[2].metric("Accessible DBs", result["databases_accessible"])
        else:
            msg = result.get("message") or result.get("error") or "Unknown error"
            st.error(f"Connection failed: {msg}")


if connect_btn:
    if _validate():
        with st.spinner("Creating connection..."):
            ok, conn_result = connect_database(_payload())

        if not ok or "id" not in conn_result:
            err = conn_result.get("error") or conn_result.get("detail") or "Unknown error"
            st.error(f"Failed to create connection: {err}")
            st.stop()

        db_id = conn_result["id"]
        st.success(f"Connection registered (id={db_id})")

        with st.spinner("Syncing schema..."):
            ok2, sync_result = sync_schema(db_id)

        if ok2:
            status = str(sync_result.get("status", "")).upper()
            if status == "QUEUED":
                st.success(sync_result.get("message", "Schema sync queued."))
                render_job_status(sync_result.get("job_id"), label="Sync Job")
                st.info("Go to Connected Sources or the Jobs Dashboard to monitor progress.")
            else:
                st.success(
                    f"Schema sync complete. "
                    f"Discovered {sync_result.get('schemas_discovered', 0)} schema(s), "
                    f"{sync_result.get('tables_discovered', 0)} table(s), "
                    f"{sync_result.get('columns_discovered', 0)} column(s)."
                )
                st.info("Go to Connected Sources or Schema Explorer to continue.")
        else:
            msg = sync_result.get("message") or sync_result.get("error") or "Unknown error"
            st.warning(
                f"Connection saved but sync failed: {msg}\n\n"
                "You can retry the sync from Connected Sources."
            )
