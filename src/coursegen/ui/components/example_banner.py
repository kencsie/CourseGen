"""Example banner component for indicating when viewing an example roadmap."""

import streamlit as st
from typing import Optional


def render_example_banner(example_metadata: dict) -> str:
    """
    Show banner when viewing example. Returns action: 'return', 'generate', or None.
    """
    # Create banner with distinct styling
    st.markdown(
        f"""
        <div style="
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px 20px;
            border-radius: 4px;
            margin-bottom: 20px;
        ">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center;">
                    <span style="font-size: 24px; margin-right: 12px;">📖</span>
                    <div>
                        <div style="font-size: 16px; font-weight: 600; color: #1976d2;">
                            您正在查看範例：{example_metadata.get('display_name', 'Unknown')}
                        </div>
                        <div style="font-size: 14px; color: #555; margin-top: 4px;">
                            {example_metadata.get('description', '')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Action buttons
    col1, col2, col3 = st.columns([2, 3, 7])

    action = None

    with col1:
        if st.button("← 返回範例列表", key="return_to_browser", use_container_width=True):
            action = "return"

    with col2:
        if st.button("✨ 基於此範例生成新的", key="generate_from_example", use_container_width=True):
            action = "generate"

    st.markdown("---")

    return action
