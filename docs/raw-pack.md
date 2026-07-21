# Official Raw Pack

Raw Pack extends the fixed F10 pipeline with traceable official documents and source-status evidence.

## Run locally

```bash
ashare-f10 fetch 688521 --output data/688521/raw-pack-demo --include-raw-pack \
  --raw-pack-packs default --raw-pack-max-docs 200
```

The flag is opt-in. `--no-raw-pack` remains the default and preserves the existing F10-only workflow.

A Raw Pack can also be generated from an existing completed F10 run:

```bash
ashare-f10 raw-pack 688521 --run-dir data/688521/existing-run --packs default --max-docs 200
```

## Output contract

```text
raw_pack/<security_code>/<run_id>/
├── metadata/raw_pack_run.json
├── source_index/source_documents.jsonl
├── source_index/attachments.jsonl
├── source_index/entity_matches.json
├── source_index/source_documents.parquet
├── source_index/raw_pack.duckdb
├── source_index/raw_pack_index.xlsx
├── raw_sources/<pack_id>/<source_id>/
├── parsed_sources/<pack_id>/<source_id>/
└── quality/raw_pack_quality.json
```

Every saved file records `source_url`, `retrieved_at_utc`, `sha256` and `entity_match_status`.

## Source-status rules

- `FACT_DIRECT`: direct statutory, government or authorized primary evidence.
- `COMPANY_CLAIM`: the company's own website or product statement.
- `PRIMARY_NONSTATUTORY`: official interaction/roadshow material that is not statutory disclosure.
- `SECONDARY_SOURCE` and `INDEX_ONLY`: discovery signals only, not direct facts.
- `NO_MATCH`: no exact entity match under the recorded query. It does **not** mean zero or non-existence.
- `PERMISSION_BLOCKED`: login, captcha, HTTP 403 or dynamic access gate. The source is tried once per run and does not fail the complete job.
- `UNRESOLVED`: download, parse or entity conflict that cannot be resolved safely.

## Web

Start the server and open `/raw-pack.html`.

```bash
ashare-f10 serve
```

The page contains a Raw Pack task center, evidence browser, document details and a permission-blocked queue.

## GitHub Actions

`Fetch A-share F10` exposes:

- `include_raw_pack` (default `false`)
- `raw_pack_packs` (default `default`)
- `raw_pack_max_docs` (default `200`)

The separate `Raw Pack 688521 E2E` workflow exercises the opt-in path without changing the existing E2E contract.
