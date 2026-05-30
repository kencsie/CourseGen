"""
Node detail and progress tracking component.
"""
from datetime import datetime

import streamlit as st

from coursegen.ui.components.content_renderer import render_content
from coursegen.ui.components.node_chat import render_node_chat
from coursegen.ui.utils.node_numbering import compute_node_numbers


def _inject_chat_panel_css(chat_open: bool) -> None:
    """Style the round rainbow-bordered chat toggle; widen the dialog when open.

    Targets only the toggle via Streamlit's per-key wrapper class
    (.st-key-chat_fab, available since 1.39). Right-alignment uses flex (robust
    across the dialog DOM) rather than absolute positioning.
    """
    css = [
        "<style>",
        # right-align + float the toggle near the dialog bottom
        ".st-key-chat_fab{",
        "  position:sticky;bottom:1.25rem;z-index:1000;",
        "  display:flex;justify-content:flex-end;pointer-events:none;",
        "}",
        # round button with a rainbow gradient ring (double-background clip trick)
        ".st-key-chat_fab button{",
        "  pointer-events:auto;",
        "  width:3.5rem;height:3.5rem;min-height:3.5rem;border-radius:50%;padding:0;",
        "  display:flex;align-items:center;justify-content:center;",
        "  font-size:1.4rem;line-height:1;",
        "  border:3px solid transparent;",
        "  background-image:linear-gradient(#fff,#fff),"
        "linear-gradient(135deg,#ff0080,#ff8c00,#ffe600,#00e676,#00b0ff,#7c4dff);",
        "  background-origin:border-box;background-clip:padding-box,border-box;",
        "  box-shadow:0 4px 16px rgba(0,0,0,0.22);",
        "}",
        ".st-key-chat_fab button:hover{",
        "  transform:translateY(-2px);",
        "  box-shadow:0 7px 22px rgba(124,77,255,0.45);",
        "}",
    ]
    if chat_open:
        css.append(
            'div[data-testid="stDialog"] div[role="dialog"]'
            "{max-width:90vw;width:90vw;}"
        )
    css.append("</style>")
    st.markdown("\n".join(css), unsafe_allow_html=True)


def get_node_data(roadmap_data: dict, node_id: str) -> dict | None:
    """Get node data from roadmap by node ID."""
    nodes = roadmap_data.get("nodes", [])
    for node in nodes:
        if node["id"] == node_id:
            return node
    return None


def format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "未記錄"
    return dt.strftime("%Y-%m-%d %H:%M")


