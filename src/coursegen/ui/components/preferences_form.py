"""
User preferences form component for Streamlit sidebar.
"""

import streamlit as st

from coursegen.schemas import Language, UserPreferences
from coursegen.ui.utils.browser_storage import persist_credentials
from coursegen.ui.utils.session_state import reset_roadmap_state

CONTENT_MODEL_PRESETS = [
    "openai/gpt-5.4",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3.1-pro-preview",
    "google/gemini-3-flash-preview",
    "Custom...",
]

HELPER_MODEL_PRESETS = [
    "google/gemini-3-flash-preview",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-5-mini",
    "Custom...",
]


def _model_selector(
    label: str,
    state_key: str,
    presets: list[str],
    help_text: str,
) -> None:
    """
    Render a model selectbox + Custom text input fallback.

    Persistence runs only via on_change callbacks (fires once per user change),
    never synchronously inside render — otherwise calling persist_credentials
    twice in one render creates duplicate component keys.
    """
    current = st.session_state.get(state_key, presets[0])
    is_custom = current not in presets[:-1]
    select_index = len(presets) - 1 if is_custom else presets.index(current)

    select_widget_key = f"_select_{state_key}"
    custom_widget_key = f"_custom_{state_key}"

    def _on_select_change():
        new_choice = st.session_state[select_widget_key]
        if new_choice != "Custom...":
            st.session_state[state_key] = new_choice
            persist_credentials()
        # If Custom, keep current state_key value as starting point for editing

    def _on_custom_change():
        st.session_state[state_key] = st.session_state.get(custom_widget_key, "")
        persist_credentials()

    choice = st.sidebar.selectbox(
        label,
        options=presets,
        index=select_index,
        help=help_text,
        key=select_widget_key,
        on_change=_on_select_change,
    )

    if choice == "Custom...":
        st.sidebar.text_input(
            f"{label} — 自訂模型 ID",
            value=current if is_custom else "",
            placeholder="例如 openai/gpt-5-mini",
            key=custom_widget_key,
            on_change=_on_custom_change,
        )


def _do_logout() -> None:
    """Revoke the active session token and reset auth-related state."""
    from coursegen.db.auth import revoke_session
    from coursegen.db.database import get_session
    token = st.session_state.get("auth_token", "")
    if token:
        with get_session() as session:
            revoke_session(session, token)
    st.session_state.auth_token = ""
    st.session_state.authenticated = False
    st.session_state.read_only = False
    # Clear any loaded roadmap so the next user starts with an empty workspace
    # instead of inheriting the previous session's display state.
    reset_roadmap_state()
    # nickname intentionally left in state so the login screen pre-fills the
    # last user — convenience for personal self-host
    persist_credentials()


def render_identity_and_api_form() -> None:
    """
    Render the identity (logged-in badge + logout) + API settings block.

    Writes directly to st.session_state — no return value.
    """
    st.sidebar.header("👤 你的身份")

    cols = st.sidebar.columns([1, 1])
    with cols[0]:
        if st.session_state.read_only:
            st.markdown(f"**{st.session_state.nickname}** 🎓 demo")
        else:
            st.markdown(f"**{st.session_state.nickname}**")
    with cols[1]:
        if st.button("登出", key="_logout_btn", use_container_width=True):
            _do_logout()
            st.rerun()

    if st.session_state.read_only:
        st.sidebar.caption("ℹ️ Demo 模式 — 可看可載入，但不能新增 / 刪除")

    with st.sidebar.expander("🔑 API 設定", expanded=False):
        st.text_input(
            "OpenRouter API Key",
            type="password",
            key="api_key",
            placeholder="sk-or-v1-...",
            help="從 https://openrouter.ai 取得。儲存在你的瀏覽器，不會上傳到 server。",
            on_change=persist_credentials,
        )
        st.text_input(
            "Tavily Key",
            type="password",
            key="tavily_key",
            placeholder="tvly-...",
            help="從 https://tavily.com 取得。必填 — 用於知識搜尋與內容生成的來源依據。",
            on_change=persist_credentials,
        )
        st.markdown("---")
        _model_selector(
            "內容生成模型",
            state_key="content_model",
            presets=CONTENT_MODEL_PRESETS,
            help_text="用於生成 roadmap 結構與每個節點的教學內容，影響輸出品質，建議選高品質模型",
        )
        _model_selector(
            "輔助任務模型",
            state_key="helper_model",
            presets=HELPER_MODEL_PRESETS,
            help_text="用於搜尋查詢生成、結果過濾、節點 AI 助教等簡單任務，可選便宜模型省成本",
        )


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
        placeholder="例如：如何學習 Harness Engineering",
        help=(
            "輸入你想學的主題，一個關鍵詞或一句話都可以，系統會自動從中**擷取核心關鍵字**去搜尋資料。\n\n"
            "✅ 例：「Harness Engineering」、「桌球殺球技巧」、「React 入門」\n\n"
            "💡 版本號或專有名詞很重要的話請寫出來，會被完整保留"
            "（例：「Minecraft 1.21.11」不會被簡化成 1.21）。"
        ),
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
