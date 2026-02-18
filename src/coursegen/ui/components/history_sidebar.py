"""
History sidebar component for browsing saved generation records.
"""
import streamlit as st

from coursegen.db.crud import list_generations, load_generation, delete_generation


def render_history_sidebar() -> None:
    """Render saved generation history in the sidebar."""
    st.sidebar.markdown("### 📜 歷史紀錄")

    records = list_generations(limit=20)

    if not records:
        st.sidebar.caption("尚無儲存的紀錄")
        return

    for record in records:
        topic_display = record["topic"]
        if len(topic_display) > 25:
            topic_display = topic_display[:25] + "..."

        date_str = ""
        if record["created_at"]:
            date_str = record["created_at"].strftime("%m/%d %H:%M")

        with st.sidebar.container(border=True):
            st.markdown(f"**{topic_display}**")
            st.caption(f"{date_str} | {record['node_count']} 個節點")

            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "📂 載入",
                    key=f"load_{record['id']}",
                    use_container_width=True,
                ):
                    _load_record(record["id"])

            with col2:
                if st.button(
                    "🗑️ 刪除",
                    key=f"del_{record['id']}",
                    use_container_width=True,
                ):
                    delete_generation(record["id"])
                    # Clear current if we just deleted it
                    if st.session_state.get("current_record_id") == record["id"]:
                        st.session_state.current_record_id = None
                    st.rerun()


def _load_record(record_id: str) -> None:
    """Load a saved record into session state."""
    data = load_generation(record_id)
    if not data:
        st.sidebar.error("❌ 載入失敗")
        return

    st.session_state.roadmap = data["roadmap"]
    st.session_state.content_map = data["content_map"]
    st.session_state.content_order = data["content_order"]
    st.session_state.content_failed_nodes = data["content_failed_nodes"]
    st.session_state.current_record_id = data["id"]
    st.session_state.selected_node = None
    st.session_state.node_progress = {}
    st.session_state.generation_metadata = {
        "elapsed_time": data.get("generation_time_sec"),
        "iterations": data.get("iteration_count"),
    }
    st.rerun()
