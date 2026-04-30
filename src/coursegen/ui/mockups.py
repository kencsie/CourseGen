"""
Streamlit-agraph circle aesthetic + hover focus mode.

Matches the look of the current streamlit-agraph DAG (green circles, labels
below, pink edges, level number as prefix on label) and adds hover focus:
hovering any node lights up its ancestors, dims everything else, and replaces
each ancestor's number prefix with a SUBGRAPH-LOCAL level number (re-running
compute_node_numbers on the ancestor subgraph).

Run with:
    uv run streamlit run src/coursegen/ui/mockups.py
"""
from __future__ import annotations

import hashlib
import html
import json

import streamlit as st
import streamlit.components.v1 as components

from coursegen.db.crud import load_generation
from coursegen.ui.utils.node_numbering import compute_node_numbers

st.set_page_config(page_title="DAG Hover Focus", layout="wide")

RECORD_ID = "368e6de4-dc60-4005-8ef8-d12d190ddc9f"

# Same as src/coursegen/ui/components/roadmap_visualizer.py
AGRAPH_COLORS = {
    "not_started": "#90EE90",
    "in_progress": "#FFD700",
    "completed":   "#4169E1",
}

CIRCLE_W = 60
CIRCLE_H = 60
LABEL_H = 36
CARD_H = CIRCLE_H + 6 + LABEL_H


def fake_status(node_id: str, layer: int) -> str:
    h = int(hashlib.md5(node_id.encode()).hexdigest()[:8], 16)
    if layer == 0:
        return "completed"
    return ["not_started", "in_progress", "completed"][h % 3]


@st.cache_data(show_spinner=False)
def load_sample():
    rec = load_generation(RECORD_ID)
    return rec["roadmap"] if rec else None


def build_layers(roadmap, numbers):
    layers_map: dict[int, list[str]] = {}
    for n in roadmap["nodes"]:
        layer = int(numbers.get(n["id"], "1").split(".")[0]) - 1
        layers_map.setdefault(layer, []).append(n["id"])
    return [layers_map[i] for i in sorted(layers_map)]


def layout_positions(layers):
    layer_gap, sibling_gap, pad = 130, 30, 30
    max_h = max(len(l) for l in layers)
    canvas_h = max_h * CARD_H + (max_h - 1) * sibling_gap + 2 * pad
    canvas_w = len(layers) * CIRCLE_W + (len(layers) - 1) * layer_gap + 2 * pad
    pos = {}
    for li, ids in enumerate(layers):
        x = pad + li * (CIRCLE_W + layer_gap)
        layer_h = len(ids) * CARD_H + (len(ids) - 1) * sibling_gap
        y_start = (canvas_h - layer_h) / 2
        for i, nid in enumerate(ids):
            pos[nid] = (x, y_start + i * (CARD_H + sibling_gap))
    return pos, canvas_w, canvas_h


def compute_focus_levels(roadmap, node_order, parents_map):
    """{target: {ancestor_id: subgraph_level_str}} — reuses compute_node_numbers
    on the ancestor subgraph so badge numbers are local to the learning path."""

    def ancestors_and_self(target):
        visited = {target}
        stack = [target]
        while stack:
            n = stack.pop()
            for p in parents_map.get(n, []):
                if p not in visited:
                    visited.add(p)
                    stack.append(p)
        return visited

    out = {}
    for target in node_order:
        anc = ancestors_and_self(target)
        sub_nodes = []
        for orig in roadmap["nodes"]:
            if orig["id"] in anc:
                deps = [d for d in (orig.get("dependencies") or []) if d in anc]
                sub_nodes.append({**orig, "dependencies": deps})
        out[target] = compute_node_numbers({"nodes": sub_nodes})
    return out


