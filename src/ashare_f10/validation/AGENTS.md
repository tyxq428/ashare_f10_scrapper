# Validation Domain Rules

These rules apply to `src/ashare_f10/validation/**`.

- Preserve point-in-time semantics: use only documents available on or before the task's `as_of_date`.
- Keep direct facts, derived facts, parse suspects, source conflicts and coverage gaps distinct.
- `NO_MATCH`, unavailable sources and extraction gaps must never become numeric zero.
- A suspicious parse remains traceable evidence but cannot enter canonical facts, reconciliation or accounting checks.
- Compare metrics using their registered method, canonical unit and tolerance; do not apply one universal numeric threshold.
- Preserve document identity, version lineage, page/row evidence and source URL/hash provenance.
- Any change to source priority, canonical meaning, tolerance or acceptance semantics is a business decision and requires ChatGPT Web review.
- Real source differences must remain visible even when execution succeeds.
