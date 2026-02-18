"""
Node detail and progress tracking component.
"""
import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime

from coursegen.ui.components.content_renderer import render_content


def get_node_data(roadmap_data: dict, node_id: str) -> Optional[dict]:
    """Get node data from roadmap by node ID."""
    nodes = roadmap_data.get("nodes", [])
    for node in nodes:
        if node["id"] == node_id:
            return node
    return None


def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime for display."""
    if dt is None:
        return "未記錄"
    return dt.strftime("%Y-%m-%d %H:%M")


def render_node_detail(
    roadmap_data: dict,
    node_id: str,
    node_progress: Dict[str, dict],
    on_status_update,
    content_map: Dict[str, dict] | None = None,
    content_failed_nodes: List[str] | None = None,
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

    # Get progress info
    progress_info = node_progress.get(node_id, {})
    status = progress_info.get("status", "not_started")
    started_at = progress_info.get("started_at")
    completed_at = progress_info.get("completed_at")

    # Display node information
    st.subheader(f"📚 {node_data['label']}")

    st.markdown("**📝 節點說明:**")
    st.info(node_data.get("description", "無說明"))

    # Display dependencies
    dependencies = node_data.get("dependencies", [])
    if dependencies:
        st.markdown("**⚠️ 前置節點:**")
        # Find parent node labels
        parent_labels = []
        for parent_id in dependencies:
            parent_node = get_node_data(roadmap_data, parent_id)
            if parent_node:
                parent_labels.append(f"• {parent_node['label']} ({parent_id})")
            else:
                parent_labels.append(f"• {parent_id}")

        for label in parent_labels:
            st.markdown(label)
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
                st.rerun()

    with col2:
        if status in ["not_started", "in_progress"]:
            if st.button("✅ 標記為已完成", use_container_width=True, type="secondary"):
                on_status_update(node_id, "completed")
                st.rerun()

    # Reset button for completed nodes
    if status == "completed":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 重置為未開始", use_container_width=True):
                on_status_update(node_id, "not_started")
                st.rerun()

    # Render teaching content
    if content_failed_nodes and node_id in content_failed_nodes:
        st.warning("⚠️ 此節點的教學內容生成失敗，請嘗試重新生成 Roadmap。")
    elif content_map and node_id in content_map:
        node_type = node_data.get("type", "")
        render_content(node_type, content_map[node_id])


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