def build_html(roadmap, numbers, node_order, parents_map):
    layers = build_layers(roadmap, numbers)
    pos, cw, ch = layout_positions(layers)

    statuses = {
        nid: fake_status(nid, int(numbers[nid].split(".")[0]) - 1)
        for nid in node_order
    }
    labels_by_id = {n["id"]: n["label"] for n in roadmap["nodes"]}

    arrow_id = "arrow-focus"
    arrow_id_focused = "arrow-focused"
    cy_off = CIRCLE_H / 2
    paths = []
    for n in roadmap["nodes"]:
        for p in (n.get("dependencies") or []):
            if p in pos and n["id"] in pos:
                sx, sy = pos[p]
                dx, dy = pos[n["id"]]
                x1, y1 = sx + CIRCLE_W, sy + cy_off
                x2, y2 = dx, dy + cy_off
                cx = (x1 + x2) / 2
                d = f"M {x1} {y1} C {cx} {y1}, {cx} {y2}, {x2} {y2}"
                paths.append(
                    f'<path class="dag-edge" data-src="{p}" data-dst="{n["id"]}" d="{d}" '
                    f'stroke="#fda4af" stroke-width="1.5" fill="none" '
                    f'marker-end="url(#{arrow_id})"/>'
                )

    svg = (
        f'<svg width="{cw}" height="{ch}">'
        f'<defs>'
        f'<marker id="{arrow_id}" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="#fda4af"/></marker>'
        f'<marker id="{arrow_id_focused}" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="#2563eb"/></marker>'
        f'</defs>'
        f'{"".join(paths)}</svg>'
    )

    cards = ""
    for nid, (x, y) in pos.items():
        color = AGRAPH_COLORS[statuses[nid]]
        title = html.escape(labels_by_id[nid], quote=True)
        label_text = html.escape(labels_by_id[nid])
        cards += (
            f'<div class="dag-card" data-node-id="{nid}" '
            f'style="left:{x:.0f}px;top:{y:.0f}px;" '
            f'title="{title}">'
            f'<div class="circle" style="background:{color}"></div>'
            f'<div class="node-label">'
            f'<span class="node-num">{numbers[nid]}</span> '
            f'<span class="node-text">{label_text}</span>'
            f'</div></div>'
        )

    focus_data = compute_focus_levels(roadmap, node_order, parents_map)
    focus_data_json = json.dumps(focus_data, ensure_ascii=False)
    global_numbers_json = json.dumps(numbers, ensure_ascii=False)

    css = """
    body { margin: 0; padding: 8px; background: white;
      font-family: -apple-system, "Helvetica Neue", "Microsoft JhengHei", sans-serif; }
    .dag-canvas {
      position: relative; background: white;
      border: 1px solid #e5e7eb; border-radius: 10px; overflow: auto;
    }
    .dag-canvas svg { position: absolute; top: 0; left: 0; pointer-events: none; }

    .dag-card {
      position: absolute; width: 60px; cursor: pointer;
      transition: opacity 0.2s, transform 0.15s;
    }
    .dag-card.dimmed { opacity: 0.18; }
    .dag-card.focused { z-index: 5; }
    .dag-card:hover { transform: translateY(-1px); }

    .circle {
      width: 60px; height: 60px; border-radius: 50%;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      transition: box-shadow 0.15s;
    }
    .dag-card.focused .circle {
      box-shadow: 0 0 0 3px #2563eb, 0 4px 12px rgba(37,99,235,0.3);
    }
    .dag-card.target .circle {
      box-shadow: 0 0 0 3px #dc2626, 0 4px 12px rgba(220,38,38,0.3);
    }

    .node-label {
      width: 200px; margin-left: -70px; margin-top: 6px;
      text-align: center; font-size: 13px; font-weight: 500;
      color: #111827; line-height: 1.25;
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
      overflow: hidden; word-break: break-word;
    }
    .node-num {
      font-weight: 700; color: #6b7280;
      font-variant-numeric: tabular-nums;
      margin-right: 2px;
    }
    .dag-card.focused .node-num { color: #2563eb; }
    .dag-card.target .node-num { color: #dc2626; }

    .dag-edge { transition: opacity 0.2s, stroke 0.2s, stroke-width 0.2s, marker-end 0.2s; }
    .dag-edge.dimmed-edge { opacity: 0.12; }
    .dag-edge.focused-edge {
      stroke: #2563eb !important;
      stroke-width: 2.4 !important;
      opacity: 1;
      marker-end: url(#arrow-focused) !important;
    }
    """

    js = """
    const focusData = __FOCUS_DATA__;
    const globalNumbers = __GLOBAL_NUMBERS__;
    const cards = document.querySelectorAll('.dag-card');
    const edges = document.querySelectorAll('.dag-edge');

    function activate(targetId) {
      const focused = focusData[targetId] || {};
      cards.forEach(card => {
        const id = card.dataset.nodeId;
        const subNum = focused[id];
        const numEl = card.querySelector('.node-num');
        if (subNum !== undefined) {
          card.classList.remove('dimmed');
          card.classList.add('focused');
          card.classList.toggle('target', id === targetId);
          numEl.textContent = subNum;
        } else {
          card.classList.add('dimmed');
          card.classList.remove('focused', 'target');
        }
      });
      edges.forEach(edge => {
        const src = edge.dataset.src;
        const dst = edge.dataset.dst;
        if (src in focused && dst in focused) {
          edge.classList.add('focused-edge');
          edge.classList.remove('dimmed-edge');
        } else {
          edge.classList.add('dimmed-edge');
          edge.classList.remove('focused-edge');
        }
      });
    }

    function clearFocus() {
      cards.forEach(card => {
        const id = card.dataset.nodeId;
        const numEl = card.querySelector('.node-num');
        numEl.textContent = globalNumbers[id];
        card.classList.remove('dimmed', 'focused', 'target');
      });
      edges.forEach(edge => edge.classList.remove('dimmed-edge', 'focused-edge'));
    }

    cards.forEach(card => {
      card.addEventListener('mouseenter', () => activate(card.dataset.nodeId));
    });
    document.querySelector('.dag-canvas').addEventListener('mouseleave', clearFocus);
    """.replace("__FOCUS_DATA__", focus_data_json).replace(
        "__GLOBAL_NUMBERS__", global_numbers_json
    )

    body = (
        f'<div class="dag-canvas" style="width:100%;height:{ch:.0f}px;">'
        f'{svg}{cards}</div>'
    )

    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head>"
        f"<body>{body}<script>{js}</script></body></html>"
    ), int(ch + 30)


