"""
CourseGen Streamlit UI - Main Application
"""

import html as html_module
import logging
import re
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
from coursegen.ui.utils.log_bridge import install as install_log_bridge, uninstall as uninstall_log_bridge

# Langfuse observability
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

# Load environment variables
load_dotenv()

# Log anchors: regex patterns matched against live log messages to infer the
# current sub-position inside a node. Tuple shape:
#   (pattern, sub_pct, label_or_None, kind)
# kind values:
#   True          — content node entry (search/generate/critic), group(1) = node idx
#   "advance"     — content advance (N/M); group(1) = completed count (1-indexed)
#   False         — rewind anchor (路由 search/generation); sub is set directly
#   "pass"        — roadmap iteration passed
#   "retry_search" / "retry_generation" — roadmap iteration failed, bump iter
#   None          — generic anchor (max-ratchet sub within current unit)
CONTENT_ANCHORS = [
    (re.compile(r"搜尋節點 \[(\d+)\]"), 0.0, "🔎 搜尋節點知識...", True),
    (re.compile(r"Source filtering 保留"), 0.2, "🧹 整合與過濾搜尋結果...", None),
    (re.compile(r"生成節點 \[(\d+)\]"), 0.4, "✍️ 生成教學內容...", True),
    (re.compile(r"審核節點 \[(\d+)\]"), 0.7, "✅ 審核內容品質...", True),
    (re.compile(r"推進: .+ 完成 \((\d+)/\d+\)"), 1.0, "➡️ 前進至下一節點...", "advance"),
    (re.compile(r"路由: search"), 0.0, "🔎 搜尋中（重試）...", False),
    (re.compile(r"路由: generation"), 0.4, "✍️ 生成中（重試）...", False),
]

