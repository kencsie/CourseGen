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

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="CourseGen - AI Learning Roadmap",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def generate_roadmap(question: str, preferences: UserPreferences):
    """
    Generate roadmap using LangGraph workflow.

    Args:
        question: Learning topic/question
        preferences: UserPreferences object

    Returns:
        Result dictionary from graph.invoke()
    """
    # Show progress
    status_container = st.status("🚀 正在生成 Roadmap...", expanded=True)

    with status_container:
        st.write("⏳ 初始化 AI 代理...")
        start_time = time.time()

        try:
            # Prepare context
            context = {
                "model_name": os.getenv("MODEL_NAME", "google/gemini-3-flash-preview"),
                "base_url": os.getenv("BASE_URL"),
                "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
                "critic_1_model": os.getenv("CRITIC_1_MODEL", "anthropic/claude-4.5-sonnet"),
                "critic_2_model": os.getenv("CRITIC_2_MODEL", "openai/gpt-4o"),
                "critic_3_model": os.getenv("CRITIC_3_MODEL", "google/gemini-3-flash-preview"),
                "max_iterations": int(os.getenv("MAX_ITERATIONS", "3")),
                "tavily_api_key": os.getenv("TAVILY_KEY"),
                "content_model": os.getenv("CONTENT_MODEL", "google/gemini-3-flash-preview"),
                "content_max_retries": int(os.getenv("CONTENT_MAX_RETRIES", "2")),
            }

            st.write("🤖 開始生成 roadmap...")
            st.write(f"📝 主題: {question}")
            st.write(f"🎯 難度: {preferences.level.name}")
            st.write(f"🎨 目標: {preferences.goal.name}")
            st.write(f"🌐 語言: {preferences.language.value}")

            # Invoke graph
            result = graph.invoke(
                {
                    "question": question,
                    "user_preferences": preferences.to_prompt_context(),
                },
                context=context,
            )

            end_time = time.time()
            elapsed = end_time - start_time

            # Check if roadmap is valid
            if not result.get("roadmap_is_valid", False):
                st.error("⚠️ Roadmap 驗證失敗，但仍會顯示結果")

            st.write(f"✅ Roadmap 生成完成！")
            st.write(f"⏱️ 耗時: {elapsed:.1f} 秒")

            # Count iterations (if available in result)
            critics = result.get("critics", [])
            st.write(f"🔄 評論迭代次數: {len(critics)}")

            # Store metadata
            st.session_state.generation_metadata = {
                "elapsed_time": elapsed,
                "iterations": len(critics),
                "timestamp": datetime.utcnow(),
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
                    difficulty=preferences.level.name,
                    goal=preferences.goal.name,
                    language=preferences.language.value,
                    roadmap=roadmap,
                    content_map=st.session_state.content_map,
                    content_order=st.session_state.content_order,
                    content_failed_nodes=st.session_state.content_failed_nodes,
                    generation_time_sec=st.session_state.generation_metadata.get("elapsed_time"),
                    iteration_count=st.session_state.generation_metadata.get("iterations"),
                )
                st.session_state.current_record_id = record_id

                st.sidebar.success("✅ Roadmap 已生成並儲存")

            except Exception as e:
                st.sidebar.error(f"❌ 錯誤: {str(e)}")

            finally:
                st.session_state.is_generating = False
                st.rerun()

    if st.session_state.current_record_id:
        st.sidebar.caption("✅ 已自動儲存至資料庫")

    st.sidebar.markdown("---")

    # Display generation metadata if available
    if st.session_state.generation_metadata:
        st.sidebar.header("📊 生成狀態")
        metadata = st.session_state.generation_metadata

        if metadata.get("elapsed_time") is not None:
            st.sidebar.metric("⏱️ 生成耗時", f"{metadata['elapsed_time']:.1f}s")

        if metadata.get("iterations") is not None:
            st.sidebar.metric("🔄 迭代次數", metadata["iterations"])

        if st.session_state.roadmap:
            # Calculate completion
            total = len(st.session_state.roadmap.get("nodes", []))
            completed = sum(
                1 for prog in st.session_state.node_progress.values()
                if prog.get("status") == "completed"
            )
            st.sidebar.metric("✅ 完成進度", f"{completed}/{total}")

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
        # DAG full-width rendering
        selected_node = render_roadmap_graph(
            st.session_state.roadmap,
            st.session_state.node_progress
        )

        # Update selected node if clicked → rerun → trigger dialog
        if selected_node and selected_node != st.session_state.selected_node:
            st.session_state.selected_node = selected_node
            st.rerun()

        # Show dialog when a node is selected
        if st.session_state.selected_node:
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
        2. 選擇難度等級、學習目標和語言
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
