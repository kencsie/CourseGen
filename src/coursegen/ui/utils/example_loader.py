"""Utility functions for loading example roadmap data."""

import json
import logging
from pathlib import Path
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)


def get_examples_directory() -> Path:
    """Get absolute path to examples/roadmaps/ directory."""
    # Navigate from this file to project root, then to examples
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent.parent
    examples_dir = project_root / "examples" / "roadmaps"
    return examples_dir


@st.cache_data
def load_metadata() -> dict:
    """Load and parse metadata.json. Returns empty dict on error."""
    try:
        examples_dir = get_examples_directory()
        metadata_path = examples_dir / "metadata.json"

        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            return {"examples": []}

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data
    except Exception as e:
        logger.error(f"Error loading metadata: {e}")
        return {"examples": []}


def load_example_roadmap(example_id: str) -> Optional[dict]:
    """Load specific example by ID. Returns None if not found."""
    try:
        metadata = load_metadata()

        # Find the example in metadata
        example_info = None
        for ex in metadata.get("examples", []):
            if ex["id"] == example_id:
                example_info = ex
                break

        if not example_info:
            logger.warning(f"Example ID not found in metadata: {example_id}")
            return None

        # Load the roadmap file
        examples_dir = get_examples_directory()
        roadmap_path = examples_dir / example_info["filename"]

        if not roadmap_path.exists():
            logger.warning(f"Roadmap file not found: {roadmap_path}")
            return None

        with open(roadmap_path, "r", encoding="utf-8") as f:
            roadmap_data = json.load(f)

        return roadmap_data
    except Exception as e:
        logger.error(f"Error loading example roadmap {example_id}: {e}")
        return None


def filter_examples(
    metadata: dict,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
    tags: Optional[list[str]] = None
) -> list:
    """Filter examples by criteria. Returns filtered list."""
    examples = metadata.get("examples", [])

    filtered = examples

    # Filter by difficulty
    if difficulty and difficulty != "全部":
        filtered = [ex for ex in filtered if ex.get("difficulty") == difficulty]

    # Filter by language
    if language and language != "全部":
        filtered = [ex for ex in filtered if ex.get("language") == language]

    # Filter by tags (example must have all selected tags)
    if tags and len(tags) > 0:
        filtered = [
            ex for ex in filtered
            if all(tag in ex.get("tags", []) for tag in tags)
        ]

    return filtered


def get_example_metadata(example_id: str) -> Optional[dict]:
    """Get metadata for a specific example by ID."""
    metadata = load_metadata()

    for ex in metadata.get("examples", []):
        if ex["id"] == example_id:
            return ex

    return None
