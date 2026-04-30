"""
Hierarchical numbering for roadmap DAG nodes.

Computes labels like "1", "2.1", "2.2", "3" so beginners see clear ordering.

Algorithm: Kahn's algorithm with longest-path layering (= ASAP scheduling).
A node's layer = max(layer of parents) + 1, which equals the wave in which Kahn
would pop it. Within-layer order = order popped from the Kahn queue, seeded and
tie-broken by the original ``roadmap["nodes"]`` list order so numbering stays
stable across reloads of saved DB records.
"""
from __future__ import annotations

import logging
from collections import deque

logger = logging.getLogger(__name__)


def compute_node_numbers(roadmap: dict) -> dict[str, str]:
    """Return a mapping {node_id: number_str} for the given roadmap.

    Solo node in a layer → "{layer}", multi-node layer → "{layer}.{pos}".
    Both numbers are 1-indexed.

    Defensive against:
    - Empty / missing nodes list → returns {}.
    - Dependencies referencing unknown IDs → silently dropped, logged at WARN.
    - Cycles (shouldn't happen — critic enforces acyclicity, but UI must not crash)
      → unprocessed remainder gets layer 0, logged at WARN.
    """
    nodes = roadmap.get("nodes") or []
    if not nodes:
        return {}

    id_set = {n["id"] for n in nodes}
    node_order = [n["id"] for n in nodes]  # original list order, used for stable tie-breaking

    # Filter dangling parent IDs once up-front
    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {nid: [] for nid in node_order}
    indegree: dict[str, int] = {}
    for n in nodes:
        nid = n["id"]
        valid_parents = []
        for p in n.get("dependencies", []) or []:
            if p in id_set:
                valid_parents.append(p)
            else:
                logger.warning("Roadmap node %s has unknown parent %s; ignoring", nid, p)
        parents[nid] = valid_parents
        indegree[nid] = len(valid_parents)
        for p in valid_parents:
            children[p].append(nid)

    # Kahn's algorithm. Seed with in-degree 0 nodes in original list order.
    queue: deque[str] = deque(nid for nid in node_order if indegree[nid] == 0)
    layer: dict[str, int] = {}
    pop_order: list[str] = []

    while queue:
        nid = queue.popleft()
        pop_order.append(nid)
        # Longest-path layer: max(parent layers) + 1, or 0 if no parents
        layer[nid] = (max((layer[p] for p in parents[nid]), default=-1) + 1)
        # Iterate children in original list order for deterministic tie-breaking
        for child in children[nid]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    # Cycle defense: any unprocessed nodes get layer 0
    if len(pop_order) < len(node_order):
        unprocessed = [nid for nid in node_order if nid not in layer]
        logger.warning(
            "Roadmap appears to contain a cycle; %d nodes unprocessed: %s",
            len(unprocessed),
            unprocessed,
        )
        for nid in unprocessed:
            layer[nid] = 0
            pop_order.append(nid)

    # Group by layer in pop_order (stable within layer)
    by_layer: dict[int, list[str]] = {}
    for nid in pop_order:
        by_layer.setdefault(layer[nid], []).append(nid)

    numbers: dict[str, str] = {}
    for lyr, members in by_layer.items():
        major = lyr + 1
        if len(members) == 1:
            numbers[members[0]] = f"{major}"
        else:
            for pos, nid in enumerate(members, start=1):
                numbers[nid] = f"{major}.{pos}"

    return numbers
