# W09 Smoke Result — B001 First Five

## Status

`PASS_WITH_GAPS`

The output is usable for the smoke gate because all gaps are explicitly classified, while all point-in-time, conservation and contamination gates pass.

## Exact evidence

- Workflow: `A-SCOPE F10 Real Smoke`.
- Run: `30547981782`.
- Job: `90889074320`.
- Head: `cabca6affeb5498393a4129218b2d9bba1524538`.
- Artifact ID: `8761691674`.
- Artifact: `ascope-f10-real-smoke-B001-5-30547981782`.
- Artifact digest: `sha256:b53e3ddb71f2965fb3d587b3956859a134baaaa69e2a3b02548a3227b5257587`.

## Acceptance matrix

| Check | Result |
|---|---:|
| Input securities | 5 |
| Successful securities | 5 |
| Failed securities | 0 |
| Deferred securities | 0 |
| Annual rows | 35 |
| Quarterly rows | 85 |
| Field-status rows | 1,370 |
| Classified data gaps | 123 |
| Future rows | 0 |
| Duplicate-resolution rows | 0 |
| Conservation | PASS |
| Fixture/non-investment contamination | 0 |

All five securities reached `COMPLETED_WITH_GAPS`. Missing internal-control opinions remain `SOURCE_MISSING`; bank-specific non-applicable industrial fields remain distinguishable from numeric zero.

## Storage finding

Completed source-run trees are pruned after their compact audit reports and canonical stock exports are preserved. This is required because the earlier five-stock raw source trees consumed roughly 1.1 GiB uncompressed and would not scale to a 200-stock hosted-runner batch.

## Next

Revalidate this smoke on exact `main`, then start full B001 automatically. Full B001 remains the W09 completion gate.
