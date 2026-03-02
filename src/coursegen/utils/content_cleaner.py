"""
Content Cleaner — 用 markdown header 切 section + cheap LLM 移除無關 section。
"""

import re
import logging

from langchain.chat_models import init_chat_model

from coursegen.schemas import SearchResult, SectionRemovalResponse
from coursegen.prompts.content import RAW_CONTENT_CLEANING_PROMPT

logger = logging.getLogger(__name__)

# Match markdown headers: #, ##, ###, ####
_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def split_into_sections(content: str) -> list[dict]:
    """Split content by markdown headers into semantic sections.

    Each section = {"heading": "## Title", "body": "...", "level": 2}
    Content before the first header becomes a preamble section (level=0).

    Fallback: if no headers found, split by \\n\\n and merge short paragraphs.
    """
    matches = list(_HEADER_RE.finditer(content))

    if not matches:
        # Fallback: split by double newline, merge short paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        sections = []
        buf = []
        for p in paragraphs:
            buf.append(p)
            merged = "\n\n".join(buf)
            if len(merged) >= 80:
                sections.append({"heading": "", "body": merged, "level": 0})
                buf = []
        if buf:
            sections.append({"heading": "", "body": "\n\n".join(buf), "level": 0})
        return sections

    sections = []

    # Preamble: content before the first header
    preamble = content[: matches[0].start()].strip()
    if preamble:
        sections.append({"heading": "", "body": preamble, "level": 0})

    for i, m in enumerate(matches):
        level = len(m.group(1))
        heading = m.group(0).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        sections.append({"heading": heading, "body": body, "level": level})

    return sections


def clean_single_source(
    raw_content: str,
    topic: str,
    node_label: str,
    model_name: str,
    api_key: str,
    base_url: str,
    config: dict | None = None,
) -> str:
    """Cheap LLM removes topic-irrelevant sections from raw_content."""
    original_len = len(raw_content)

    # 1. Split into sections
    sections = split_into_sections(raw_content)

    # 2. Too few sections — not worth an API call
    if len(sections) <= 3:
        logger.info(
            f"content_cleaner: only {len(sections)} sections, skipping LLM cleaning"
        )
        return raw_content

    # 3. Build numbered preview for prompt (heading + first 200 chars of body)
    previews = []
    for i, sec in enumerate(sections, 1):
        heading = sec["heading"] or "(no heading)"
        body_preview = sec["body"][:200]
        if len(sec["body"]) > 200:
            body_preview += "..."
        previews.append(f"[{i}] {heading}\n{body_preview}")
    numbered_sections = "\n\n".join(previews)

    prompt = RAW_CONTENT_CLEANING_PROMPT.format(
        topic=topic,
        node_label=node_label,
        numbered_sections=numbered_sections,
    )

    # 4. Call cheap LLM
    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    try:
        chain = model.with_structured_output(SectionRemovalResponse).with_retry(
            stop_after_attempt=2,
        )
        result = chain.invoke(prompt, config=config)
    except Exception as e:
        logger.warning(f"content_cleaner: LLM call failed, returning original: {e}")
        return raw_content

    # 5. Validate indices (1-based, within range)
    total = len(sections)
    remove_set = {idx for idx in result.remove_indices if 1 <= idx <= total}

    if not remove_set:
        logger.info("content_cleaner: LLM kept all sections")
        return raw_content

    # 6. Remove sections and rejoin
    kept = []
    for i, sec in enumerate(sections, 1):
        if i not in remove_set:
            if sec["heading"]:
                kept.append(sec["heading"] + "\n\n" + sec["body"])
            else:
                kept.append(sec["body"])

    cleaned = "\n\n".join(kept)
    cleaned_len = len(cleaned)
    reduction = (1 - cleaned_len / original_len) * 100 if original_len else 0

    logger.info(
        f"content_cleaner: removed {len(remove_set)}/{total} sections, "
        f"{original_len} -> {cleaned_len} chars ({reduction:.0f}% reduction)"
    )

    return cleaned


def clean_search_results(
    results: list[SearchResult],
    topic: str,
    node_label: str,
    model_name: str,
    api_key: str,
    base_url: str,
    config: dict | None = None,
) -> list[SearchResult]:
    """Clean raw_content for each SearchResult via cheap LLM. Returns new list."""
    cleaned = []
    total_before = 0
    total_after = 0

    for r in results:
        if not r.raw_content:
            cleaned.append(r)
            continue

        total_before += len(r.raw_content)
        new_content = clean_single_source(
            raw_content=r.raw_content,
            topic=topic,
            node_label=node_label,
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            config=config,
        )
        total_after += len(new_content)
        cleaned.append(
            SearchResult(
                title=r.title,
                url=r.url,
                content=r.content,
                score=r.score,
                raw_content=new_content,
            )
        )

    if total_before:
        reduction = (1 - total_after / total_before) * 100
        logger.info(
            f"content_cleaner total: {total_before} -> {total_after} chars "
            f"({reduction:.0f}% reduction) across {len(results)} sources"
        )

    return cleaned
