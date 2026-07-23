# Policy: data and research semantics

- `NO_MATCH`, unavailable, unsupported, not-yet-disclosed, missing, parse-suspect, and explicit zero are distinct.
- Never infer zero, absence, no risk, no order, or non-existence from a failed search or missing disclosure.
- Preserve original value, normalized value, unit, report period, event date, scope, source URL, document identity, page/row location, availability date, retrieval date, and derivation.
- Point-in-time runs may use only documents and facts available on or before `as_of_date`.
- Official direct facts outrank derived facts and secondary sources, but authoritative disagreement remains a visible conflict rather than a silently selected number.
- Execution success and research acceptance are separate. A pipeline may execute successfully and return coverage gaps or review-required source conflicts.
- Parser-suspect evidence remains traceable but is quarantined from reconciliation and accounting checks.
- Any new canonical mapping, sign convention, tolerance, or formula requires positive and negative regression fixtures.
