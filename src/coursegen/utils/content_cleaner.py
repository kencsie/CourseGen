"""
Content Cleaner — 用 markdown header 切 section + cheap LLM 移除無關 section。
"""

import re
import logging

from langchain.chat_models import init_chat_model

from coursegen.schemas import SearchResult, SectionRemovalResponse, SourceSelectionResponse
from coursegen.prompts.content import (
    RAW_CONTENT_CLEANING_PROMPT,
    SOURCE_SELECTION_PROMPT,
    AGGRESSIVE_CLEANING_PROMPT,
)

logger = logging.getLogger(__name__)

# Match markdown headers: #, ##, ###, ####
_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# Match inline base64 image data URIs
_BASE64_RE = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+")

# Match markdown image syntax ![alt](url)
_MARKDOWN_IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")

# Match wiki/CMS edit links [edit](url) or [edit source](url)
_EDIT_LINK_RE = re.compile(r"\[edit(?:\s*source)?\]\([^)]+\)", re.IGNORECASE)


def strip_base64_images(content: str) -> str:
    """Remove inline base64 image data from content."""
    cleaned = _BASE64_RE.sub("", content)
    if len(cleaned) < len(content):
        removed = len(content) - len(cleaned)
        logger.info(f"strip_base64: removed {removed:,} chars of base64 image data")
    return cleaned


def strip_web_noise(content: str) -> str:
    """Remove common web-to-markdown noise: images, edit links."""
    original_len = len(content)
    content = _MARKDOWN_IMG_RE.sub("", content)
    content = _EDIT_LINK_RE.sub("", content)
    removed = original_len - len(content)
    if removed > 0:
        logger.info(f"strip_web_noise: removed {removed:,} chars")
    return content


