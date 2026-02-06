"""
Streamlit session state initialization and management.
"""
import streamlit as st


def init_session_state():
    """Initialize all Streamlit session state variables."""
    defaults = {
        # Current roadmap data
        "roadmap": None,  # Current roadmap data (from LangGraph)

        # UI state
        "selected_node": None,  # Currently selected node ID
        "node_progress": {},  # node_id -> {status, notes, started_at, completed_at}

        # Generation metadata
        "generation_metadata": {},  # Store time, iterations, etc.
        "is_generating": False,  # Whether roadmap is currently being generated

        # Error handling
        "error_message": None,  # Store error messages
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_roadmap_state():
    """Reset roadmap-related state (when generating new roadmap)."""
    st.session_state.roadmap = None
    st.session_state.selected_node = None
    st.session_state.node_progress = {}
    st.session_state.generation_metadata = {}
    st.session_state.error_message = None
