"""Idempotent seed: populate user_id='example' with default reference roadmaps.

Called from init_db() after Base.metadata.create_all. If 'example' user
already has any rows, seed is a no-op.

Seed files live in `src/coursegen/db/seeds/example_*.json` and are produced
by `scripts/export_example_seeds.py` from a reference DB.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from coursegen.db.models import GenerationRecord

EXAMPLE_USER_ID = "example"
SEEDS_DIR = Path(__file__).parent / "seeds"

# Columns the schema stores as JSON. Some legacy seed files (exported via
# raw SQL against SQLite) embed these as stringified JSON; parse defensively
# so both shapes load correctly.
_JSON_COLUMNS = {
    "roadmap_json",
    "content_map_json",
    "content_order_json",
    "content_failed_nodes_json",
}


def seed_example_user(session: Session) -> int:
    """Insert seed records if the example user has none. Returns count inserted."""
    existing = (
        session.query(GenerationRecord)
        .filter(GenerationRecord.user_id == EXAMPLE_USER_ID)
        .count()
    )
    if existing > 0:
        return 0

    if not SEEDS_DIR.exists():
        return 0

    count = 0
    for seed_file in sorted(SEEDS_DIR.glob("example_*.json")):
        data = json.loads(seed_file.read_text(encoding="utf-8"))
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        for col in _JSON_COLUMNS:
            if isinstance(data.get(col), str):
                data[col] = json.loads(data[col])

        record = GenerationRecord(user_id=EXAMPLE_USER_ID, **data)
        session.add(record)
        count += 1

    return count
