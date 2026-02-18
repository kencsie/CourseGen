"""
CourseGen Streamlit UI - Main Application
"""
import streamlit as st
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# Import workflow
from coursegen.workflows.basic import graph

# Import schemas
from coursegen.schemas import UserPreferences

# Import UI components
from coursegen.ui.components.preferences_form import render_preferences_form
from coursegen.ui.components.roadmap_visualizer import render_roadmap_graph
from coursegen.ui.components.node_detail import render_node_detail, render_no_selection_message
from coursegen.ui.components.example_browser import render_example_browser
from coursegen.ui.components.example_banner import render_example_banner

# Import utilities
from coursegen.ui.utils.session_state import init_session_state, reset_roadmap_state
from coursegen.ui.utils.example_loader import load_example_roadmap, get_example_metadata

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
    """Render sidebar with form (simplified - no database)."""
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

                # Save to session state only
                st.session_state.roadmap = result["roadmap"]
                st.session_state.node_progress = {}

                st.sidebar.success("✅ Roadmap 已生成")

            except Exception as e:
                st.sidebar.error(f"❌ 錯誤: {str(e)}")

            finally:
                st.session_state.is_generating = False
                st.rerun()

    st.sidebar.markdown("---")

    # Session warning
    st.sidebar.warning("⚠️ **注意**：資料僅在當前瀏覽器會話有效，關閉瀏覽器後將消失")

    st.sidebar.markdown("---")

    # Display generation metadata if available
    if st.session_state.generation_metadata:
        st.sidebar.header("📊 生成狀態")
        metadata = st.session_state.generation_metadata

        if "elapsed_time" in metadata:
            st.sidebar.metric("⏱️ 生成耗時", f"{metadata['elapsed_time']:.1f}s")

        if "iterations" in metadata:
            st.sidebar.metric("🔄 迭代次數", metadata["iterations"])

        if st.session_state.roadmap:
            # Calculate completion
            total = len(st.session_state.roadmap.get("nodes", []))
            completed = sum(
                1 for prog in st.session_state.node_progress.values()
                if prog.get("status") == "completed"
            )
            st.sidebar.metric("✅ 完成進度", f"{completed}/{total}")


def render_main_content():
    """Render main content area."""
    st.title("🎓 CourseGen - AI Learning Roadmap Generator")

    # Create tabs
    tab1, tab2 = st.tabs(["🚀 生成 Roadmap", "📚 範例 Roadmaps"])

    with tab1:
        # Tab 1: Generated roadmaps
        if st.session_state.roadmap and not st.session_state.is_example_mode:
            # Roadmap loaded - show visualization and details
            col1, col2 = st.columns([2, 1])

            with col1:
                # Render roadmap graph
                selected_node = render_roadmap_graph(
                    st.session_state.roadmap,
                    st.session_state.node_progress
                )

                # Update selected node if clicked
                if selected_node and selected_node != st.session_state.selected_node:
                    st.session_state.selected_node = selected_node
                    st.rerun()

            with col2:
                # Render node detail or instructions
                if st.session_state.selected_node:
                    render_node_detail(
                        roadmap_data=st.session_state.roadmap,
                        node_id=st.session_state.selected_node,
                        node_progress=st.session_state.node_progress,
                        on_status_update=handle_status_update,
                    )
                else:
                    render_no_selection_message()

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

    with tab2:
        # Tab 2: Example roadmaps
        if st.session_state.is_example_mode and st.session_state.roadmap:
            # Show example banner
            example_metadata = get_example_metadata(st.session_state.current_example_id)

            if example_metadata:
                action = render_example_banner(example_metadata)

                if action == "return":
                    # Clear example state, return to browser
                    st.session_state.is_example_mode = False
                    st.session_state.roadmap = None
                    st.session_state.current_example_id = None
                    st.session_state.selected_node = None
                    st.rerun()

                elif action == "generate":
                    # Switch to tab 1, pre-fill form
                    st.session_state.prefill_from_example = example_metadata
                    st.session_state.is_example_mode = False
                    st.session_state.roadmap = None
                    st.session_state.current_example_id = None
                    st.session_state.selected_node = None
                    st.info("💡 請切換到「生成 Roadmap」標籤頁，表單已預先填入範例資訊")
                    st.rerun()

            # Show example visualization and detail
            col1, col2 = st.columns([2, 1])

            with col1:
                # Render roadmap graph
                selected_node = render_roadmap_graph(
                    st.session_state.roadmap,
                    st.session_state.node_progress
                )

                # Update selected node if clicked
                if selected_node and selected_node != st.session_state.selected_node:
                    st.session_state.selected_node = selected_node
                    st.rerun()

            with col2:
                # Render node detail or instructions
                if st.session_state.selected_node:
                    render_node_detail(
                        roadmap_data=st.session_state.roadmap,
                        node_id=st.session_state.selected_node,
                        node_progress=st.session_state.node_progress,
                        on_status_update=handle_status_update,
                    )
                else:
                    render_no_selection_message()

        else:
            # Show example browser
            selected_id = render_example_browser()

            if selected_id:
                # Load example into session state
                example_data = load_example_roadmap(selected_id)

                if example_data:
                    st.session_state.roadmap = example_data
                    st.session_state.is_example_mode = True
                    st.session_state.current_example_id = selected_id
                    st.session_state.node_progress = {}
                    st.session_state.selected_node = None
                    st.rerun()
                else:
                    st.error(f"❌ 無法載入範例: {selected_id}")


def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()

    # Render sidebar
    render_sidebar()

    # Render main content
    render_main_content()


if __name__ == "__main__":
    main()