def split_into_sections(content: str, max_section_size: int = 10_000) -> list[dict]:
    """Split content by markdown headers into semantic sections.

    Each section = {"heading": "## Title", "body": "..."}
    Content before the first header becomes a preamble section (heading="").

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
                sections.append({"heading": "", "body": merged})
                buf = []
        if buf:
            sections.append({"heading": "", "body": "\n\n".join(buf)})
        return sections

    sections = []

    # Preamble: content before the first header
    preamble = content[: matches[0].start()].strip()
    if preamble:
        sections.append({"heading": "", "body": preamble})

    for i, m in enumerate(matches):
        heading = m.group(0).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        sections.append({"heading": heading, "body": body})

    # Split oversized sections into chunks at nearest \n\n
    final = []
    for sec in sections:
        if len(sec["body"]) <= max_section_size:
            final.append(sec)
        else:
            body = sec["body"]
            chunks = []
            start = 0
            while start < len(body):
                if start + max_section_size >= len(body):
                    chunks.append(body[start:])
                    break
                # Search for \n\n near the boundary
                cut = body.rfind("\n\n", start, start + max_section_size)
                if cut <= start:
                    # No \n\n found, hard cut
                    cut = start + max_section_size
                else:
                    cut += 2  # include the \n\n in current chunk
                chunks.append(body[start:cut])
                start = cut
            for part_num, chunk in enumerate(chunks, 1):
                final.append(
                    {
                        "heading": f"{sec['heading']} (part {part_num})" if sec["heading"] else "",
                        "body": chunk,
                    }
                )
            logger.info(
                f"split_into_sections: split '{sec['heading'][:50]}' "
                f"({len(body):,} chars) into {len(chunks)} chunks"
            )
    return final


def select_top_sources(
    results: list[SearchResult],
    topic: str,
    node_label: str,
    model_name: str,
    api_key: str,
    base_url: str,
    max_sources: int = 4,
    config: dict | None = None,
) -> list[SearchResult]:
    """Cheap LLM selects top-k most valuable sources from N candidates."""
    if len(results) <= max_sources:
        logger.info(
            f"source_selection: only {len(results)} sources (<= {max_sources}), skipping"
        )
        return results

    # Build numbered preview: [i] title\nURL\nPreview: first 200 chars
    previews = []
    for i, r in enumerate(results, 1):
        preview = (r.raw_content or r.content or "")[:200]
        previews.append(f"[{i}] {r.title}\nURL: {r.url}\nPreview: {preview}")
    numbered_sources = "\n\n".join(previews)

    prompt = SOURCE_SELECTION_PROMPT.format(
        max_sources=max_sources,
        topic=topic,
        node_label=node_label,
        numbered_sources=numbered_sources,
    )

    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    try:
        chain = model.with_structured_output(SourceSelectionResponse).with_retry(
            stop_after_attempt=2,
        )
        result = chain.invoke(prompt, config=config)
    except Exception as e:
        logger.warning(f"source_selection: LLM call failed, keeping all sources: {e}")
        return results

    # Validate indices and cap at max_sources
    total = len(results)
    valid_indices = [idx for idx in result.keep_indices if 1 <= idx <= total]
    valid_indices = valid_indices[:max_sources]

    if not valid_indices:
        logger.warning("source_selection: no valid indices returned, keeping all sources")
        return results

    selected = [results[idx - 1] for idx in valid_indices]
    logger.info(
        f"source_selection: selected {len(selected)}/{total} sources "
        f"(indices: {valid_indices})"
    )
    return selected


def clean_single_source(
    raw_content: str,
    topic: str,
    node_label: str,
    model_name: str,
    api_key: str,
    base_url: str,
    config: dict | None = None,
    aggressive_threshold: int = 50000,
    max_sections: int = 10,
) -> str:
    """Cheap LLM removes topic-irrelevant sections from raw_content.

    Two-pass cleaning:
    1. First pass: remove completely irrelevant sections.
    2. Second pass (if result > aggressive_threshold): keep only top-N most relevant sections.
    """
    raw_content = strip_base64_images(raw_content)
    raw_content = strip_web_noise(raw_content)
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

    # ── Second pass: aggressive cleaning if still too large ──
    if cleaned_len > aggressive_threshold:
        cleaned = _aggressive_clean(
            cleaned, topic, node_label, model_name, api_key, base_url,
            config=config, max_sections=max_sections,
        )

    return cleaned


def _aggressive_clean(
    content: str,
    topic: str,
    node_label: str,
    model_name: str,
    api_key: str,
    base_url: str,
    config: dict | None = None,
    max_sections: int = 10,
) -> str:
    """Second-pass: keep only the top-N most relevant sections."""
    sections = split_into_sections(content)
    if len(sections) <= max_sections:
        logger.info(
            f"aggressive_clean: only {len(sections)} sections (<= {max_sections}), skipping"
        )
        return content

    # Build numbered preview
    previews = []
    for i, sec in enumerate(sections, 1):
        heading = sec["heading"] or "(no heading)"
        body_preview = sec["body"][:200]
        if len(sec["body"]) > 200:
            body_preview += "..."
        previews.append(f"[{i}] {heading}\n{body_preview}")
    numbered_sections = "\n\n".join(previews)

    prompt = AGGRESSIVE_CLEANING_PROMPT.format(
        topic=topic,
        node_label=node_label,
        numbered_sections=numbered_sections,
        max_sections=max_sections,
    )

    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    try:
        chain = model.with_structured_output(SourceSelectionResponse).with_retry(
            stop_after_attempt=2,
        )
        result = chain.invoke(prompt, config=config)
    except Exception as e:
        logger.warning(f"aggressive_clean: LLM call failed, returning first-pass result: {e}")
        return content

    # Validate and cap
    total = len(sections)
    keep_indices = [idx for idx in result.keep_indices if 1 <= idx <= total]
    keep_indices = keep_indices[:max_sections]

    if not keep_indices:
        logger.warning("aggressive_clean: no valid indices, returning first-pass result")
        return content

    keep_set = set(keep_indices)
    kept = []
    for i, sec in enumerate(sections, 1):
        if i in keep_set:
            if sec["heading"]:
                kept.append(sec["heading"] + "\n\n" + sec["body"])
            else:
                kept.append(sec["body"])

    aggressive_cleaned = "\n\n".join(kept)
    original_len = len(content)
    new_len = len(aggressive_cleaned)
    reduction = (1 - new_len / original_len) * 100 if original_len else 0

    logger.info(
        f"aggressive_clean: kept {len(keep_set)}/{total} sections, "
        f"{original_len} -> {new_len} chars ({reduction:.0f}% reduction)"
    )
    return aggressive_cleaned


def clean_search_results(
    results: list[SearchResult],
    topic: str,
    node_label: str,
    model_name: str,
    api_key: str,
    base_url: str,
    config: dict | None = None,
) -> tuple[list[SearchResult], dict]:
    """Clean raw_content for each SearchResult via cheap LLM.

    Returns:
        (cleaned_results, stats) where stats = {"raw_chars": int, "cleaned_chars": int}
    """
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

    stats = {"raw_chars": total_before, "cleaned_chars": total_after}
    return cleaned, stats
