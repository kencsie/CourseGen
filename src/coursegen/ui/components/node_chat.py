"""
Per-node AI chat component.

Renders a chat interface inside the node detail dialog. The system prompt is
built from the node's full type-specific content + sources + parent labels,
so the LLM stays scoped to that specific node.

Session-only — chat history lives in st.session_state.node_chat_history keyed by
f"{record_id}::{node_id}", and is wiped on new generation via reset_roadmap_state.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import streamlit as st
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from coursegen.ui.utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


def _chat_key(record_id: str | None, node_id: str) -> str:
    return f"{record_id or 'session'}::{node_id}"


def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return "（無來源資訊。請告知使用者本節點未引用外部來源，回答時不要編造引用編號。）"
    lines = []
    for i, s in enumerate(sources, start=1):
        title = s.get("title", "未知")
        url = s.get("url", "")
        snippet = s.get("snippet", "")
        if snippet:
            snippet = snippet[:400]
        lines.append(f"[{i}] {title} — {url}\n    {snippet}")
    return "\n\n".join(lines)


def _format_parents(parent_summaries: list[dict]) -> str:
    if not parent_summaries:
        return "（此節點為起始節點，無前置節點。）"
    return "\n".join(
        f"- {p.get('number', '?')} {p.get('label', '')}"
        for p in parent_summaries
    )


def _build_system_prompt(
    node_number: str,
    node_data: dict,
    parent_summaries: list[dict],
    content_entry: dict | None,
) -> str:
    """Build a system prompt that scopes the assistant to this single node.

    content_entry shape (from content_map): {"type": ..., ...content fields..., "sources": [...]}
    """
    label = node_data.get("label", "")
    node_type = node_data.get("type", "")
    description = node_data.get("description", "")

    if content_entry:
        sources = content_entry.get("sources", [])
        content_for_llm = {k: v for k, v in content_entry.items() if k != "sources"}
        content_block = json.dumps(content_for_llm, ensure_ascii=False, indent=2)
        sources_block = _format_sources(sources)
        content_status_note = ""
    else:
        content_block = "（此節點的教學內容尚未生成或生成失敗。請僅根據節點描述與前置節點脈絡回答，並明確告知使用者教學內容尚未就緒。）"
        sources_block = "（無來源資訊。）"
        content_status_note = "\n注意：本節點目前沒有正式教學內容，請避免編造細節。"

    parents_block = _format_parents(parent_summaries)

    return f"""你是 CourseGen 學習助教，專門協助使用者深入理解單一學習節點。
你必須**只**回答與下列節點相關的問題；若使用者問題超出此節點範圍，請禮貌地將焦點拉回本節點，並指出哪個前置或後續節點可能更適合。
{content_status_note}

# 本節點資訊
- 編號：{node_number}
- 名稱：{label}
- 類型：{node_type}
- 簡述：{description}

# 前置節點（學習者應已熟悉這些）
{parents_block}

# 本節點教學內容（JSON）
{content_block}

# 本節點引用來源
{sources_block}

