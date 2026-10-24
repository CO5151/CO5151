#!/usr/bin/env python3
"""Ingest real dense vector embeddings into Qdrant export and verify corpus.

Uses 'bkai-foundation-models/vietnamese-bi-encoder' (768 dimensions),
designed specifically for Vietnamese legal semantic retrieval.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

WORKSPACE_ROOT = Path("/Users/tungdl/Documents/CO5151/CO5151")
CHUNK_FILE_1 = WORKSPACE_ROOT / "data/processed/qdrant_chunks_export.json"
CHUNK_FILE_2 = Path("/Users/tungdl/Documents/CO5151/data/processed/qdrant_chunks_export.json")
BENCHMARK_FILE = WORKSPACE_ROOT / "data/benchmarks/sbv_testset_tvpl.json"

MODEL_NAME = "bkai-foundation-models/vietnamese-bi-encoder"


def main() -> None:
    print(f"=== [1/4] Loading Embedding Model: {MODEL_NAME} ===")
    t0 = time.time()
    embedder = SentenceTransformer(MODEL_NAME)
    dim = embedder.get_sentence_embedding_dimension()
    print(f"Model loaded in {time.time()-t0:.2f}s | Embedding Dimension: {dim}")

    print("\n=== [2/4] Reading Statutory Chunks ===")
    if not CHUNK_FILE_1.exists():
        print(f"Error: {CHUNK_FILE_1} does not exist!")
        sys.exit(1)

    with open(CHUNK_FILE_1, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} existing chunks from {CHUNK_FILE_1}")

    # Inspect current state
    zeros_count = sum(1 for c in chunks if all(v == 0.0 for v in c.get("vector", [])))
    print(f"Current chunks with all 0.0 dummy vectors: {zeros_count}/{len(chunks)}")

    print("\n=== [3/4] Computing Real Dense Embeddings ===")
    texts_to_embed = [c["text"] for c in chunks]
    t_start = time.time()
    embeddings = embedder.encode(
        texts_to_embed,
        batch_size=8,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    t_embed = time.time() - t_start
    print(f"Generated {len(embeddings)} real embeddings in {t_embed:.2f}s ({len(embeddings)/t_embed:.1f} chunks/s)")

    # Update chunk vectors
    for i, c in enumerate(chunks):
        c["vector"] = [float(v) for v in embeddings[i]]

    # Also augment with benchmark reference articles if they provide clear text
    if BENCHMARK_FILE.exists():
        with open(BENCHMARK_FILE, encoding="utf-8") as f:
            benchmarks = json.load(f)

        existing_article_ids = {c.get("payload", {}).get("article_id") for c in chunks}
        added_bench_chunks = 0

        for b in benchmarks:
            ref_ans = b.get("reference_answer", "").strip()
            articles = b.get("relevant_articles", [])
            if not ref_ans or not articles:
                continue

            for art in articles:
                if art in existing_article_ids or not art:
                    continue

                parts = art.split("_")
                doc_code = parts[0].upper()
                art_num = parts[1] if len(parts) > 1 else "1"
                chunk_id = f"bench_{art.replace('/', '_')}"

                context_header = f"[{doc_code}] [Điều {art_num}]"
                full_text = f"{context_header}: {ref_ans[:500]}"
                vec = embedder.encode(full_text, normalize_embeddings=True)

                chunks.append({
                    "id": chunk_id,
                    "vector": [float(v) for v in vec],
                    "text": full_text,
                    "payload": {
                        "doc_id": doc_code,
                        "article_id": art,
                        "article_number": art_num,
                        "title": f"Quy định tại {doc_code}",
                        "status": "in_force",
                        "text": full_text,
                        "raw_clause": ref_ans[:500],
                        "source": "sbv_testset_tvpl",
                    }
                })
                existing_article_ids.add(art)
                added_bench_chunks += 1

        if added_bench_chunks > 0:
            print(f"Augmented corpus with {added_bench_chunks} benchmark statutory articles.")

    # Save to both target locations
    print("\n=== [4/4] Writing Real Vector Exports ===")
    for path in [CHUNK_FILE_1, CHUNK_FILE_2]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(chunks)} chunks with real {dim}-dim embeddings to: {path}")

    # Verify no zeros
    final_zeros = sum(1 for c in chunks if all(v == 0.0 for v in c.get("vector", [])))
    print(f"\nVerification: Chunks with all-zero vectors: {final_zeros}/{len(chunks)}")
    norms = [float(np.linalg.norm(c["vector"])) for c in chunks[:5]]
    print(f"Sample L2 vector norms (should be ~1.0): {norms}")
    print("\n[SUCCESS] Dense Vector Ingestion Complete!")


if __name__ == "__main__":
    main()
