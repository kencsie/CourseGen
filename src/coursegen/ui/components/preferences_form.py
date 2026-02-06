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

    # Learning topic input
    question = st.sidebar.text_input(
        "學習主題",
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
        index=0,
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
        index=1,  # Default to DEEP_DIVE
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
        index=0,  # Default to ZH_TW
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
