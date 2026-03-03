"""
CourseGen Streamlit UI - Main Application
"""

import logging
import streamlit as st
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# Configure logging (same format as basic.py)
logging.basicConfig(
    level=logging.INFO,
    format="{asctime} | {name:<20} | {levelname:<8} | {message}",
    datefmt="%Y-%m-%d %H:%M:%S",
    style="{",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Import workflow
from coursegen.workflows.basic import graph

# Import schemas
from coursegen.schemas import UserPreferences

# Import UI components
from coursegen.ui.components.preferences_form import render_preferences_form
from coursegen.ui.components.roadmap_visualizer import render_roadmap_graph
from coursegen.ui.components.node_detail import render_node_detail

# Import database
from coursegen.db.database import init_db
from coursegen.db.crud import save_generation

# Import utilities
from coursegen.ui.utils.session_state import init_session_state, reset_roadmap_state
from coursegen.ui.components.history_sidebar import render_history_sidebar
from coursegen.ui.utils.cost_tracker import CostTracker

# Langfuse observability
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

# Load environment variables
load_dotenv()

# Node name → (中文標籤, phase)
NODE_LABELS = {
    # Phase 1: Roadmap
    "knowledge_search_node": ("🔍 搜尋相關知識...", "roadmap"),
    "roadmap_node": ("🗺️ 生成學習路徑...", "roadmap"),
    "roadmap_critic_node": ("🤖 審核學習路徑...", "roadmap"),
    # Phase 2: Content
    "content_planning_node": ("📋 規劃內容順序...", "content"),
    "content_knowledge_search_node": ("🔎 搜尋節點知識...", "content"),
    "content_generation_node": ("✍️ 生成教學內容...", "content"),
    "content_critic_node": ("✅ 審核內容品質...", "content"),
    "content_advance_node": ("➡️ 前進至下一節點...", "content"),
}

# Page configuration
st.set_page_config(
    page_title="CourseGen - AI Learning Roadmap",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def generate_roadmap(question: str, preferences: UserPreferences):
    """
    Generate roadmap using LangGraph workflow with streaming progress.

    Args:
        question: Learning topic/question
        preferences: UserPreferences object

    Returns:
        Result dictionary (same shape as graph.invoke())
    """
    status_container = st.status("🚀 正在生成 Roadmap...", expanded=True)

    with status_container:
        progress_bar = st.progress(0)
        step_text = st.empty()
        step_text.write("⏳ 初始化 AI 代理...")
        start_time = time.time()

        try:
            context = {
                "model_name": os.getenv("MODEL_NAME", "google/gemini-3-flash-preview"),
                "base_url": os.getenv("BASE_URL"),
                "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
                "roadmap_critic_model": os.getenv(
                    "ROADMAP_CRITIC_MODEL", "google/gemini-3-flash-preview"
                ),
                "max_iterations": int(os.getenv("MAX_ITERATIONS", "5")),
                "tavily_api_key": os.getenv("TAVILY_KEY"),
                "content_model": os.getenv(
                    "CONTENT_MODEL", "google/gemini-3-flash-preview"
                ),
                "content_critic_model": os.getenv(
                    "CONTENT_CRITIC_MODEL", "google/gemini-3-flash-preview"
                ),
                "content_max_retries": int(os.getenv("CONTENT_MAX_RETRIES", "5")),
                "cheap_model": os.getenv(
                    "CHEAP_MODEL", "google/gemini-3-flash-preview"
                ),
            }

            st.write(f"📝 主題: {question}")
            st.write(f"🌐 語言: {preferences.language.value}")

            # --- Streaming with progress tracking ---
            max_iterations = int(os.getenv("MAX_ITERATIONS", "5"))
            # Roadmap phase: worst-case steps = (search + generation + critic) * max_iterations
            roadmap_steps_per_iter = 3  # knowledge_search + roadmap + roadmap_critic
            est_roadmap_steps = roadmap_steps_per_iter * max_iterations

            roadmap_steps_done = 0
            content_steps_done = 0
            total_content_steps = None  # determined after content_planning_node
            content_node_index = 0  # current content node (0-based)
            total_content_nodes = None

            # Track the latest full state from "values" stream
            result = {}

            langfuse_handler = LangfuseCallbackHandler()
            cost_tracker = CostTracker()

            for chunk in graph.stream(
                {
                    "question": question,
                    "user_preferences": preferences.to_prompt_context(),
                },
                context=context,
                stream_mode=["updates", "values"],
                config={"callbacks": [langfuse_handler, cost_tracker]},
            ):
                stream_type, data = chunk

                if stream_type == "values":
                    # LangGraph uses reducers to correctly accumulate full state
                    result = data
                    continue

                if stream_type != "updates":
                    continue

                node_name = list(data.keys())[0]

                label_info = NODE_LABELS.get(node_name)
                if not label_info:
                    continue

                label, phase = label_info

                if phase == "roadmap":
                    roadmap_steps_done += 1
                    # Progress: 0% ~ 30% for roadmap phase
                    pct = min(0.30, 0.30 * roadmap_steps_done / est_roadmap_steps)
                    iteration = (roadmap_steps_done - 1) // roadmap_steps_per_iter + 1
                    pct_display = int(pct * 100)
                    step_text.write(
                        f"**階段 1/2 — Roadmap 生成** (迭代 {iteration}) — {pct_display}%\n\n{label}"
                    )
                    progress_bar.progress(pct)

                elif phase == "content":
                    content_steps_done += 1

                    # After content_planning_node, determine total content nodes
                    if (
                        node_name == "content_planning_node"
                        and total_content_nodes is None
                    ):
                        node_output = data.get("content_planning_node", {})
                        content_order = node_output.get("content_order") or result.get(
                            "content_order", []
                        )
                        total_content_nodes = len(content_order) if content_order else 1
                        # steps per node: search + generate + critic + advance
                        steps_per_node = 4
                        total_content_steps = (
                            1 + total_content_nodes * steps_per_node
                        )  # +1 for planning

                    if node_name == "content_advance_node":
                        content_node_index += 1

                    # Progress: 30% ~ 100% for content phase
                    if total_content_steps and total_content_steps > 0:
                        pct = 0.30 + 0.70 * min(
                            1.0, content_steps_done / total_content_steps
                        )
                    else:
                        pct = 0.30

                    pct_display = int(min(pct, 1.0) * 100)
                    node_info = ""
                    if total_content_nodes and total_content_nodes > 0:
                        current = min(content_node_index + 1, total_content_nodes)
                        node_info = f" — 節點 {current}/{total_content_nodes}"
                    step_text.write(
                        f"**階段 2/2 — 內容生成**{node_info} — {pct_display}%\n\n{label}"
                    )
                    progress_bar.progress(min(pct, 1.0))

            progress_bar.progress(1.0)

            end_time = time.time()
            elapsed = end_time - start_time

            # Debug: check what's in result
            content_map = result.get("content_map", {})
            logger = logging.getLogger(__name__)
            logger.info(
                f"Stream finished. result keys: {list(result.keys())}, "
                f"content_map keys: {list(content_map.keys())}, "
                f"content_map non-empty: {sum(1 for v in content_map.values() if v)}"
            )

            step_text.write(f"✅ 生成完成！耗時 {elapsed:.1f} 秒")

            critics = result.get("critics", [])
            cost_summary = cost_tracker.get_summary()

            st.session_state.generation_metadata = {
                "elapsed_time": elapsed,
                "iterations": len(critics),
                "timestamp": datetime.utcnow(),
                "total_tokens": cost_summary["total_tokens"],
                "total_cost_usd": cost_summary["total_cost_usd"],
                "cleaning_raw_chars": result.get("cleaning_raw_chars"),
                "cleaning_cleaned_chars": result.get("cleaning_cleaned_chars"),
            }

            status_container.update(label="✅ Roadmap 生成成功！", state="complete")

            return result

        except Exception as e:
            st.error(f"❌ 生成失敗: {str(e)}")
            status_container.update(label="❌ 生成失敗", state="error")
            raise e


def handle_status_update(node_id: str, new_status: str):
    """Handle node status update (session state only)."""
    # Update session state
    if node_id not in st.session_state.node_progress:
        st.session_state.node_progress[node_id] = {}
    st.session_state.node_progress[node_id]["status"] = new_status

    if new_status == "in_progress":
        st.session_state.node_progress[node_id]["started_at"] = datetime.utcnow()
    elif new_status == "completed":
        st.session_state.node_progress[node_id]["completed_at"] = datetime.utcnow()
    elif new_status == "not_started":
        st.session_state.node_progress[node_id]["started_at"] = None
        st.session_state.node_progress[node_id]["completed_at"] = None


def render_sidebar():
    """Render sidebar with form, save button, and history."""
    # Preferences form
    question, preferences = render_preferences_form()

    # Generate button
    if st.sidebar.button("🚀 生成 Roadmap", use_container_width=True, type="primary"):
        if not question.strip():
            st.sidebar.error("⚠️ 請輸入學習主題")
        else:
            # Reset state and generate
            reset_roadmap_state()
            st.session_state.is_generating = True

            try:
                # Generate roadmap
                result = generate_roadmap(question, preferences)

                logger = logging.getLogger(__name__)
                logger.info(
                    f"result keys: {list(result.keys())}, "
                    f"content_map keys: {list(result.get('content_map', {}).keys())}"
                )

                # Save full workflow results to session state
                st.session_state.roadmap = result["roadmap"]
                st.session_state.content_map = result.get("content_map", {})
                st.session_state.content_order = result.get("content_order", [])
                st.session_state.content_failed_nodes = result.get(
                    "content_failed_nodes", []
                )
                st.session_state.last_preferences = preferences
                st.session_state.node_progress = {}

                # Auto-save to database
                roadmap = result["roadmap"]
                record_id = save_generation(
                    topic=roadmap.get("topic", "未命名"),
                    language=preferences.language.value,
                    roadmap=roadmap,
                    content_map=st.session_state.content_map,
                    content_order=st.session_state.content_order,
                    content_failed_nodes=st.session_state.content_failed_nodes,
                    generation_time_sec=st.session_state.generation_metadata.get(
                        "elapsed_time"
                    ),
                    iteration_count=st.session_state.generation_metadata.get(
                        "iterations"
                    ),
                    total_tokens=st.session_state.generation_metadata.get(
                        "total_tokens"
                    ),
                    total_cost_usd=st.session_state.generation_metadata.get(
                        "total_cost_usd"
                    ),
                    raw_content_chars=st.session_state.generation_metadata.get(
                        "cleaning_raw_chars"
                    ),
                    cleaned_content_chars=st.session_state.generation_metadata.get(
                        "cleaning_cleaned_chars"
                    ),
                )
                st.session_state.current_record_id = record_id

            except Exception as e:
                st.session_state.error_message = f"❌ 錯誤: {str(e)}"
                logging.getLogger(__name__).exception(
                    "Generation failed after streaming"
                )

            finally:
                st.session_state.is_generating = False
                st.rerun()

    # Display persistent error message (survives st.rerun)
    if st.session_state.error_message:
        st.sidebar.error(st.session_state.error_message)
        st.session_state.error_message = None  # clear after showing once

    if st.session_state.current_record_id:
        st.sidebar.caption("✅ 已自動儲存至資料庫")

    st.sidebar.markdown("---")

    # Display generation metadata if available
    if st.session_state.generation_metadata:
        st.sidebar.header("📊 生成狀態")
        metadata = st.session_state.generation_metadata

        if metadata.get("elapsed_time") is not None:
            st.sidebar.metric("⏱️ 生成耗時", f"{metadata['elapsed_time']:.1f}s")

        if metadata.get("total_tokens"):
            st.sidebar.metric("🪙 Token 用量", f"{metadata['total_tokens']:,}")

        cost = metadata.get("total_cost_usd")
        if cost is not None:
            st.sidebar.metric("💰 估計成本", f"${cost:.4f}")

    st.sidebar.markdown("---")

    # History sidebar
    render_history_sidebar()


@st.dialog("📚 節點詳情", width="large")
def show_node_dialog():
    """Show node detail in a dialog overlay."""
    render_node_detail(
        roadmap_data=st.session_state.roadmap,
        node_id=st.session_state.selected_node,
        node_progress=st.session_state.node_progress,
        on_status_update=handle_status_update,
        content_map=st.session_state.content_map,
        content_failed_nodes=st.session_state.content_failed_nodes,
    )


def render_main_content():
    """Render main content area."""
    st.title("🎓 CourseGen - AI Learning Roadmap Generator")

    if st.session_state.roadmap:
        # Snapshot whether the dialog was rendered in the previous render,
        # then reset so it's only set True if we actually render it this pass.
        was_dialog_open = st.session_state._dialog_was_rendered
        st.session_state._dialog_was_rendered = False

        # DAG full-width rendering
        selected_node = render_roadmap_graph(
            st.session_state.roadmap, st.session_state.node_progress
        )

        # Detect outside-click dismissal:
        # dialog was open last render, selected_node still set,
        # and no internal dialog button triggered this rerun.
        if (
            was_dialog_open
            and st.session_state.selected_node
            and not st.session_state._dialog_internal_action
        ):
            st.session_state._dialog_dismissed = st.session_state.selected_node
            st.session_state.selected_node = None
        st.session_state._dialog_internal_action = False  # reset for next rerun

        # Update selected node if clicked → rerun → trigger dialog
        dismissed = st.session_state._dialog_dismissed
        if selected_node and selected_node != st.session_state.selected_node:
            # Skip if this is the node that was just dismissed (agraph retains selection)
            if selected_node != dismissed:
                st.session_state._dialog_dismissed = (
                    None  # clear — a new node was clicked
                )
                st.session_state.selected_node = selected_node
                st.rerun()

        # Show dialog when a node is selected
        if st.session_state.selected_node:
            st.session_state._dialog_was_rendered = True
            show_node_dialog()

    else:
        # No roadmap loaded - show welcome message
        st.markdown("""
        ## 歡迎使用 CourseGen！

        CourseGen 是一個 AI 驅動的學習路徑生成系統，能夠：

        - 🎯 根據您的需求自動生成結構化的學習路徑
        - 📊 以互動式 DAG 圖表呈現學習路徑
        - ✅ 追蹤您的學習進度

        ### 使用教學

        1. 在左側側邊欄輸入您想學習的主題
        2. 選擇語言
        3. 點擊「生成 Roadmap」按鈕
        4. 等待 30-60 秒，系統會生成個性化的學習路徑

        """)

        st.info("👈 請從左側側邊欄開始")


def main():
    """Main application entry point."""
    # Initialize database
    init_db()

    # Initialize session state
    init_session_state()

    # Render sidebar
    render_sidebar()

    # Render main content
    render_main_content()


if __name__ == "__main__":
    main()
