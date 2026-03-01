"""
User preferences form component for Streamlit sidebar.
"""

import streamlit as st
from coursegen.schemas import UserPreferences, Language


def render_preferences_form() -> tuple[str, UserPreferences]:
    """
    Render user preferences input form in sidebar.

    Returns:
        tuple: (question: str, preferences: UserPreferences)
    """
    st.sidebar.header("📚 新增 Roadmap")

    # Check if we need to prefill from example
    prefill_data = st.session_state.get("prefill_from_example")
    default_question = ""
    default_language_idx = 0

    if prefill_data:
        default_question = prefill_data.get("display_name", "")

        language_map = {"ZH_TW": 0, "EN": 1}
        default_language_idx = language_map.get(
            prefill_data.get("language", "ZH_TW"), 0
        )

        # Clear prefill after use
        st.session_state.prefill_from_example = None

    # Learning topic input
    question = st.sidebar.text_input(
        "學習主題",
        value=default_question,
        placeholder="例如：如何學習 React.js？",
        help="請輸入您想學習的主題或技術",
    )

    # Language preference
    language_options = {
        "繁體中文": Language.ZH_TW,
        "English": Language.EN,
    }

    selected_language = st.sidebar.selectbox(
        "語言",
        options=list(language_options.keys()),
        index=default_language_idx,
        help="選擇 roadmap 生成的語言",
    )
    language = language_options[selected_language]

    preferences = UserPreferences(language=language)

    return question, preferences
