# W09 B001 recovery plan

## Evidence received

The uploaded B001 checkpoint from rollout run `30551430941` contains:

- input securities: 200;
- completed with gaps: 196;
- terminal failures: 4;
- deferred: 0;
- annual rows: 1,372;
- quarterly rows: 3,332;
- field-status rows: 53,704;
- formal future rows: 0;
- duplicate-resolution rows: 0;
- security conservation: PASS.

The four terminal failures are:

| Security | Name | Deterministic root cause |
|---|---|---|
| `SZSE.000032` | 深桑达A | Excel-forbidden `U+0002` in `BUSINESS_REVIEW` |
| `SZSE.000403` | 派林生物 | Excel-forbidden `U+0000` padding in judgment text |
| `SZSE.000552` | 甘肃能化 | Excel-forbidden `U+0002` in `BUSINESS_REVIEW` |
| `SZSE.000593` | 德龙汇能 | Excel-forbidden `U+0019` in an announcement title |

All 113 F10 request groups completed for each failed security. The failure occurred during optional XLSX rendering after raw data collection; it is not an upstream request, disclosure-date or financial-mapping failure.

## Fix

1. Preserve raw JSON, Parquet and DuckDB values unchanged.
2. Before XLSX rendering only, remove XML/Excel-forbidden C0 control characters while preserving tab, line feed and carriage return.
3. Record affected string, character and code-point counts in `excel_sanitization.json`.
4. Restore the immutable B001 artifact from run `30551430941`.
5. Verify that the checkpoint contains exactly the four documented terminal failures and that their combined payloads contain the documented code points.
6. Reset only those four states to `PENDING`, with an audit entry in `recovery_history`; preserve all 196 successful securities.
7. Resume B001 from its existing per-stock request-group checkpoints.
8. Require 200/200 successful terminal states before releasing B002-B027.
9. Continue B002-B027 with `max-parallel=2`, then reduce and reconcile all 5,331 securities.

## Safety boundaries

- no blind rerun of the 196 successful B001 securities;
- no change to raw source values;
- no conversion of missing or not-applicable data to zero;
- no use of `report_period` as unknown `available_at`;
- no ST/*ST standard-path inclusion;
- Codex calls remain zero;
- paid probes remain zero;
- automatic trading remains disabled.
