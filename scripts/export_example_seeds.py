"""One-time helper: dump records from a source DB to JSON seed files.

Run this ONCE against the DB that holds the reference roadmaps:

    uv run python scripts/export_example_seeds.py \\
        --source postgresql://user:pass@host:port/db \\
        --output src/coursegen/db/seeds

After running and committing the JSON files, this script can be deleted.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text


COLUMNS = [
    "id",
    "topic",
    "language",
    "created_at",
    "generation_time_sec",
    "iteration_count",
    "total_tokens",
    "total_cost_usd",
    "roadmap_json",
    "content_map_json",
    "content_order_json",
    "content_failed_nodes_json",
    "raw_content_chars",
    "cleaned_content_chars",
]

# Columns stored as JSON in the schema but returned as strings by some
# dialects (notably SQLite) when queried via raw text(). We parse them back
# into native dict/list so the resulting JSON file is well-formed nested
# JSON, not a JSON-with-stringified-JSON.
JSON_COLUMNS = {
    "roadmap_json",
    "content_map_json",
    "content_order_json",
    "content_failed_nodes_json",
}


def _serialize(col, value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if col in JSON_COLUMNS and isinstance(value, str):
        return json.loads(value)
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source DB URL")
    parser.add_argument(
        "--output", required=True, help="Directory to write seed JSONs into"
    )
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(args.source)
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(f"SELECT {', '.join(COLUMNS)} FROM generation_records "
                     f"ORDER BY created_at ASC")
            )
            .mappings()
            .all()
        )

    if not rows:
        print(f"No rows found in {args.source}")
        return

    for i, row in enumerate(rows, 1):
        record = {col: _serialize(col, row[col]) for col in COLUMNS}
        filename = out_dir / f"example_{i:02d}.json"
        filename.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Wrote {filename} ({row['topic']})")

    print(f"\nExported {len(rows)} record(s) to {out_dir}")


if __name__ == "__main__":
    main()
