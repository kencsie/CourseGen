"""Read/write user credentials & preferences to browser localStorage."""
import streamlit as st
from streamlit_local_storage import LocalStorage

LS_KEYS = ["nickname", "api_key", "tavily_key", "content_model", "helper_model"]
_LS_PREFIX = "coursegen_"


def _ls() -> LocalStorage:
    return LocalStorage(key="coursegen_storage_init")


def load_persisted_credentials() -> None:
    """
    Hydrate session_state from localStorage on app start.

    Idempotent: existing non-empty session_state values are NOT overwritten,
    so typing-in-progress is never clobbered by a late localStorage read.
    """
    ls = _ls()
    for key in LS_KEYS:
        current = st.session_state.get(key)
        if current:
            continue
        stored = ls.getItem(f"{_LS_PREFIX}{key}")
        if stored:
            st.session_state[key] = stored


def persist_credentials() -> None:
    """Write current session_state values back to localStorage."""
    ls = _ls()
    for key in LS_KEYS:
        value = st.session_state.get(key, "")
        if value:
            ls.setItem(f"{_LS_PREFIX}{key}", value, key=f"ls_set_{key}")
