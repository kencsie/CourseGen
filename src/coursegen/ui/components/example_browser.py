"""Example browser component for displaying roadmap examples."""

import streamlit as st
from typing import Optional

from ..utils.example_loader import load_metadata, filter_examples


def render_example_browser() -> Optional[str]:
    """
    Render example browser with cards and filters.
    Returns: selected example_id or None
    """
    st.markdown("### 📚 探索範例學習路徑")
    st.markdown("瀏覽由 AI 生成的優質學習路徑範例，快速了解系統能力")

    # Load metadata
    metadata = load_metadata()
    examples = metadata.get("examples", [])

    if not examples:
        st.warning("目前沒有可用的範例路徑")
        return None

    # Extract unique values for filters
    all_difficulties = list(set(ex.get("difficulty", "") for ex in examples))
    all_languages = list(set(ex.get("language", "") for ex in examples))
    all_tags = list(set(tag for ex in examples for tag in ex.get("tags", [])))

    # Filters section
    st.markdown("---")
    col1, col2, col3, col4 = st.columns([2, 2, 3, 1])

    with col1:
        difficulty_filter = st.selectbox(
            "難度",
            ["全部"] + all_difficulties,
            key="example_difficulty_filter"
        )

    with col2:
        language_filter = st.selectbox(
            "語言",
            ["全部"] + all_languages,
            key="example_language_filter"
        )

    with col3:
        tag_filter = st.multiselect(
            "標籤",
            all_tags,
            key="example_tag_filter"
        )

    with col4:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        if st.button("清除篩選", key="clear_filters"):
            st.session_state.example_difficulty_filter = "全部"
            st.session_state.example_language_filter = "全部"
            st.session_state.example_tag_filter = []
            st.rerun()

    # Apply filters
    filtered_examples = filter_examples(
        metadata,
        difficulty=difficulty_filter if difficulty_filter != "全部" else None,
        language=language_filter if language_filter != "全部" else None,
        tags=tag_filter if tag_filter else None
    )

    st.markdown("---")

    # Show filtered count
    if len(filtered_examples) < len(examples):
        st.info(f"顯示 {len(filtered_examples)} / {len(examples)} 個範例")

    # Empty state
    if not filtered_examples:
        st.warning("沒有符合篩選條件的範例")
        return None

    # Render example cards in a grid (3 columns)
    num_cols = 3
    cols = st.columns(num_cols)

    selected_id = None

    for idx, example in enumerate(filtered_examples):
        col = cols[idx % num_cols]

        with col:
            # Card container
            with st.container():
                # Icon mapping
                icon_map = {
                    "React": "⚛️",
                    "Python": "🐍",
                    "JavaScript": "💛",
                    "前端": "🎨",
                    "後端": "⚙️",
                    "全端": "🌐",
                    "Data Science": "📊",
                    "Machine Learning": "🤖"
                }
                # Find first matching icon or use default
                icon = "📘"
                for tag in example.get("tags", []):
                    if tag in icon_map:
                        icon = icon_map[tag]
                        break

                # Title with icon
                st.markdown(f"## {icon} {example['display_name']}")

                # Description
                st.markdown(f"*{example['description']}*")

                # Badges row
                difficulty_colors = {
                    "BEGINNER": "🟢",
                    "INTERMEDIATE": "🟡",
                    "ADVANCED": "🔴"
                }
                language_labels = {
                    "ZH_TW": "🔵 繁中",
                    "EN": "🔴 英文",
                    "ZH_CN": "🟢 簡中"
                }

                difficulty_badge = difficulty_colors.get(example.get("difficulty", ""), "⚪")
                language_badge = language_labels.get(example.get("language", ""), "")

                st.markdown(f"{difficulty_badge} {language_badge}")

                # Stats
                node_count = example.get("node_count", 0)
                estimated_hours = node_count * 4  # Rough estimate
                st.markdown(f"**{node_count}** 個節點 · 約 **{estimated_hours}** 小時")

                # Tags
                tags = example.get("tags", [])
                if tags:
                    tag_html = " ".join([f'<span style="background-color: #e0e0e0; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-right: 4px;">{tag}</span>' for tag in tags])
                    st.markdown(tag_html, unsafe_allow_html=True)

                st.markdown("")  # Spacing

                # View button
                if st.button("查看範例", key=f"view_{example['id']}", use_container_width=True):
                    selected_id = example['id']

                st.markdown("---")

    return selected_id


def get_difficulty_label(difficulty: str) -> str:
    """Convert difficulty code to display label."""
    labels = {
        "BEGINNER": "新手",
        "INTERMEDIATE": "中級",
        "ADVANCED": "進階"
    }
    return labels.get(difficulty, difficulty)


def get_language_label(language: str) -> str:
    """Convert language code to display label."""
    labels = {
        "ZH_TW": "繁體中文",
        "EN": "English",
        "ZH_CN": "简体中文"
    }
    return labels.get(language, language)
