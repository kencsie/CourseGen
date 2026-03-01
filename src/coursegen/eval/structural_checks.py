"""Layer 2: Rule-based structural checks per generation."""
from __future__ import annotations

import re
from collections import deque

from coursegen.eval.schemas import CheckFailure, StructuralReport

# ── Type-specific field requirements ──
# (field, min_items, max_items)  — for list fields
# (field, min_len, max_len)      — for string fields (character count)

_LIST_REQS: dict[str, list[tuple[str, int, int]]] = {
    "prerequisite": [
        ("checklist", 1, 3),
        ("remediation", 2, 4),
    ],
    "concept": [
        ("key_points", 3, 5),
        ("examples", 1, 3),
    ],
    "pitfall": [
        ("pitfalls", 3, 5),
        ("warning_signs", 2, 3),
    ],
    "comparison": [
        ("comparison_table", 3, 6),
    ],
    "practice": [
        ("tasks", 2, 4),
        ("hints", 1, 3),
    ],
}

_STR_REQS: dict[str, list[tuple[str, int, int]]] = {
    "concept": [
        ("explanation", 150, 3000),
    ],
}

_NONEMPTY_STR: dict[str, list[str]] = {
    "comparison": ["subject_a", "subject_b"],
    "practice": ["objective"],
}

_CITATION_RE = re.compile(r"\[(\d+)\]")


def run_structural_checks(generation: dict) -> StructuralReport:
    """Run all rule-based checks on a single generation record.

    Args:
        generation: dict from ``load_generation()``.
    """
    failures: list[CheckFailure] = []
    total_checks = 0
    gen_id = generation["id"]
    topic = generation["topic"]
    roadmap = generation.get("roadmap") or {}
    nodes = roadmap.get("nodes", [])
    content_map = generation.get("content_map") or {}

    # ── Roadmap checks ──
    total_checks += 3
    failures.extend(_check_dag(nodes))
    failures.extend(_check_node_count(nodes))
    failures.extend(_check_type_coverage(nodes))

    # ── Per-node content checks ──
    for node in nodes:
        nid = node.get("id", "?")
        ntype = node.get("type", "unknown")
        content = content_map.get(nid)
        if content is None:
            # Node content missing — skip content checks for this node
            continue

        # Common checks
        total_checks += 3
        failures.extend(_check_required_fields(nid, ntype, content))
        failures.extend(_check_sources(nid, content))
        failures.extend(_check_citations(nid, content))

        # Type-specific checks
        tc = _check_type_specific(nid, ntype, content)
        total_checks += tc[0]
        failures.extend(tc[1])

    passed = len(failures) == 0
    return StructuralReport(
        generation_id=gen_id,
        topic=topic,
        passed=passed,
        total_checks=total_checks,
        failures=failures,
    )


# ── Roadmap-level checks ──


def _check_dag(nodes: list[dict]) -> list[CheckFailure]:
    """Verify nodes form a valid DAG: no cycles, all dependency IDs exist."""
    failures: list[CheckFailure] = []
    node_ids = {n["id"] for n in nodes}

    # Check dependency references
    for n in nodes:
        for dep in n.get("dependencies", []):
            if dep not in node_ids:
                failures.append(CheckFailure(
                    check="dag_dependency_exists",
                    detail=f"Node '{n['id']}' depends on '{dep}' which does not exist",
                ))

    # Cycle detection via topological sort (Kahn's algorithm)
    adj: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    in_deg: dict[str, int] = {n["id"]: 0 for n in nodes}
    for n in nodes:
        for dep in n.get("dependencies", []):
            if dep in adj:
                adj[dep].append(n["id"])
                in_deg[n["id"]] += 1

    queue = deque(nid for nid, d in in_deg.items() if d == 0)
    visited = 0
    while queue:
        cur = queue.popleft()
        visited += 1
        for child in adj[cur]:
            in_deg[child] -= 1
            if in_deg[child] == 0:
                queue.append(child)

    if visited != len(nodes):
        failures.append(CheckFailure(
            check="dag_no_cycle",
            detail=f"Cycle detected in roadmap DAG (visited {visited}/{len(nodes)} nodes)",
        ))

    return failures


def _check_node_count(nodes: list[dict]) -> list[CheckFailure]:
    n = len(nodes)
    if n < 5 or n > 15:
        return [CheckFailure(
            check="node_count_range",
            detail=f"Expected 5-15 nodes, got {n}",
        )]
    return []


