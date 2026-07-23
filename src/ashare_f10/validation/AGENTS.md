# Validation-domain instructions

- Preserve point-in-time semantics: facts and documents unavailable after `as_of_date` must not enter a historical baseline.
- Keep execution success separate from research acceptance; evidence-backed source conflicts are review findings, not process crashes.
- Missing, unavailable, not-yet-disclosed, unsupported, and explicit zero are distinct states.
- Do not silently select a canonical value when authoritative sources conflict.
- Preserve source document, page, row, unit, period, version, and derivation lineage.
- Parser-suspect facts remain traceable but must not contaminate reconciliation or accounting checks.
- Any new normalization or tolerance rule requires a positive fixture and a negative fixture that protects genuine conflicts.
