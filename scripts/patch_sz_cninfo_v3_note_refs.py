from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_sz_cninfo_parser_fix_v3.py")
text = path.read_text(encoding="utf-8")
old = '''    text = _NUMBER_PATTERN.sub(" ", text)
    text = re.sub(r"(^|\\s)[一二三四五六七八九十百]+(?=\\s|$)", " ", text)
'''
new = '''    text = _NUMBER_PATTERN.sub(" ", text)
    text = re.sub(r"[（(][A-Za-z][）)]", " ", text)
    text = re.sub(r"(^|\\s)[一二三四五六七八九十百]+(?=\\s|$)", " ", text)
'''
if old not in text and 're.sub(r"[（(][A-Za-z][）)]"' not in text:
    raise SystemExit("CNINFO v3 alphabetic note marker not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
