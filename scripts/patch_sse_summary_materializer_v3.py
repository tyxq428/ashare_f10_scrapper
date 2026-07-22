from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_sse_summary_scope_fix.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    parser,
    ''' + "'''" + '''        unit: tuple[str, float],
        scope: str,
    ) -> OfficialFact | None:
''' + "'''" + ''',
    ''' + "'''" + '''        unit: tuple[str, float],
        scope: str,
        max_width: int = 3,
    ) -> OfficialFact | None:
''' + "'''" + ''',
    "parameterize text window width",
)
'''
new = '''replace_once(
    parser,
    ''' + "'''" + '''    def _extract_from_text(
        self,
        text: str,
        target: TargetField,
        document: OfficialDocument,
        page_number: int,
        unit: tuple[str, float],
        scope: str,
    ) -> OfficialFact | None:
''' + "'''" + ''',
    ''' + "'''" + '''    def _extract_from_text(
        self,
        text: str,
        target: TargetField,
        document: OfficialDocument,
        page_number: int,
        unit: tuple[str, float],
        scope: str,
        max_width: int = 3,
    ) -> OfficialFact | None:
''' + "'''" + ''',
    "parameterize PDF text window width",
)
'''
if old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
elif "parameterize PDF text window width" not in text:
    raise SystemExit("PDF text extractor parameter marker not found")