ROADMAP_ANCHORS = [
    (re.compile(r"知識搜尋開始"), 0.0, "🔍 搜尋相關知識...", None),
    (re.compile(r"Source filtering 保留"), 0.2, "🧹 整合與過濾搜尋結果...", None),
    (re.compile(r"LLM 統整知識中"), 0.3, "🧠 統整知識...", None),
    (re.compile(r"=== Roadmap 生成"), 0.4, "🗺️ 生成學習路徑...", None),
    (re.compile(r"節點清單"), 0.7, "🤖 審核學習路徑...", None),
    (re.compile(r"迭代 \d+/\d+ \| 通過"), 1.0, None, "pass"),
    (re.compile(r"迭代 \d+/\d+ \| 不通過 \| retry_target: search"), 0.0, "🔄 重新搜尋...", "retry_search"),
    (re.compile(r"迭代 \d+/\d+ \| 不通過 \| retry_target: generation"), 0.4, "🔄 重新生成路徑...", "retry_generation"),
]

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
        log_slot = st.empty()
        recent_log_lines: list[str] = []
        start_time = time.time()

        try:
            context = {
                "model_name": os.getenv("MODEL_NAME", "openai/gpt-5.2"),
                "base_url": os.getenv("BASE_URL"),
                "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
                "roadmap_critic_model": os.getenv(
                    "ROADMAP_CRITIC_MODEL", "openai/gpt-5.2"
                ),
                "max_iterations": int(os.getenv("MAX_ITERATIONS", "5")),
                "tavily_api_key": os.getenv("TAVILY_KEY"),
                "content_model": os.getenv(
                    "CONTENT_MODEL", "openai/gpt-5.2"
                ),
                "content_critic_model": os.getenv(
                    "CONTENT_CRITIC_MODEL", "openai/gpt-5.2"
                ),
                "content_max_retries": int(os.getenv("CONTENT_MAX_RETRIES", "5")),
                "cheap_model": os.getenv(
                    "CHEAP_MODEL", "google/gemini-3-flash-preview"
                ),
            }

            st.write(f"📝 主題: {question}")
            st.write(f"🌐 語言: {preferences.language.value}")

            # --- Streaming with anchor-based progress tracking ---
            content_node_index = 0
            total_content_nodes = None
            content_phase_started = False
            current_node_sub = 0.0     # content: sub-position within current node
            roadmap_iter_index = 0     # roadmap iteration count (0-indexed)
            roadmap_sub = 0.0          # roadmap: sub-position within current iteration
            current_pct = 0.0
            current_label = "⏳ 初始化 AI 代理..."

            # Track the latest full state from "values" stream (root namespace only)
            result = {}

            def _recompute_pct() -> float:
                if not content_phase_started:
                    prev_cap = 0.28 * (1 - 0.5 ** roadmap_iter_index)
                    curr_cap = 0.28 * (1 - 0.5 ** (roadmap_iter_index + 1))
                    return prev_cap + (curr_cap - prev_cap) * roadmap_sub
                if total_content_nodes and total_content_nodes > 0:
                    frac = (content_node_index + current_node_sub) / total_content_nodes
                    return 0.30 + 0.70 * min(frac, 1.0)
                return max(current_pct, 0.30)

            def _render() -> None:
                pct_display = int(current_pct * 100)
                if not content_phase_started:
                    header = f"**階段 1/2 — Roadmap 生成** (迭代 {roadmap_iter_index + 1}) — {pct_display}%"
                else:
                    node_info = ""
                    if total_content_nodes and total_content_nodes > 0:
                        current = min(content_node_index + 1, total_content_nodes)
                        node_info = f" — 節點 {current}/{total_content_nodes}"
                    header = f"**階段 2/2 — 內容生成**{node_info} — {pct_display}%"
                step_text.write(f"{header}\n\n{current_label}")
                progress_bar.progress(current_pct)

            langfuse_handler = LangfuseCallbackHandler()
            cost_tracker = CostTracker()

            bridge_handler = install_log_bridge()
            try:
                stream_iter = graph.stream(
                    {
                        "question": question,
                        "user_preferences": preferences.to_prompt_context(),
                    },
                    context=context,
                    stream_mode=["updates", "values", "custom"],
                    subgraphs=True,
                    config={"callbacks": [langfuse_handler, cost_tracker]},
                )
                for chunk in stream_iter:
                    ns, stream_type, data = chunk

                    if stream_type == "values":
                        if not ns:
                            result = data
                        continue

                    if stream_type == "custom":
                        if not isinstance(data, dict) or data.get("kind") != "log":
                            continue
                        raw_message = str(data.get("message", "")).strip()
                        if not raw_message:
                            continue
                        display_message = (
                            raw_message if len(raw_message) <= 200
                            else raw_message[:200] + "…"
                        )
                        recent_log_lines.append(f"▸ {display_message}")
                        if len(recent_log_lines) > 100:
                            recent_log_lines = recent_log_lines[-100:]
                        # Reverse DOM order + flex column-reverse keeps scroll
                        # anchored at the visual bottom without JS, so no iframe
                        # blink on every update.
                        line_divs = "".join(
                            f"<div>{html_module.escape(line)}</div>"
                            for line in reversed(recent_log_lines)
                        )
                        container_style = (
                            "height:216px;overflow-y:auto;"
                            "display:flex;flex-direction:column-reverse;"
                            "padding:10px 14px;"
                            "background:#f5f5f7;color:#374151;"
                            "border:1px solid #e5e7eb;border-radius:6px;"
                            "font-family:'Source Code Pro',ui-monospace,"
                            "SFMono-Regular,monospace;font-size:12px;"
                            "line-height:1.6;white-space:pre-wrap;"
                        )
                        log_slot.markdown(
                            f'<div style="{container_style}">{line_divs}</div>',
                            unsafe_allow_html=True,
                        )

                        anchors = (
                            CONTENT_ANCHORS if content_phase_started else ROADMAP_ANCHORS
                        )
                        allow_rewind = False
                        for pattern, sub, label, kind in anchors:
                            m = pattern.search(raw_message)
                            if not m:
                                continue
                            if label is not None:
                                current_label = label
                            if not content_phase_started:
                                if kind == "pass":
                                    roadmap_sub = 1.0
                                elif kind in ("retry_search", "retry_generation"):
                                    roadmap_iter_index += 1
                                    roadmap_sub = sub
                                    allow_rewind = True
                                else:
                                    roadmap_sub = max(roadmap_sub, sub)
                            else:
                                if kind is True and m.groups():
                                    parsed_idx = int(m.group(1))
                                    if parsed_idx != content_node_index:
                                        content_node_index = parsed_idx
                                        current_node_sub = 0.0
                                    current_node_sub = max(current_node_sub, sub)
                                elif kind == "advance":
                                    content_node_index = int(m.group(1)) - 1
                                    current_node_sub = 1.0
                                elif kind is False:
                                    current_node_sub = sub
                                    allow_rewind = True
                                else:
                                    current_node_sub = max(current_node_sub, sub)
                            break

                        new_pct = _recompute_pct()
                        if allow_rewind:
                            current_pct = new_pct
                        else:
                            current_pct = max(current_pct, min(new_pct, 1.0))
                        _render()
                        continue

                    if stream_type != "updates":
                        continue

                    node_name = next(iter(data.keys()), None)
                    if node_name is None:
                        continue

                    # Updates are only used to snap into content phase and learn
                    # how many content nodes we'll generate; all intra-phase
                    # progress is anchor-driven from the custom log stream.
                    if (
                        node_name == "content_planning_node"
                        and not content_phase_started
                    ):
                        content_phase_started = True
                        node_output = data.get("content_planning_node", {})
                        content_order = node_output.get("content_order") or result.get(
                            "content_order", []
                        )
                        total_content_nodes = (
                            len(content_order) if content_order else 1
                        )
                        content_node_index = 0
                        current_node_sub = 0.0
                        current_pct = max(current_pct, 0.30)
                        _render()
            finally:
                uninstall_log_bridge(bridge_handler)

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