# ── Main ───────────────────────────────────────────────────────────────
st.title("圓形節點 + Hover 焦點模式（截圖風格）")
st.markdown(
    "完全比照截圖視覺：**綠色圓**（status 著色）、**label 在圓下方**、**level 編號當 prefix**"
    "（`1.1 先備環境` 這樣）、**粉紅 edge**。\n\n"
    "**hover 任一節點**時：祖先 highlight、其他節點淡化、edge 變藍加粗、"
    "祖先的編號 prefix 會被**換成子圖內的 level 編號**（用 `compute_node_numbers` 重算），"
    "目標節點本身的編號變紅。離開 canvas 復原全域編號。"
)

roadmap = load_sample()
if roadmap is None:
    st.error(f"找不到 record `{RECORD_ID}`。")
    st.stop()

numbers = compute_node_numbers(roadmap)
node_order = [n["id"] for n in roadmap["nodes"]]
parents_map = {n["id"]: list(n.get("dependencies", []) or []) for n in roadmap["nodes"]}

st.caption(
    f"真實 15 節點 roadmap：**{roadmap['topic'][:50]}…**　"
    f"hover 任一節點看祖先子圖編號重算。"
)

demo_html, h = build_html(roadmap, numbers, node_order, parents_map)
components.html(demo_html, height=h, scrolling=True)

st.markdown("---")
st.markdown(
    "**完全可實作**——靜態畫面跟你截圖的 streamlit-agraph 視覺幾乎一致（HTML/SVG 自繪），"
    "只是元件換成 `streamlit.components.v1.html` 自繪。\n\n"
    "**整合進 app 的代價**：\n"
    "- ✅ 視覺與互動完整保留\n"
    "- ✅ 維持目前 `roadmap_visualizer.py` 的對外介面（`render_roadmap_graph(roadmap, node_progress)`）\n"
    "- ⚠️ streamlit-agraph 內建的 zoom/pan 控制按鈕（截圖右下那 4 顆）會消失，"
    "要的話得自己加（CSS transform + JS wheel/drag listener，約 80 行）\n"
    "- ⚠️ 點擊節點開 dialog：原本是 agraph 直接回傳 selected node id；換完之後需要 JS 端用 "
    "`window.parent.postMessage` 通知 Streamlit，或改用 `streamlit-extras` / 自寫 component "
    "（≈30 行）\n\n"
    "做下去嗎？我會把這個 HTML 渲染邏輯搬進 `roadmap_visualizer.py`、保留 click→dialog、"
    "保留 hover focus；zoom/pan 看你需不需要。"
)
