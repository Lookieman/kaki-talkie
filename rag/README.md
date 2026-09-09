<!-- v1.0 | 10-Sep-2026 | Describe the WP3.1 corpus ingestion package. -->
# kaki-rag

The KaKi-Talkie retrieval subsystem. WP3.1 delivers corpus ingestion:
allowlisted official pages are fetched over HTTPS, kept as dated snapshots,
cleaned to heading-aware markdown blocks, chunked along semantic boundaries
and stored with full per-chunk provenance. Embeddings, Chroma and hybrid
retrieval arrive in WP3.2+.

## Layout

```text
corpus/allowlist.yaml     Source definitions (the only fetchable pages)
src/kaki_rag/ingest/      fetch, clean, chunk, metadata, pipeline
tests/                    Deterministic offline tests and HTML fixtures
```

Generated data never lives in Git. Snapshots go to
`KAKI_DATA_ROOT/corpus/snapshots/YYYY-MM-DD/` and processed chunks to
`KAKI_DATA_ROOT/corpus/processed/` (`design.md` 18.3).

## Use

Install editable into the application environment (`python -m pip install -e rag`),
then run ingestion through the owner CLI:

```sh
python scripts/ingest_corpus.py --allowlist rag/corpus/allowlist.yaml
```

Validation procedure and evidence: `docs/04-prototype/wp-validation-runbook.md`
section 8 (WP3.1 blocks). The allowlist format is a strict YAML subset
documented in `src/kaki_rag/ingest/fetch.py`; edit it only with owner review,
because it defines what the product may cite.