# 回答規範
1. 回答用使用者提問的同種語言（預設繁體中文）。
2. 若引用上方來源，使用 `[N]` 標記，N 必須是上方來源列表中存在的編號；切勿編造編號或來源。
3. 若使用者問的事項在上述資訊中沒有依據，請坦白說「上述資料未涵蓋」並建議他們查核外部資料，不要硬編。
4. 回答盡量精煉（除非使用者要求展開），以教學語氣解釋，必要時用條列或範例。
5. 不要重複貼出整段教學內容；針對使用者的具體問題回答即可。
""".strip()


def _stream_assistant(
    model,
    messages: list,
    callbacks: list,
) -> Iterable[str]:
    """Yield content chunks from a LangChain ChatModel stream."""
    for chunk in model.stream(messages, config={"callbacks": callbacks}):
        text = getattr(chunk, "content", "")
        if isinstance(text, str) and text:
            yield text
        elif isinstance(text, list):
            # Some providers return list-of-parts; join string parts only
            for part in text:
                if isinstance(part, str) and part:
                    yield part
                elif isinstance(part, dict) and isinstance(part.get("text"), str):
                    yield part["text"]


def render_node_chat(
    roadmap_data: dict,
    node_id: str,
    node_data: dict,
    node_number: str,
    parent_summaries: list[dict],
    content_entry: dict | None,
) -> None:
    """Render the chat tab for a node inside the detail dialog."""
    record_id = st.session_state.get("current_record_id")
    key = _chat_key(record_id, node_id)
    history: list[dict] = st.session_state.node_chat_history.setdefault(key, [])

    api_key = st.session_state.get("api_key", "")
    if not api_key:
        st.error("⚠️ 請在 Sidebar 的「🔑 API 設定」中輸入 OpenRouter API Key，才能使用 AI 助教。")
        return

    st.caption(
        "💡 AI 助教只會根據此節點的教學內容、來源與前置節點回答。"
        "對話僅保存在當前 session，重新生成或關閉瀏覽器後消失。"
    )

    # ── Layout ────────────────────────────────────────────────────────
    # Top: clear-button slot (empty until history non-empty; populated AFTER
    # processing so the button appears right after the first query)
    # Middle: messages container (replayed history + new turn rendered into it)
    # Bottom: chat_input (called last in code → appears at the bottom of the tab)
    clear_slot = st.empty()
    messages_box = st.container()

    with messages_box:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    prompt = st.chat_input("針對此節點提問…", key=f"chat_input_{node_id}")

    # ── Process new prompt ────────────────────────────────────────────
    if prompt:
        # Mark this rerun as a dialog-internal action so the dismissal
        # heuristic in app.py doesn't close the dialog when chat_input
        # triggers a rerun.
        st.session_state._dialog_internal_action = True

        history.append({"role": "user", "content": prompt})

        system_prompt = _build_system_prompt(
            node_number, node_data, parent_summaries, content_entry
        )
        messages = [SystemMessage(content=system_prompt)]
        for msg in history[:-1]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        messages.append(HumanMessage(content=prompt))

        chat_model = (
            st.session_state.get("helper_model")
            or "google/gemini-3-flash-preview"
        )
        try:
            model = init_chat_model(
                model=chat_model,
                model_provider="openai",
                api_key=api_key,
                base_url=os.getenv("BASE_URL"),
                temperature=0.4,
            )
        except Exception as e:
            logger.exception("Failed to init chat model")
            history.pop()  # roll back the user msg so they can retry
            with messages_box:
                with st.chat_message("assistant"):
                    st.error(f"❌ 模型初始化失敗：{e}")
            return

        tracker = CostTracker()
        try:
            with messages_box:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    full_text = st.write_stream(
                        _stream_assistant(model, messages, callbacks=[tracker])
                    )
        except Exception as e:
            logger.exception("Chat stream failed")
            history.pop()  # roll back the user msg
            with messages_box:
                with st.chat_message("assistant"):
                    st.error(f"❌ 回答失敗：{e}")
            return

        # st.write_stream returns the joined string when given a generator
        if isinstance(full_text, list):
            full_text = "".join(s for s in full_text if isinstance(s, str))
        if not isinstance(full_text, str):
            full_text = str(full_text)

        history.append({"role": "assistant", "content": full_text})

        summary = tracker.get_summary()
        if summary["total_tokens"]:
            cost = summary.get("total_cost_usd")
            cost_str = f" · ${cost:.4f}" if isinstance(cost, (int, float)) else ""
            with messages_box:
                st.caption(
                    f"🪙 本輪 token: {summary['total_tokens']:,}"
                    f" (in {summary['input_tokens']:,} / out {summary['output_tokens']:,})"
                    f"{cost_str}"
                )

    # ── Populate clear button slot (after processing, so button appears
    # right after the first query) ─────────────────────────────────────
    if history:
        if clear_slot.button(
            "🧹 清除此節點對話",
            key=f"clear_chat_{node_id}",
            use_container_width=True,
        ):
            history.clear()
            st.session_state._dialog_internal_action = True
            st.rerun()
