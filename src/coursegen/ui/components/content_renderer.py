"""
Content renderers for 5 node types.
"""
import re

import streamlit as st
import pandas as pd


_SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _style_citations(text: str) -> str:
    """將 [1] 等引用標記轉為 Unicode 上標，例如 [1] → ⁽¹⁾。"""
    return re.sub(
        r"\[(\d+)\]",
        lambda m: f"⁽{m.group(1).translate(_SUPERSCRIPT_DIGITS)}⁾",
        text,
    )


def _render_sources(sources: list[dict]) -> None:
    """在內容底部渲染來源清單。"""
    if not sources:
        return
    st.markdown("---")
    st.markdown("#### 參考來源")
    for i, src in enumerate(sources, 1):
        title = src.get("title", "未知來源")
        url = src.get("url", "")
        st.markdown(f"[{i}] [{title}]({url})")


def render_prerequisite(content: dict) -> None:
    """Render prerequisite node content."""
    st.markdown(_style_citations(content.get("overview", "")))

    st.markdown("#### 自我檢核清單")
    for item in content.get("checklist", []):
        st.markdown(f"- {_style_citations(item)}")

    remediation = content.get("remediation", [])
    if remediation:
        with st.expander("📖 補救資源與建議"):
            for item in remediation:
                st.markdown(f"- {_style_citations(item)}")


def render_concept(content: dict) -> None:
    """Render concept node content."""
    st.markdown(_style_citations(content.get("explanation", "")))

    key_points = content.get("key_points", [])
    if key_points:
        st.markdown("#### 關鍵要點")
        for point in key_points:
            st.markdown(f"- {_style_citations(point)}")

    examples = content.get("examples", [])
    if examples:
        with st.expander("💡 範例"):
            for i, example in enumerate(examples, 1):
                st.markdown(f"**範例 {i}**")
                st.markdown(_style_citations(example))
                if i < len(examples):
                    st.markdown("---")


def render_pitfall(content: dict) -> None:
    """Render pitfall node content."""
    for pitfall in content.get("pitfalls", []):
        st.warning(_style_citations(pitfall), icon=None)

    warning_signs = content.get("warning_signs", [])
    if warning_signs:
        st.markdown("#### 警示信號")
        for sign in warning_signs:
            st.error(_style_citations(sign), icon=None)


def render_comparison(content: dict) -> None:
    """Render comparison node content."""
    subject_a = content.get("subject_a", "A")
    subject_b = content.get("subject_b", "B")

    table = content.get("comparison_table", [])
    if table:
        styled_table = [
            {k: _style_citations(v) if isinstance(v, str) else v for k, v in row.items()}
            for row in table
        ]
        df = pd.DataFrame(styled_table)
        # Rename columns for display
        column_map = {"dimension": "比較面向", "a": subject_a, "b": subject_b}
        df = df.rename(columns=column_map)
        st.dataframe(df, use_container_width=True, hide_index=True)

    when_to_use = content.get("when_to_use", "")
    if when_to_use:
        st.info(f"**何時使用？** {_style_citations(when_to_use)}")


def render_practice(content: dict) -> None:
    """Render practice node content."""
    st.markdown(f"**目標：** {_style_citations(content.get('objective', ''))}")

    tasks = content.get("tasks", [])
    if tasks:
        st.markdown("#### 任務列表")
        for i, task in enumerate(tasks, 1):
            st.markdown(f"{i}. {_style_citations(task)}")

    expected = content.get("expected_output", "")
    if expected:
        st.success(f"**預期成果：** {_style_citations(expected)}")

    hints = content.get("hints", [])
    if hints:
        with st.expander("💡 提示（卡住時再看）"):
            for hint in hints:
                st.markdown(f"- {_style_citations(hint)}")


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
        _render_sources(content.get("sources", []))
    elif not content:
        st.caption("尚未生成教學內容")
