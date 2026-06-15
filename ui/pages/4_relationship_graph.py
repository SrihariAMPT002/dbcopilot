"""
Relationship Graph page - visual schema relationship intelligence.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from components.api_client import (
    export_relationship_graph,
    get_connections,
    get_join_paths,
    get_relationship_graph,
    get_relationship_package,
    get_table_neighbors,
)
from components.sidebar import render_sidebar
from components.source_terms import badge_label, source_family, terminology


st.set_page_config(
    page_title="Relationship Graph",
    page_icon="",
    layout="wide",
)

st.markdown(
    """
<style>
    .graph-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    }
    .graph-stat {
        background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px;
        min-height: 92px;
    }
    .graph-label { font-size: 0.76rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; }
    .graph-value { font-size: 1.35rem; font-weight: 800; color: #0f172a; margin-top: 4px; }
    .graph-sub { font-size: 0.84rem; color: #475569; margin-top: 6px; }
    .pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        font-size: 0.8rem;
        color: #334155;
        margin-right: 6px;
        margin-bottom: 6px;
    }
</style>
""",
    unsafe_allow_html=True,
)

render_sidebar()

st.markdown("## Relationship Graph")
st.markdown("Visual relationship intelligence with zoom, pan, highlights, and dependency paths.")
st.markdown("---")

ok, conns = get_connections()
connections = conns if ok and isinstance(conns, list) else []
if not connections:
    st.info("Connect and sync a database first to build its relationship graph.")
    st.stop()

db_options = {
    f"{conn.get('name', 'Unnamed')} ({conn.get('db_type', '').upper()})": conn for conn in connections
}
selected_label = st.selectbox("Database", options=list(db_options.keys()))
selected_conn = db_options[selected_label]
db_id = selected_conn["id"]
db_type = selected_conn.get("db_type", "")
family = source_family(db_type)
terms = terminology(db_type)
st.markdown(
    f"<span class='pill'>{badge_label(db_type)}</span>"
    f"<span class='pill'>{terms['relationship_label']}</span>",
    unsafe_allow_html=True,
)

if family == "NoSQL":
    st.info(
        "NoSQL relationship graphs are UI-ready, but inferred relationship backend support is not wired yet. "
        "This view will show inferred relationships once the backend surfaces them."
    )
    st.markdown("### NoSQL Visual States")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Collections", "Pending")
    c2.metric("Direct Relationship", "Pending")
    c3.metric("Inferred Relationship", "Pending")
    c4.metric("Dependency Paths", "Pending")
    st.markdown(
        """
        **NoSQL graph terminology**

        - direct relationship
        - inferred relationship
        - nested structure dependency
        - collection connectivity
        """
    )
    st.stop()

ok_graph, graph_payload = get_relationship_graph(db_id)
if not ok_graph:
    st.error(graph_payload.get("error", "Unable to load relationship graph"))
    st.stop()

nodes = graph_payload.get("nodes", [])
edges = graph_payload.get("edges", [])
metrics = graph_payload.get("metrics", {})
cycles = graph_payload.get("cycles", [])
relationship_intelligence = graph_payload.get("relationship_intelligence", {})
ok_package, relationship_package = get_relationship_package(db_id)
relationship_package = relationship_package if ok_package and isinstance(relationship_package, dict) else {}

top1, top2, top3, top4, top5 = st.columns(5)
top1.markdown(
    f"<div class='graph-stat'><div class='graph-label'>Most Connected Tables</div><div class='graph-value'>{len(metrics.get('central_tables', []))}</div><div class='graph-sub'>High-degree nodes</div></div>",
    unsafe_allow_html=True,
)
top2.markdown(
    f"<div class='graph-stat'><div class='graph-label'>Join Density</div><div class='graph-value'>{metrics.get('relationship_density', 0)}</div><div class='graph-sub'>Edge density across the schema</div></div>",
    unsafe_allow_html=True,
)
top3.markdown(
    f"<div class='graph-stat'><div class='graph-label'>Graph Depth</div><div class='graph-value'>{metrics.get('graph_depth', 0)}</div><div class='graph-sub'>Longest dependency span</div></div>",
    unsafe_allow_html=True,
)
top4.markdown(
    f"<div class='graph-stat'><div class='graph-label'>Relationship Complexity</div><div class='graph-value'>{metrics.get('relationship_complexity', 0)}</div><div class='graph-sub'>Depth + joins + cycles</div></div>",
    unsafe_allow_html=True,
)
top5.markdown(
    f"<div class='graph-stat'><div class='graph-label'>Isolated Tables</div><div class='graph-value'>{len(metrics.get('isolated_tables', []))}</div><div class='graph-sub'>No inbound/outbound joins</div></div>",
    unsafe_allow_html=True,
)

st.markdown("")

if relationship_intelligence:
    st.markdown("### Business Relationship Intelligence")
    bi_col1, bi_col2 = st.columns(2)
    with bi_col1:
        st.markdown("**AI Summary**")
        st.write(relationship_intelligence.get("ai_summary") or "No business summary available yet.")
        st.markdown("**Business Entity Graph**")
        st.code(relationship_intelligence.get("business_entity_graph") or "[]", language="json")
        st.markdown("**Hidden Relationships**")
        st.code(relationship_intelligence.get("hidden_relationships") or "[]", language="json")
    with bi_col2:
        st.markdown("**Business Process Flows**")
        st.code(relationship_intelligence.get("business_process_flows") or "[]", language="json")
        st.markdown("**Lifecycle flows**")
        st.code(
            relationship_intelligence.get("lifecycle_flows")
            or relationship_intelligence.get("entity_lifecycle_descriptions")
            or "[]",
            language="json",
        )
        st.markdown("**Upstream / Downstream**")
        st.code(
            json.dumps({
                "upstream_dependencies": relationship_intelligence.get("upstream_dependencies") or "[]",
                "downstream_dependencies": relationship_intelligence.get("downstream_dependencies") or "[]",
            }, indent=2),
            language="json",
        )
    st.caption(
        f"Prompt: {relationship_intelligence.get('ai_prompt_id', 'relationship_discovery')} "
        f"v{relationship_intelligence.get('ai_prompt_version', '')} · "
        f"Model: {relationship_intelligence.get('ai_model_name', '')}"
    )
    st.markdown("---")

if relationship_package.get("packages"):
    st.markdown("### Relationship Packages")
    st.json(relationship_package)

node_map = {f"{node['schema_name']}.{node['table_name']}": node for node in nodes}
focus_options = list(node_map.keys())
focus_search = st.text_input("Table search", placeholder="Search tables, schemas, or columns...")

filtered_focus_options = [
    label
    for label in focus_options
    if not focus_search or focus_search.lower() in label.lower()
]
if not filtered_focus_options:
    filtered_focus_options = focus_options

col_a, col_b, col_c = st.columns([2, 2, 1])
with col_a:
    focus_label = st.selectbox("Focus table", options=filtered_focus_options)
with col_b:
    compare_label = st.selectbox("Path target", options=focus_options, index=min(1, len(focus_options) - 1))
with col_c:
    neighbor_depth = st.slider("Depth", min_value=1, max_value=4, value=2)

focus_node = node_map[focus_label]
compare_node = node_map[compare_label]

ok_neighbors, neighbor_payload = get_table_neighbors(focus_node["table_id"], depth=neighbor_depth)
if not ok_neighbors:
    st.warning(neighbor_payload.get("error", "Unable to load neighbors"))
    neighbor_payload = {"neighbors": [], "edges": []}

ok_paths, paths_payload = get_join_paths(focus_node["table_id"], compare_node["table_id"], max_paths=5)
if not ok_paths:
    paths_payload = {"paths": [], "message": "Join paths unavailable"}

path_edge_pairs = set()
for path in paths_payload.get("paths", []):
    for step in path.get("steps", []):
        path_edge_pairs.add((step.get("source_table_id"), step.get("target_table_id")))
        path_edge_pairs.add((step.get("target_table_id"), step.get("source_table_id")))


def _table_label(node: dict) -> str:
    return f"{node['schema_name']}.{node['table_name']}"


def _build_network() -> str:
    net = Network(height="760px", width="100%", bgcolor="#ffffff", font_color="#0f172a", directed=True)
    net.toggle_physics(True)
    net.barnes_hut(gravity=-22000, central_gravity=0.3, spring_length=180, spring_strength=0.04, damping=0.35)

    focused_id = focus_node["table_id"]
    neighbor_ids = {item["table_id"] for item in neighbor_payload.get("neighbors", [])}
    search_term = focus_search.lower().strip()

    for node in nodes:
        node_id = node["table_id"]
        label = _table_label(node)
        title = (
            f"{label}<br>"
            f"Type: {node.get('table_type', 'table')}<br>"
            f"Degree: {node.get('degree', 0)}<br>"
            f"Depth: {node.get('depth', 0)}"
        )

        color = "#eef2ff"
        border = "#818cf8"
        size = 18
        if node_id == focused_id:
            color = "#fde68a"
            border = "#f59e0b"
            size = 28
        elif node_id in neighbor_ids:
            color = "#dbeafe"
            border = "#2563eb"
            size = 22
        elif node.get("is_isolated"):
            color = "#f1f5f9"
            border = "#94a3b8"

        if search_term and search_term not in label.lower():
            color = "#f8fafc"
            border = "#cbd5e1"

        net.add_node(
            node_id,
            label=label,
            title=title,
            color=color,
            borderWidth=3,
            borderWidthSelected=5,
            size=size,
        )

    for edge in edges:
        is_path_edge = (edge["source_table_id"], edge["target_table_id"]) in path_edge_pairs
        is_focus_edge = focused_id in (edge["source_table_id"], edge["target_table_id"])
        join_label = ", ".join(
            f"{item['source_column']}={item['target_column']}" for item in edge.get("join_columns", [])
        )
        color = "#94a3b8"
        width = max(1.5, float(edge.get("relationship_strength", 1.0)) * 4)
        if is_focus_edge:
            color = "#f59e0b"
            width += 1.5
        if is_path_edge:
            color = "#2563eb"
            width += 2
        net.add_edge(
            edge["source_table_id"],
            edge["target_table_id"],
            title=join_label or edge.get("relationship_type", "fk"),
            label=join_label,
            color=color,
            width=width,
            arrows="to",
            smooth={"type": "cubicBezier"},
        )

    net.set_options(
        """
        var options = {
          "interaction": {
            "hover": true,
            "tooltipDelay": 120,
            "navigationButtons": true,
            "keyboard": true
          },
          "physics": {
            "enabled": true,
            "stabilization": {
              "iterations": 180
            }
          },
          "edges": {
            "font": {"align": "middle"},
            "scaling": {"min": 1, "max": 6}
          }
        }
        """
    )

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    tmp.close()
    net.write_html(tmp.name, notebook=False, local=True)
    html = Path(tmp.name).read_text(encoding="utf-8")
    return html


st.markdown("### Interactive Graph")
graph_html = _build_network()
components.html(graph_html, height=780, scrolling=True)

st.markdown("### Dependency Paths")
if paths_payload.get("paths"):
    for idx, path in enumerate(paths_payload.get("paths", []), start=1):
        st.markdown(f"**Path {idx}** · {path.get('hops', 0)} hop(s)")
        for step in path.get("steps", []):
            join_columns = ", ".join(
                f"{item['source_column']}={item['target_column']}" for item in step.get("join_columns", [])
            )
            st.markdown(
                f"- `{step.get('source_table_name')}` → `{step.get('target_table_name')}` "
                f"({step.get('relationship_type')}, strength={step.get('relationship_strength', 0):.2f}, {join_columns})"
            )
else:
    st.info(paths_payload.get("message", "No join path found between the selected tables."))

st.markdown("### Neighbors")
neighbors = neighbor_payload.get("neighbors", [])
if neighbors:
    for item in neighbors:
        st.markdown(
            f"- **{item['schema_name']}.{item['table_name']}** "
            f"`{item['table_type']}` · degree {item['degree']} · depth {item['depth']}"
        )
else:
    st.caption("No neighboring tables at the selected depth.")

st.markdown("---")
st.markdown("### Graph Metrics")
metric_left, metric_right = st.columns(2)
with metric_left:
    st.markdown("**Central Tables**")
    for table_name in metrics.get("central_tables", []):
        st.markdown(f"- {table_name}")
    if not metrics.get("central_tables"):
        st.caption("No central tables detected yet.")
with metric_right:
    st.markdown("**Isolated Tables**")
    for table_name in metrics.get("isolated_tables", []):
        st.markdown(f"- {table_name}")
    if not metrics.get("isolated_tables"):
        st.caption("No isolated tables detected.")

if cycles:
    st.markdown("### Circular References")
    for cycle in cycles:
        st.markdown(f"- {' → '.join(cycle)}")

st.markdown("---")
st.markdown("### Exports")
e1, e2, e3 = st.columns(3)
for export_format, column in (("json", e1), ("markdown", e2), ("diagram", e3)):
    ok_export, export_payload = export_relationship_graph(db_id, export_format=export_format)
    if ok_export:
        column.download_button(
            label=f"Download {export_format.upper()}",
            data=export_payload.get("content", ""),
            file_name=export_payload.get("filename", f"relationship-graph.{export_format}"),
            mime="application/json" if export_format == "json" else "text/plain",
            use_container_width=True,
        )
    else:
        column.warning(f"{export_format.upper()} export unavailable")
