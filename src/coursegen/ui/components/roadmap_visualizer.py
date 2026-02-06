"""
Interactive DAG visualization component using streamlit-agraph.
"""
import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
from typing import Dict, Optional, List


def get_node_color(status: str) -> str:
    """
    Get node color based on learning status.

    Args:
        status: Node status (not_started, in_progress, completed)

    Returns:
        Hex color code
    """
    color_map = {
        "not_started": "#90EE90",  # Light green
        "in_progress": "#FFD700",  # Gold/Yellow
        "completed": "#4169E1",  # Royal blue
    }
    return color_map.get(status, "#90EE90")  # Default to not_started


def build_graph_elements(
    roadmap_data: dict, node_progress: Dict[str, dict]
) -> tuple[List[Node], List[Edge]]:
    """
    Build agraph nodes and edges from roadmap data.

    Args:
        roadmap_data: Roadmap dictionary with 'nodes' key
        node_progress: Dictionary mapping node_id to progress info

    Returns:
        tuple: (nodes, edges) for agraph
    """
    nodes = []
    edges = []

    roadmap_nodes = roadmap_data.get("nodes", [])

    # Create nodes
    for node_data in roadmap_nodes:
        node_id = node_data["id"]
        label = node_data["label"]
        description = node_data.get("description", "")

        # Get node status for coloring
        progress_info = node_progress.get(node_id, {})
        status = progress_info.get("status", "not_started")
        color = get_node_color(status)

        # Create tooltip with status
        status_emoji = {
            "not_started": "⚪",
            "in_progress": "🟡",
            "completed": "🔵",
        }
        emoji = status_emoji.get(status, "⚪")
        title = f"{emoji} {label}\n{description}"

        # Create agraph Node
        node = Node(
            id=node_id,
            label=label,
            title=title,
            color=color,
            size=25,
            font={"size": 14},
        )
        nodes.append(node)

    # Create edges from dependencies
    for node_data in roadmap_nodes:
        node_id = node_data["id"]
        dependencies = node_data.get("dependencies", [])

        for parent_id in dependencies:
            # Edge direction: parent -> child (dependency)
            edge = Edge(
                source=parent_id,
                target=node_id,
                # type="CURVE_SMOOTH",
            )
            edges.append(edge)

    return nodes, edges


def render_roadmap_graph(roadmap_data: dict, node_progress: Dict[str, dict]) -> Optional[str]:
    """
    Render interactive DAG using streamlit-agraph.

    Args:
        roadmap_data: Complete roadmap data
        node_progress: Node progress dictionary

    Returns:
        Selected node ID or None
    """
    if not roadmap_data or "nodes" not in roadmap_data:
        st.warning("⚠️ 沒有可用的 roadmap 資料")
        return None

    # Build graph elements
    nodes, edges = build_graph_elements(roadmap_data, node_progress)

    if not nodes:
        st.warning("⚠️ Roadmap 中沒有節點")
        return None

    # Configure graph layout
    config = Config(
        width="100%",
        height=600,
        directed=True,
        physics={
            "enabled": True,
            "hierarchicalRepulsion": {
                "centralGravity": 0.0,
                "springLength": 100,
                "springConstant": 0.01,
                "nodeDistance": 200,
                "damping": 0.09,
            },
        },
        layout={
            "hierarchical": {
                "enabled": True,
                "direction": "LR",  # Left to Right flow
                "sortMethod": "directed",
                "nodeSpacing": 150,
                "levelSeparation": 200,
            }
        },
        interaction={
            "hover": True,
            "navigationButtons": True,
            "keyboard": True,
        },
    )

    # Render graph
    st.subheader(f"📊 Roadmap: {roadmap_data.get('topic', 'Learning Path')}")

    # Legend
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🟢 **未開始**")
    with col2:
        st.markdown("🟡 **進行中**")
    with col3:
        st.markdown("🔵 **已完成**")

    st.markdown("---")

    # Render interactive graph
    return_value = agraph(nodes=nodes, edges=edges, config=config)

    # Handle node selection
    if return_value:
        # agraph returns the selected node ID
        return return_value

    return None
