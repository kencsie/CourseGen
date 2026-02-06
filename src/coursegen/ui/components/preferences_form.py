"""
User preferences form component for Streamlit sidebar.
"""
import streamlit as st
from coursegen.schemas import UserPreferences, DifficultyLevel, LearningGoal, Language


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
    default_difficulty_idx = 0
    default_goal_idx = 1
    default_language_idx = 0

    if prefill_data:
        # Pre-fill values from example
        default_question = prefill_data.get("display_name", "")

        # Map difficulty
        difficulty_map = {
            "BEGINNER": 0,
            "INTERMEDIATE": 1,
            "ADVANCED": 2
        }
        default_difficulty_idx = difficulty_map.get(prefill_data.get("difficulty", "BEGINNER"), 0)

        # Map goal
        goal_map = {
            "QUICK_START": 0,
            "DEEP_DIVE": 1
        }
        default_goal_idx = goal_map.get(prefill_data.get("goal", "DEEP_DIVE"), 1)

        # Map language
        language_map = {
            "ZH_TW": 0,
            "EN": 1
        }
        default_language_idx = language_map.get(prefill_data.get("language", "ZH_TW"), 0)

        # Clear prefill after use
        st.session_state.prefill_from_example = None

    # Learning topic input
    question = st.sidebar.text_input(
        "學習主題",
        value=default_question,
        placeholder="例如：如何學習 React.js？",
        help="請輸入您想學習的主題或技術",
    )

    # Difficulty level
    difficulty_options = {
        "新手 - 從零開始": DifficultyLevel.BEGINNER,
        "有經驗 - 尋求進階": DifficultyLevel.INTERMEDIATE,
        "專家 - 查漏補缺": DifficultyLevel.ADVANCED,
    }

    selected_difficulty = st.sidebar.selectbox(
        "難度等級",
        options=list(difficulty_options.keys()),
        index=default_difficulty_idx,
        help="選擇您當前的知識水平",
    )
    difficulty = difficulty_options[selected_difficulty]

    # Learning goal
    goal_options = {
        "快速入門/速成": LearningGoal.QUICK_START,
        "深入精通/底層原理": LearningGoal.DEEP_DIVE,
    }

    selected_goal = st.sidebar.selectbox(
        "學習目標",
        options=list(goal_options.keys()),
        index=default_goal_idx,
        help="選擇您的學習目標",
    )
    goal = goal_options[selected_goal]

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

    # Create UserPreferences object
    preferences = UserPreferences(
        level=difficulty,
        goal=goal,
        language=language,
    )

    return question, preferences
