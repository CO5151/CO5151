#!/usr/bin/env python3
"""Seed the Qdrant vector store from the local processed export.

Reads ``data/processed/qdrant_chunks_export.json`` (103 clauses with real 768-dim embeddings)
and upserts them directly into the live Qdrant collection.

Usage::

    docker compose up -d qdrant
    python scripts/load_qdrant_from_export.py
    python scripts/load_qdrant_from_export.py --recreate   # wipe & recreate collection
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from src.knowledge.qdrant_client import QdrantClientManager  # noqa: E402

CHUNK_EXPORT = WORKSPACE / "data/processed/qdrant_chunks_export.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Qdrant vector database from chunk export")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the Qdrant collection before upserting",
    )
    args = parser.parse_args()

    if not CHUNK_EXPORT.exists():
        print(f"[!] Error: {CHUNK_EXPORT} does not exist!")
        sys.exit(1)

    chunks = json.loads(CHUNK_EXPORT.read_text(encoding="utf-8"))
    print(f"[+] Loaded {len(chunks)} chunks from {CHUNK_EXPORT}")

    mgr = QdrantClientManager()
    if not mgr.health_check():
        print(f"[!] Error: Qdrant is not reachable at {mgr.host}:{mgr.port}.")
        print("    Please run: docker compose up -d qdrant")
        sys.exit(1)

    dim = len(chunks[0]["vector"]) if chunks and "vector" in chunks[0] else 768
    mgr.init_collection(vector_size=dim, recreate=args.recreate)
    mgr.setup_payload_indexes()

    count = mgr.upsert_legal_chunks(chunks)
    print(
        f"[+] Successfully upserted {count}/{len(chunks)} chunks into Qdrant collection '{mgr.collection_name}'!"
    )


if __name__ == "__main__":
    main()
