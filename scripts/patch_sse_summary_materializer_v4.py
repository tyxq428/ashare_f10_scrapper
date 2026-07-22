from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_sse_summary_scope_fix.py")
text = path.read_text(encoding="utf-8")
old = '''    pending_mask = (
        (date_values > latest_available)
        & result["status"].eq("OFFICIAL_PERIOD_NOT_LOADED")
    )
'''
new = '''    pending_mask = pd.Series(False, index=result.index)
    if latest_available:
        pending_mask = (
            ~date_values.isin(post_listing_missing)
            & (date_values > latest_available)
            & result["status"].eq("OFFICIAL_PERIOD_NOT_LOADED")
        )
'''
if old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
elif "pending_mask = pd.Series(False, index=result.index)" not in text:
    raise SystemExit("pending-report precedence marker not found")
