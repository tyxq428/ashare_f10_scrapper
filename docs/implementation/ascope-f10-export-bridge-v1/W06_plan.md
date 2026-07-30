# W06 Plan — Batch Reduction and Quality Assurance

## Goal

Reduce per-stock outputs into one deterministic batch package and fail closed on schema, point-in-time, identity, duplicate or conservation errors.

## Tasks

1. Read every requested stock manifest and terminal status.
2. Verify input-package, batch and cutoff fingerprints.
3. Concatenate annual, quarterly and field-status tables.
4. Preserve explicit empty tables and applicable headers.
5. Enforce unique annual and quarterly keys.
6. Verify every formal row has `available_at <= as_of_date`.
7. Verify standard-path securities match the batch request exactly.
8. Validate no ST/*ST row entered the standard path.
9. Reconcile completed, failed and deferred counts to input count.
10. Generate field coverage by field, template and reporting period.
11. Generate gap, future-row, conflict and duplicate-resolution outputs.
12. Write a versioned validation report and batch manifest.

## Required batch outputs

- `financial_annual.csv`
- `financial_quarterly.csv`
- `financial_field_status.csv`
- `completed_securities.csv`
- `failed_securities.csv`
- `deferred_securities.csv`
- `data_gaps.csv`
- `future_available_rows.csv`
- `duplicate_resolution.csv`
- `field_coverage.csv`
- `validation_report.json`
- `batch_manifest.json`
- `checkpoint.json`

## Gates

- Each input security appears exactly once in completed, failed or deferred ledgers.
- Formal financial tables have no future rows.
- Annual primary key: `security_id + report_period` unique.
- Quarterly primary key: `security_id + report_period` unique.
- Field status preserves missing/inapplicable distinction.
- Batch totals conserve input rows.
- All outputs are readable by the downstream A-SCOPE merger.

## Exit

W06 passes when a mixed fixture batch reduces deterministically and every injected integrity error fails closed with an explicit reason code.