def render_node_detail(
    roadmap_data: dict,
    node_id: str,
    node_progress: dict[str, dict],
    on_status_update,
    content_map: dict[str, dict] | None = None,
    content_failed_nodes: list[str] | None = None,
) -> None:
    """
    Render node detail view with progress tracking and teaching content.

    Args:
        roadmap_data: Complete roadmap data
        node_id: Selected node ID
        node_progress: Node progress dictionary
        on_status_update: Callback(node_id, new_status)
        content_map: node_id -> content dict
        content_failed_nodes: list of failed node IDs
    """
    # Get node data
    node_data = get_node_data(roadmap_data, node_id)
    if not node_data:
        st.error(f"❌ 找不到節點: {node_id}")
        return

    # Compute hierarchical numbers (Kahn-layer based) for display
    numbers = compute_node_numbers(roadmap_data)
    node_number = numbers.get(node_id, "")
    title_prefix = f"{node_number} " if node_number else ""

    # Get progress info
    progress_info = node_progress.get(node_id, {})
    status = progress_info.get("status", "not_started")
    started_at = progress_info.get("started_at")
    completed_at = progress_info.get("completed_at")

    # Display node information
    st.subheader(f"📚 {title_prefix}{node_data['label']}")

    st.markdown("**📝 節點說明:**")
    st.info(node_data.get("description", "無說明"))

    # Display dependencies (with hierarchical numbers)
    dependencies = node_data.get("dependencies", [])
    parent_summaries: list[dict] = []
    if dependencies:
        st.markdown("**⚠️ 前置節點:**")
        for parent_id in dependencies:
            parent_node = get_node_data(roadmap_data, parent_id)
            parent_number = numbers.get(parent_id, "")
            if parent_node:
                prefix = f"{parent_number} " if parent_number else ""
                st.markdown(f"• {prefix}{parent_node['label']}")
                parent_summaries.append({
                    "id": parent_id,
                    "number": parent_number,
                    "label": parent_node["label"],
                })
            else:
                st.markdown(f"• {parent_id}")
                parent_summaries.append({
                    "id": parent_id,
                    "number": parent_number,
                    "label": parent_id,
                })
    else:
        st.markdown("**⚠️ 前置節點:** 無（起始節點）")

    st.markdown("---")

    # Display current status
    status_display = {
        "not_started": "⚪ 未開始",
        "in_progress": "🟡 進行中",
        "completed": "🔵 已完成",
    }
    st.markdown(f"**📊 當前狀態:** {status_display.get(status, status)}")

    # Display timestamps
    if started_at:
        st.caption(f"開始時間: {format_datetime(started_at)}")
    if completed_at:
        st.caption(f"完成時間: {format_datetime(completed_at)}")

    st.markdown("---")

    # Status update buttons
    col1, col2 = st.columns(2)

    with col1:
        if status == "not_started":
            if st.button("▶️ 標記為進行中", use_container_width=True, type="primary"):
                on_status_update(node_id, "in_progress")
                st.session_state._dialog_internal_action = True
                st.rerun()

    with col2:
        if status in ["not_started", "in_progress"]:
            if st.button("✅ 標記為已完成", use_container_width=True, type="secondary"):
                on_status_update(node_id, "completed")
                st.session_state._dialog_internal_action = True
                st.rerun()

    # Reset button for completed nodes
    if status == "completed":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 重置為未開始", use_container_width=True):
                on_status_update(node_id, "not_started")
                st.session_state._dialog_internal_action = True
                st.rerun()

    # Teaching content + per-node AI chat. The chat is opt-in via a floating
    # button so the content keeps its full width by default; opening it widens
    # the dialog and shows the chat beside the content (state: chat_open).
    st.markdown("---")

    failed = bool(content_failed_nodes and node_id in content_failed_nodes)
    content_entry = (content_map or {}).get(node_id) if content_map else None
    chat_open = st.session_state.get("chat_open", False)

    _inject_chat_panel_css(chat_open)

    def _render_teaching_content() -> None:
        if failed:
            st.warning("⚠️ 此節點的教學內容生成失敗，請嘗試重新生成 Roadmap。")
        elif content_entry:
            render_content(node_data.get("type", ""), content_entry)
        else:
            st.caption("尚未生成教學內容")

    if chat_open:
        content_col, chat_col = st.columns([3, 2], gap="medium")
        with content_col:
            _render_teaching_content()
        with chat_col:
            # content_entry=None when failed/missing so the system prompt falls
            # back to description + parent context.
            render_node_chat(
                roadmap_data=roadmap_data,
                node_id=node_id,
                node_data=node_data,
                node_number=node_number,
                parent_summaries=parent_summaries,
                content_entry=None if failed else content_entry,
            )
    else:
        _render_teaching_content()

    # Floating round toggle: 💬 opens the tutor, ✕ collapses it. Mark the rerun
    # as an internal dialog action so the dismissal heuristic keeps the dialog
    # open (see render_main_content in app.py).
    if st.button(
        "✕" if chat_open else "💬",
        key="chat_fab",
        help="收起 AI 助教" if chat_open else "開啟 AI 助教",
    ):
        st.session_state.chat_open = not chat_open
        st.session_state._dialog_internal_action = True
        st.rerun()

    # Close button (closes the whole dialog)
    st.markdown("---")
    if st.button("❌ 關閉", use_container_width=True):
        st.session_state.selected_node = None
        st.rerun()


def render_no_selection_message():
    """Render message when no node is selected."""
    st.info("👈 請點擊左側圖表中的節點以查看詳細資訊")

    st.markdown("""
    ### 📖 使用說明

    1. **生成 Roadmap**: 在側邊欄輸入學習主題和偏好設定，點擊「生成 Roadmap」
    2. **查看節點**: 點擊圖表中的節點查看詳細說明
    3. **追蹤進度**: 使用「標記為進行中」和「標記為已完成」按鈕

    ### 🎨 節點顏色說明

    - 🟢 **綠色** - 未開始
    - 🟡 **黃色** - 進行中
    - 🔵 **藍色** - 已完成

    ### ⚠️ 注意

    - 資料僅在當前會話有效
    - 關閉瀏覽器後將消失
    """)
