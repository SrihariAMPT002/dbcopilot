"""
Chat page — placeholder for future AI querying layer.
Shows the planned architecture and lets users see what's coming.
"""

import streamlit as st
from components.sidebar import render_sidebar

st.set_page_config(
    page_title="Chat — DB Copilot", page_icon="", layout="wide"
)

st.markdown("""
<style>
    .chat-coming-soon {
        text-align: center;
        padding: 60px 40px;
        background: linear-gradient(135deg, #f0f4ff 0%, #f8f0ff 100%);
        border-radius: 16px;
        border: 1px dashed #c4b5fd;
        margin: 20px 0;
    }
    .chat-coming-soon h1 { font-size: 3rem; margin-bottom: 8px; }
    .chat-coming-soon h2 { color: #4f46e5; font-size: 1.5rem; margin-bottom: 12px; }
    .chat-coming-soon p  { color: #6b7280; font-size: 1rem; max-width: 500px; margin: 0 auto 24px; }
    .roadmap-step {
        background: white;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
        border-left: 4px solid #818cf8;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .roadmap-step.done  { border-left-color: #34d399; }
    .roadmap-step.soon  { border-left-color: #818cf8; }
    .roadmap-step.later { border-left-color: #e5e7eb; }
    .roadmap-step h4 { margin: 0 0 4px 0; font-size: 0.95rem; color: #1a1a2e; }
    .roadmap-step p  { margin: 0; font-size: 0.83rem; color: #6b7280; }
</style>
""", unsafe_allow_html=True)

render_sidebar()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="chat-coming-soon">
    <h1></h1>
    <h2>AI Chat is Coming</h2>
    <p>
        The schema context is already being collected. Once the AI layer is activated,
        you'll be able to ask questions in plain English and get SQL, results, and insights.
    </p>
</div>
""", unsafe_allow_html=True)

# ── Roadmap ───────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("###  Already Built (Foundation)")
    for item in [
        (" Database Connector Layer",
         "PostgreSQL, MySQL, SQL Server, MongoDB — all connected via async connectors."),
        ("Schema Sync Engine",
         "Full introspection: databases, schemas, tables, columns, FK relationships."),
        ("🗄 Metadata Store",
         "All schema context stored in internal PostgreSQL — ready for AI retrieval."),
        (" REST API",
         "FastAPI backend with all connection, sync and metadata endpoints live."),
        (" Schema Explorer",
         "Full browse UI — schema hierarchy, column types, keys, and relationships."),
    ]:
        st.markdown(
            f"<div class='roadmap-step done'><h4>{item[0]}</h4><p>{item[1]}</p></div>",
            unsafe_allow_html=True,
        )

with col_right:
    st.markdown("### 🚀 Next: AI Layer")
    for label, items in [
        ("soon", [
            (" Natural Language Interface",
             "Type questions in plain English. Schema-aware context injected automatically."),
            ("⚡ Text-to-SQL (LLM)",
             "GPT-4o / local LLM converts your question to validated, safe SQL."),
            (" SQL Validation Agent",
             "Checks generated SQL for correctness and safety before execution."),
            ("📊 Result Display",
             "Query results rendered as tables with one-click chart generation."),
        ]),
        ("later", [
            ("🧠 Schema Embeddings (Qdrant)",
             "Vector search over schema metadata for smarter context retrieval."),
            ("🤖 LangGraph Agent Workflows",
             "Multi-step planning agents: planner → generator → validator → executor."),
            (" AI Insights",
             "Automatic pattern detection, trend analysis and anomaly highlighting."),
            ("🗣 Conversational Memory",
             "Multi-turn conversations with Redis-backed session memory."),
        ]),
    ]:
        for item in items:
            st.markdown(
                f"<div class='roadmap-step {label}'><h4>{item[0]}</h4><p>{item[1]}</p></div>",
                unsafe_allow_html=True,
            )

# ── Demo chat mock (disabled) ─────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Preview: What Chatting Will Look Like")

with st.container():
    user_q = st.text_input(
        "Ask your database anything…",
        placeholder='e.g. "How many orders were placed last month?"',
        disabled=False,
        key="demo_input",
    )
    if user_q:
        st.info(
            "🚀 **AI query engine not yet enabled.** "
            "Your schema context is already stored and ready — "
            "AI querying will be activated in the next release.\n\n"
            f"*Your question:* \"{user_q}\""
        )

    # Fake example response to show what output will look like
    with st.expander("👀 See an example of what a response will look like"):
        st.markdown("**You:** How many users signed up this week?")
        st.markdown("---")
        st.markdown("**DB Copilot:** Here's the SQL I generated:")
        st.code(
            "SELECT COUNT(*) AS new_users\nFROM users\nWHERE created_at >= CURRENT_DATE - INTERVAL '7 days';",
            language="sql",
        )
        st.markdown("**Result:** 243 new users signed up in the last 7 days.")
        st.markdown("📈 *Insight: This is 12% higher than the previous week (217 users).*")
