"""Login / first-time registration screen.

Shown by app.main() when session is not authenticated. Three branches:
  1. nickname == 'example' → blocked in form; demo button bypasses password
  2. nickname exists in users table → verify password
  3. nickname new → first submit reveals a confirm field, second submit
                    validates the match and registers
"""
from __future__ import annotations

import streamlit as st

from coursegen.db.auth import (
    EXAMPLE_USER_ID,
    create_session,
    register_user,
    user_exists,
    verify_password,
)
from coursegen.db.database import get_session
from coursegen.ui.utils.browser_storage import persist_credentials


def render_login_screen() -> None:
    # Centered card layout: 1-2-1 columns with the form constrained to the
    # middle column — Streamlit's standard "narrow centered" pattern.
    _, mid, _ = st.columns([1, 2, 1])

    with mid:
        st.markdown(
            "<h1 style='text-align:center;'>🎓 CourseGen</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#6b7280;'>"
            "歡迎！輸入暱稱與密碼開始使用。<br>"
            "首次使用這個暱稱會引導你設定密碼。"
            "</p>",
            unsafe_allow_html=True,
        )
        st.write("")

        # The confirm field appears only after a first submit detects the
        # nickname as new — we can't decide this during the very first
        # render (DB check needs a committed nickname value), and toggling
        # the field inline during the same submit-rerun would show it as
        # empty and immediately reject with a mismatch error.
        needs_confirm = st.session_state.get("_login_needs_confirm", False)

        with st.container(border=True):
            with st.form("login_form"):
                nickname = st.text_input(
                    "暱稱",
                    value=st.session_state.get("nickname", ""),
                    key="_login_nickname",
                )
                password = st.text_input(
                    "密碼", type="password", key="_login_password"
                )

                password_confirm = None
                if needs_confirm:
                    st.info("👋 偵測到這是新暱稱 — 請再次輸入相同密碼確認。")
                    password_confirm = st.text_input(
                        "確認密碼",
                        type="password",
                        key="_login_password_confirm",
                    )

                submitted = st.form_submit_button(
                    "繼續", type="primary", use_container_width=True
                )

            if submitted:
                _handle_submit(nickname.strip(), password, password_confirm)

        st.markdown(
            "<p style='text-align:center;color:#9ca3af;margin:1rem 0;'>"
            "──────── 或 ────────</p>",
            unsafe_allow_html=True,
        )

        if st.button(
            "👀 以 example 模式瀏覽（只能看，不能改）",
            use_container_width=True,
        ):
            st.session_state.nickname = EXAMPLE_USER_ID
            st.session_state.authenticated = True
            st.session_state.read_only = True
            st.rerun()


def _handle_submit(
    nickname: str, password: str, password_confirm: str | None
) -> None:
    if not nickname:
        st.error("⚠️ 請輸入暱稱")
        return
    if not password:
        st.error("⚠️ 請輸入密碼")
        return

    if nickname == EXAMPLE_USER_ID:
        st.error("⚠️ example 是 demo 帳號，請點下方「以 example 模式瀏覽」按鈕進入")
        return

    with get_session() as session:
        exists = user_exists(session, nickname)

    if exists:
        # Existing user — verify password and clear any stale confirm-field
        # state left over from a prior new-user attempt (e.g. user changed
        # the nickname mid-flow to an existing one).
        st.session_state.pop("_login_needs_confirm", None)
        with get_session() as session:
            if not verify_password(session, nickname, password):
                st.error("❌ 密碼錯誤")
                return
            token = create_session(session, nickname)
    else:
        # New user — two-step flow:
        #   1st submit: flip the flag, rerun so the confirm field appears
        #   2nd submit (with confirm filled): validate match, register
        if not st.session_state.get("_login_needs_confirm", False):
            st.session_state["_login_needs_confirm"] = True
            st.rerun()
            return
        if not password_confirm:
            st.error("⚠️ 請在「確認密碼」欄再次輸入密碼")
            return
        if password != password_confirm:
            st.error("⚠️ 兩次輸入的密碼不一致")
            return
        if len(password) < 6:
            st.error("⚠️ 密碼至少 6 個字元")
            return
        with get_session() as session:
            register_user(session, nickname, password)
            token = create_session(session, nickname)
        st.session_state.pop("_login_needs_confirm", None)

    st.session_state.nickname = nickname
    st.session_state.auth_token = token
    st.session_state.authenticated = True
    st.session_state.read_only = False
    persist_credentials()
    st.rerun()
