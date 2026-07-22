from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_sz_cninfo_parser_fix_v2.py")
text = path.read_text(encoding="utf-8")
old = '''def _unit_info(text: str) -> tuple[str, float]:
    return _page_unit_info(text) or ("元", 1.0)
'''
new = '''def _unit_info(text: str) -> tuple[str, float]:
    return _row_unit_info(text) or ("元", 1.0)
'''
if old not in text and new not in text:
    raise SystemExit("CNINFO v2 unit compatibility marker not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
