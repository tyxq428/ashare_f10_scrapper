# W02 Plan — Canonical Finance Semantics

## Goal

Map existing normalized F10 facts into A-SCOPE annual and quarterly fields while preserving source lineage, applicability, point-in-time availability, report revisions and cumulative-flow semantics.

## Inputs

- normalized F10 fact rows from `facts.parquet` or the `facts` DuckDB table;
- existing `ResearchOntology` field aliases;
- request row cutoff and requested history ranges;
- optional disclosure-date metadata rows;
- company industry template.

## Tasks

1. Define versioned A-SCOPE target fields and source-key priorities.
2. Add industry templates:
   - `INDUSTRIAL`;
   - `BANK`;
   - `INSURANCE`;
   - `SECURITIES`;
   - `OTHER_FINANCIAL`.
3. Normalize source values to canonical units without inventing missing values.
4. Resolve `available_at` from direct source metadata or explicit disclosure-date supplement.
5. Exclude facts with unknown required availability from formal output.
6. Select the latest revision available at or before the cutoff.
7. Build annual rows from fiscal-year observations.
8. Build standalone quarterly flow values:
   - Q1 direct cumulative;
   - Q2 = H1 cumulative − Q1;
   - Q3 = 9M cumulative − H1;
   - Q4 = FY cumulative − 9M;
   - direct standalone quarter values override derived values when explicitly identified.
9. Preserve point-in-time balance-sheet values without differencing.
10. Derive audited fields only from explicit source keys or metadata.
11. Write field-level status and lineage records.
12. Quarantine conflicts, suspect parses and future observations.

## Canonical quarterly fields

- `revenue`
- `gross_profit`
- `deducted_net_profit`
- `operating_cash_flow`
- `accounts_receivable`
- `inventory`
- `contract_liabilities`
- `capex`
- `interest_bearing_debt`
- `total_equity`
- `total_assets`
- `cash`

## Core statuses

- `SOURCE_DIRECT`
- `DERIVED`
- `DERIVED_PROXY`
- `NOT_APPLICABLE`
- `NOT_DISCLOSED`
- `SOURCE_MISSING`
- `CONFLICTING`
- `FUTURE_EXCLUDED`
- `PARSE_SUSPECT`

## Gates

- Industrial fixture maps all directly available fields.
- Bank fixture leaves industrial-only fields null with `NOT_APPLICABLE`.
- Unknown `available_at` rows are excluded, not backfilled from report date.
- Future revisions are excluded.
- Latest eligible revision wins deterministically.
- Quarter derivations reconcile to cumulative source values within tolerance.
- Balance-sheet values are never differenced.
- Direct and derived values include source/derivation lineage.
- Ruff, compile and targeted tests pass.

## Failure policy

A missing field does not fail the whole security when the field has an explicit status. A required availability date, irreconcilable duplicate or conflicting usable source prevents that field from entering formal output and creates a data gap.

## Exit

W02 passes when fixtures for an industrial company, a bank, revision history and cumulative quarter derivation all satisfy the point-in-time and field-status contracts.