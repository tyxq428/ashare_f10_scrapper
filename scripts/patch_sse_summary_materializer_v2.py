from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("apply_sse_summary_scope_fix.py")
text = path.read_text(encoding="utf-8")
start_label = '    "display summary-only and pending periods",\n)\n'
end_label = '    "close nested lifecycle coverage expression",\n)\n'
start = text.find("replace_once(\n    lifecycle,\n    '''        else:\n")
if start < 0:
    if "classify formatted lifecycle period table" in text:
        raise SystemExit(0)
    raise SystemExit("formatted lifecycle replacement start not found")
first_end = text.find(start_label, start)
if first_end < 0:
    raise SystemExit("formatted lifecycle first replacement end not found")
second_start = first_end + len(start_label)
second_end = text.find(end_label, second_start)
if second_end < 0:
    raise SystemExit("formatted lifecycle second replacement end not found")
second_end += len(end_label)
replacement = '''replace_once(
    lifecycle,
    ''' + "'''" + '''        elif report_date in transition:
            period_class = "LISTING_TRANSITION_PERIOD"
            coverage_status = (
                "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
                if report_date in zero_extraction
                else ("AVAILABLE" if report_date in available else "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND")
            )
        else:
            period_class = "POST_LISTING_PERIODIC_EXPECTED"
            coverage_status = (
                "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
                if report_date in zero_extraction
                else (
                    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND"
                    if report_date in post_missing
                    else ("AVAILABLE" if report_date in available else "UNRESOLVED")
                )
            )
''' + "'''" + ''',
    ''' + "'''" + '''        elif report_date in transition:
            period_class = "LISTING_TRANSITION_PERIOD"
            if report_date in summary_only:
                coverage_status = "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP"
            elif report_date in zero_extraction:
                coverage_status = "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
            elif report_date in available:
                coverage_status = "AVAILABLE"
            else:
                coverage_status = "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND"
        elif report_date in pending:
            period_class = "POST_LISTING_PERIOD_NOT_YET_DISCLOSED"
            coverage_status = "OFFICIAL_REPORT_NOT_YET_DISCLOSED"
        else:
            period_class = "POST_LISTING_PERIODIC_EXPECTED"
            if report_date in summary_only:
                coverage_status = "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP"
            elif report_date in zero_extraction:
                coverage_status = "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
            elif report_date in post_missing:
                coverage_status = "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND"
            elif report_date in available:
                coverage_status = "AVAILABLE"
            else:
                coverage_status = "UNRESOLVED"
''' + "'''" + ''',
    "classify formatted lifecycle period table",
)
'''
path.write_text(text[:start] + replacement + text[second_end:], encoding="utf-8")
