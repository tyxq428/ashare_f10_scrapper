# Operations and troubleshooting

## Rate limiting

Start with 8 group workers and 4 page workers. If the target returns 403/429:

```env
ASHARE_F10_MAX_WORKERS=3
ASHARE_F10_PAGE_WORKERS=2
ASHARE_F10_RETRIES=4
```

Successful request fingerprints remain cached, so rerunning does not start from zero.

## Resume

Each successful request group is saved under `groups/<group_id>.json`. A repeated run with the same output directory loads successful groups and only processes missing groups.

## Data integrity

- Raw response SHA-256 is stored in cache metadata.
- JSON and Excel are generated from the same combined group results.
- DuckDB and Parquet derive from the same fact iterator.
- Original API keys are never discarded.

## GitHub Pages

Pages is a static viewer. It cannot execute Python or securely store a private-repository token. Use GitHub Actions manually or add the Cloudflare Worker proxy in phase 2.

## Server deployment

Replace `OWNER` in `deploy/server/docker-compose.yml`, or build locally:

```bash
docker build -t ashare-f10 .
docker run --rm -p 8000:8000 -v "$PWD/data:/app/data" ashare-f10
```
