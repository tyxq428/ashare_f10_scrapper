from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_sse_summary_scope_fix.py")
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    runner,
    ''' + "'''" + '''                facts = parser.extract(path, document)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
''' + "'''" + ''',
    ''' + "'''" + '''                facts = parser.extract(path, document)
                document_scope_by_report_date[document.report_date] = classify_pdf_financial_scope(path)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
''' + "'''" + ''',
    "classify downloaded report financial scope",
)
'''
new = '''replace_once(
    runner,
    ''' + "'''" + '''        def parse_document(document):
            cache_path = parsed_cache_dir / f"{document.sha256}-{PARSER_CACHE_VERSION}.json"
''' + "'''" + ''',
    ''' + "'''" + '''        def parse_document(document):
            path = Path(document.local_path)
            document_scope_by_report_date[document.report_date] = classify_pdf_financial_scope(path)
            cache_path = parsed_cache_dir / f"{document.sha256}-{PARSER_CACHE_VERSION}.json"
''' + "'''" + ''',
    "classify downloaded report scope before cache lookup",
)
replace_once(
    runner,
    ''' + "'''" + '''            facts = parser.extract(document.local_path, document)
''' + "'''" + ''',
    ''' + "'''" + '''            facts = parser.extract(path, document)
''' + "'''" + ''',
    "use the classified PDF path for parsing",
)
'''
if old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
elif "classify downloaded report scope before cache lookup" not in text:
    raise SystemExit("runner cache marker not found in SSE summary materializer")

compatibility = Path(__file__).with_name("patch_sse_summary_materializer_v2.py")
exec(compile(compatibility.read_text(encoding="utf-8"), str(compatibility), "exec"))
