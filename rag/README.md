<!-- v1.2 | 10-Sep-2026 | Document the WP3.2 hybrid retrieval layer and extras. -->
<!-- v1.1 | 10-Sep-2026 | Document the manual markdown capture model for the MVP corpus. -->
<!-- v1.0 | 10-Sep-2026 | Describe the WP3.1 corpus ingestion package. -->
# kaki-rag

The KaKi-Talkie retrieval subsystem. WP3.1 delivers corpus ingestion:
allowlisted official sources are kept as dated snapshots, cleaned to
heading-aware blocks, chunked along semantic boundaries and stored with
full per-chunk provenance. The MVP corpus is captured manually as
owner-reviewed markdown (`capture: manual` in the allowlist, seeded with
`scripts/seed_snapshot.py`; design.md 7.2) and is never fetched live; the
automated HTTPS fetch path remains for `capture: auto` sources.

WP3.2 delivers hybrid multilingual retrieval (design.md 7.4): processed
chunks are embedded with `Qwen/Qwen3-Embedding-0.6B` (approved fallback
`BAAI/bge-m3`) into a persistent embedded Chroma collection, a
dependency-free BM25 index protects exact terms such as `CHAS`, and the
`HybridRetriever` merges dense and lexical candidates for the original
transcript and the normalised English query with reciprocal rank fusion.
Application code depends on the `Retriever` and `EmbeddingPort`
interfaces, never on Chroma or model APIs directly. Grounded answering
and refusal arrive in WP3.3/WP3.4.

## Layout

```text
corpus/allowlist.yaml     Source definitions (the only fetchable pages)
src/kaki_rag/ingest/      fetch, clean, chunk, metadata, pipeline
src/kaki_rag/retrieve/    chunks, embedding, vector_store, lexical, hybrid, index
tests/                    Deterministic offline tests and fixtures
```

Optional extras: `kaki-rag[retrieve]` adds `chromadb` (needed by CI for
the offline retrieval tests); `kaki-rag[embed]` adds the
`sentence-transformers` runtime (Mac only). The base install stays
stdlib + httpx for ingestion.

Generated data never lives in Git. Snapshots go to
`KAKI_DATA_ROOT/corpus/snapshots/YYYY-MM-DD/` and processed chunks to
`KAKI_DATA_ROOT/corpus/processed/` (`design.md` 18.3).

## Use

Install editable into the application environment
(`python -m pip install -e "rag[retrieve,embed]"` on the Mac), then run
ingestion, indexing and retrieval smoke tests through the owner CLIs:

```sh
python scripts/ingest_corpus.py --allowlist rag/corpus/allowlist.yaml
python scripts/index_corpus.py
python scripts/query_corpus.py --query "How do I use my CDC vouchers?" --top-k 3
```

Validation procedure and evidence: `docs/04-prototype/wp-validation-runbook.md`
section 8 (WP3.1/WP3.2 blocks). The allowlist format is a strict YAML subset
documented in `src/kaki_rag/ingest/fetch.py`; edit it only with owner review,
because it defines what the product may cite.