def _check_type_coverage(nodes: list[dict]) -> list[CheckFailure]:
    expected = {"prerequisite", "concept", "pitfall", "comparison", "practice"}
    present = {n.get("type") for n in nodes}
    missing = expected - present
    if missing:
        return [CheckFailure(
            check="type_coverage",
            detail=f"Missing node types: {sorted(missing)}",
        )]
    return []


# ── Per-node common checks ──


def _check_required_fields(node_id: str, node_type: str, content: dict) -> list[CheckFailure]:
    """Check that all expected fields for this node type are non-empty."""
    failures: list[CheckFailure] = []
    # Common fields that should exist
    type_fields: dict[str, list[str]] = {
        "prerequisite": ["overview", "checklist", "remediation"],
        "concept": ["explanation", "key_points", "examples"],
        "pitfall": ["pitfalls", "warning_signs"],
        "comparison": ["subject_a", "subject_b", "comparison_table", "when_to_use"],
        "practice": ["objective", "tasks", "expected_output", "hints"],
    }
    for field in type_fields.get(node_type, []):
        val = content.get(field)
        if val is None or val == "" or val == []:
            failures.append(CheckFailure(
                node_id=node_id,
                check="required_field_present",
                detail=f"Field '{field}' is empty or missing",
            ))
    return failures


def _check_sources(node_id: str, content: dict) -> list[CheckFailure]:
    """Check that sources array exists."""
    sources = content.get("sources")
    if sources is None:
        return [CheckFailure(
            node_id=node_id,
            check="sources_present",
            detail="'sources' field is missing",
        )]
    return []


def _check_citations(node_id: str, content: dict) -> list[CheckFailure]:
    """Check citation [N] references against sources length."""
    failures: list[CheckFailure] = []
    sources = content.get("sources") or []
    num_sources = len(sources)

    # Collect all text fields to scan for citations
    text_parts: list[str] = []
    for key, val in content.items():
        if key in ("reasoning", "sources"):
            continue
        if isinstance(val, str):
            text_parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    text_parts.extend(str(v) for v in item.values())

    all_text = " ".join(text_parts)
    cited_indices = {int(m) for m in _CITATION_RE.findall(all_text)}

    for idx in sorted(cited_indices):
        if idx < 1 or idx > num_sources:
            failures.append(CheckFailure(
                node_id=node_id,
                check="citation_valid_index",
                detail=f"Citation [{idx}] out of range (sources has {num_sources} items)",
            ))

    return failures


# ── Type-specific checks ──


def _check_type_specific(
    node_id: str, node_type: str, content: dict
) -> tuple[int, list[CheckFailure]]:
    """Return (num_checks, failures) for type-specific rules."""
    checks = 0
    failures: list[CheckFailure] = []

    # List length checks
    for field, lo, hi in _LIST_REQS.get(node_type, []):
        checks += 1
        val = content.get(field)
        if isinstance(val, list):
            n = len(val)
            if n < lo or n > hi:
                failures.append(CheckFailure(
                    node_id=node_id,
                    check=f"{field}_count",
                    detail=f"Expected {lo}-{hi} items, got {n}",
                ))
        # Missing field already caught by required_field_present

    # String length checks (word count)
    for field, lo, hi in _STR_REQS.get(node_type, []):
        checks += 1
        val = content.get(field, "")
        if isinstance(val, str):
            wc = len(val)
            if wc < lo or wc > hi:
                failures.append(CheckFailure(
                    node_id=node_id,
                    check=f"{field}_length",
                    detail=f"Expected {lo}-{hi} chars, got {wc}",
                ))

    # Non-empty string checks
    for field in _NONEMPTY_STR.get(node_type, []):
        checks += 1
        val = content.get(field, "")
        if not val or not val.strip():
            failures.append(CheckFailure(
                node_id=node_id,
                check=f"{field}_nonempty",
                detail=f"Field '{field}' must be non-empty",
            ))

    # comparison_table dimension check
    if node_type == "comparison":
        checks += 1
        table = content.get("comparison_table") or []
        for i, row in enumerate(table):
            if not isinstance(row, dict):
                continue
            for key in ("dimension", "a", "b"):
                if not row.get(key):
                    failures.append(CheckFailure(
                        node_id=node_id,
                        check="comparison_table_fields",
                        detail=f"comparison_table[{i}] missing '{key}'",
                    ))

    return checks, failures
