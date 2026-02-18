"""
Content renderers for 5 node types.
"""
import streamlit as st
import pandas as pd


def render_prerequisite(content: dict) -> None:
    """Render prerequisite node content."""
    st.markdown(content.get("overview", ""))

    st.markdown("#### 自我檢核清單")
    for item in content.get("checklist", []):
        st.markdown(f"- {item}")

    remediation = content.get("remediation", [])
    if remediation:
        with st.expander("📖 補救資源與建議"):
            for item in remediation:
                st.markdown(f"- {item}")


def render_concept(content: dict) -> None:
    """Render concept node content."""
    st.markdown(content.get("explanation", ""))

    key_points = content.get("key_points", [])
    if key_points:
        st.markdown("#### 關鍵要點")
        for point in key_points:
            st.markdown(f"- {point}")

    examples = content.get("examples", [])
    if examples:
        with st.expander("💡 範例"):
            for i, example in enumerate(examples, 1):
                st.markdown(f"**範例 {i}**")
                st.markdown(example)
                if i < len(examples):
                    st.markdown("---")


def render_pitfall(content: dict) -> None:
    """Render pitfall node content."""
    for pitfall in content.get("pitfalls", []):
        st.warning(pitfall)

    warning_signs = content.get("warning_signs", [])
    if warning_signs:
        st.markdown("#### 警示信號")
        for sign in warning_signs:
            st.error(sign)


def render_comparison(content: dict) -> None:
    """Render comparison node content."""
    subject_a = content.get("subject_a", "A")
    subject_b = content.get("subject_b", "B")

    table = content.get("comparison_table", [])
    if table:
        df = pd.DataFrame(table)
        # Rename columns for display
        column_map = {"dimension": "比較面向", "a": subject_a, "b": subject_b}
        df = df.rename(columns=column_map)
        st.dataframe(df, use_container_width=True, hide_index=True)

    when_to_use = content.get("when_to_use", "")
    if when_to_use:
        st.info(f"**何時使用？** {when_to_use}")


def render_practice(content: dict) -> None:
    """Render practice node content."""
    st.markdown(f"**目標：** {content.get('objective', '')}")

    tasks = content.get("tasks", [])
    if tasks:
        st.markdown("#### 任務列表")
        for i, task in enumerate(tasks, 1):
            st.markdown(f"{i}. {task}")

    expected = content.get("expected_output", "")
    if expected:
        st.success(f"**預期成果：** {expected}")

    hints = content.get("hints", [])
    if hints:
        with st.expander("💡 提示（卡住時再看）"):
            for hint in hints:
                st.markdown(f"- {hint}")


# Dispatcher: node type → renderer function
_RENDERERS = {
    "prerequisite": render_prerequisite,
    "concept": render_concept,
    "pitfall": render_pitfall,
    "comparison": render_comparison,
    "practice": render_practice,
}


def render_content(node_type: str, content: dict) -> None:
    """Dispatch to the appropriate renderer based on node type."""
    renderer = _RENDERERS.get(node_type)
    if renderer and content:
        st.markdown("---")
        st.markdown("### 📖 教學內容")
        renderer(content)
    elif not content:
        st.caption("尚未生成教學內容")
