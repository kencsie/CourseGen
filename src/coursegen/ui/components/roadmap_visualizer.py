"""
Interactive DAG visualization with hover-driven focus mode.

Renders the roadmap as circles + labels-below using a custom Streamlit
component (HTML/SVG/JS in dag_frontend/index.html) instead of streamlit-agraph,
so we can:
- React to hover natively (highlight ancestors, dim others, recolor edges)
- Replace each ancestor's level number prefix with the SUBGRAPH-LOCAL level
  number (re-running compute_node_numbers on the ancestor subgraph)
- Still report click events back to Python so the detail dialog opens

Public API: ``render_roadmap_graph(roadmap, node_progress)`` returns
``(clicked_node_id, click_ts)``. click_ts is the frontend's Date.now() stamp,
which lets the caller tell a fresh click on the same node from a stale
(sticky) component value.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from coursegen.ui.utils.node_numbering import compute_node_numbers

# ── Constants ──────────────────────────────────────────────────────────
STATUS_COLORS = {
    "not_started": "#90EE90",  # Light green
    "in_progress": "#FFD700",  # Gold
    "completed":   "#4169E1",  # Royal blue
}

CIRCLE_W = 60
CIRCLE_H = 60
LABEL_AREA_H = 36
CARD_H = CIRCLE_H + 6 + LABEL_AREA_H  # circle + spacing + 2-line label area

LAYER_GAP_X = 130   # horizontal pixels between layers
SIBLING_GAP_Y = 30  # vertical pixels between same-layer siblings
PAD = 30            # canvas padding

# ── Custom component ──────────────────────────────────────────────────
_FRONTEND_DIR = Path(__file__).parent / "dag_frontend"
_dag_component = components.declare_component(
    "coursegen_dag_visualizer",
    path=str(_FRONTEND_DIR),
)


def get_node_color(status: str) -> str:
    return STATUS_COLORS.get(status, STATUS_COLORS["not_started"])


# ── Layout helpers ────────────────────────────────────────────────────
def _build_layers(roadmap: dict, numbers: dict[str, str]) -> list[list[str]]:
    """Group node ids by layer (major number = layer + 1) preserving roadmap order."""
    layers_map: dict[int, list[str]] = {}
    for n in roadmap["nodes"]:
        layer = int(numbers.get(n["id"], "1").split(".")[0]) - 1
        layers_map.setdefault(layer, []).append(n["id"])
    return [layers_map[i] for i in sorted(layers_map)]


def _layout_positions(layers: list[list[str]]) -> tuple[dict[str, tuple[float, float]], int, int]:
    """Hierarchical LR layout. Returns (id→(x,y), canvas_w, canvas_h)."""
    max_h = max(len(l) for l in layers)
    canvas_h = max_h * CARD_H + (max_h - 1) * SIBLING_GAP_Y + 2 * PAD
    canvas_w = len(layers) * CIRCLE_W + (len(layers) - 1) * LAYER_GAP_X + 2 * PAD
    pos: dict[str, tuple[float, float]] = {}
    for li, ids in enumerate(layers):
        x = PAD + li * (CIRCLE_W + LAYER_GAP_X)
        layer_h = len(ids) * CARD_H + (len(ids) - 1) * SIBLING_GAP_Y
        y_start = (canvas_h - layer_h) / 2
        for i, nid in enumerate(ids):
            pos[nid] = (x, y_start + i * (CARD_H + SIBLING_GAP_Y))
    return pos, int(canvas_w), int(canvas_h)


# ── Focus mode: subgraph re-numbering ─────────────────────────────────
def _compute_focus_levels(
    roadmap: dict,
    node_order: list[str],
    parents_map: dict[str, list[str]],
) -> dict[str, dict[str, str]]:
    """For each target node, return {ancestor_id: subgraph_level_number_str}.

    Reuses compute_node_numbers on the ancestor subgraph so badge numbers are
    local to the learning path leading to the target (e.g. 1, 2.1, 2.2, 3...).
    """

    def ancestors_and_self(target: str) -> set[str]:
        visited = {target}
        stack = [target]
        while stack:
            n = stack.pop()
            for p in parents_map.get(n, []):
                if p not in visited:
                    visited.add(p)
                    stack.append(p)
        return visited

    out: dict[str, dict[str, str]] = {}
    for target in node_order:
        anc = ancestors_and_self(target)
        sub_nodes = []
        for orig in roadmap["nodes"]:
            if orig["id"] in anc:
                deps = [d for d in (orig.get("dependencies") or []) if d in anc]
                sub_nodes.append({**orig, "dependencies": deps})
        out[target] = compute_node_numbers({"nodes": sub_nodes})
    return out


# ── Public render function ────────────────────────────────────────────
def render_roadmap_graph(
    roadmap_data: dict,
    node_progress: dict[str, dict],
) -> tuple[str | None, int | None]:
    """Render the interactive DAG; return (clicked_node_id, click_ts) or (None, None).

    click_ts is the frontend's Date.now() stamp for the click, so the caller can
    tell a fresh click on the same node from a stale (sticky) component value.
    """
    if not roadmap_data or "nodes" not in roadmap_data:
        st.warning("⚠️ 沒有可用的 roadmap 資料")
        return None, None

    nodes = roadmap_data["nodes"]
    if not nodes:
        st.warning("⚠️ Roadmap 中沒有節點")
        return None, None

    # --- Header + legend (kept identical to old agraph version) ---
    st.subheader(f"📊 Roadmap: {roadmap_data.get('topic', 'Learning Path')}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🟢 **未開始**")
    with col2:
        st.markdown("🟡 **進行中**")
    with col3:
        st.markdown("🔵 **已完成**")
    st.markdown("---")
    st.caption("💡 Hover 任一節點查看達到該節點所需的學習路徑與順序；點擊節點開啟詳情。")

    # --- Compute layout + numbering ---
    numbers = compute_node_numbers(roadmap_data)
    node_order = [n["id"] for n in nodes]
    parents_map = {n["id"]: list(n.get("dependencies", []) or []) for n in nodes}

    layers = _build_layers(roadmap_data, numbers)
    pos, canvas_w, canvas_h = _layout_positions(layers)

    # --- Build node payloads ---
    node_payloads = []
    for n in nodes:
        nid = n["id"]
        x, y = pos[nid]
        status = node_progress.get(nid, {}).get("status", "not_started")
        node_payloads.append({
            "id": nid,
            "x": int(x),
            "y": int(y),
            "color": get_node_color(status),
            "number": numbers.get(nid, ""),
            "label": n["label"],
            "status": status,
        })

    edges_payload = [
        {"src": parent, "dst": n["id"]}
        for n in nodes
        for parent in (n.get("dependencies") or [])
        if parent in pos and n["id"] in pos
    ]

    focus_data = _compute_focus_levels(roadmap_data, node_order, parents_map)

    # --- Render component ---
    result = _dag_component(
        nodes=node_payloads,
        edges=edges_payload,
        focus_data=focus_data,
        global_numbers=numbers,
        canvas_width=canvas_w,
        canvas_height=canvas_h,
        circle_w=CIRCLE_W,
        circle_h=CIRCLE_H,
        key="dag_main",
        default=None,
    )

    if isinstance(result, dict) and result.get("nodeId"):
        return result["nodeId"], result.get("ts")
    return None, None
