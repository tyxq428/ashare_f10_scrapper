from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"missing replacement anchor: {label}")
    return text.replace(old, new, 1)


def patch_runner() -> None:
    path = Path("src/ashare_f10/cross_validation/runner.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from ashare_f10.cross_validation.exporter import CrossValidationExporter\n"
        "from ashare_f10.cross_validation.process_policy import ensure_process_policy\n",
        "from ashare_f10.cross_validation.exporter import CrossValidationExporter\n"
        "from ashare_f10.cross_validation.lifecycle import (\n"
        "    apply_lifecycle_statuses,\n"
        "    build_security_lifecycle,\n"
        "    infer_listing_date_from_eastmoney,\n"
        ")\n"
        "from ashare_f10.cross_validation.process_policy import ensure_process_policy\n",
        "runner lifecycle imports",
    )
    text = replace_once(
        text,
        "from ashare_f10.validation.documents.pdf_parser import PdfStatementParser\n",
        "from ashare_f10.validation.documents.pdf_parser import (\n"
        "    PdfStatementParser,\n"
        "    classify_pdf_financial_scope,\n"
        ")\n",
        "runner parser imports",
    )
    text = text.replace('PARSER_CACHE_VERSION = "1.7.0"', 'PARSER_CACHE_VERSION = "1.10.0"', 1)

    start = text.index('        self._notify(\n            "OFFICIAL_DISCOVERY",')
    end = text.index('        document_dir = self.output_dir / "source_documents"', start)
    discovery = '''        listing_date = None
        listing_date_source = ""
        listing_profile_error = ""
        listing_profile: dict[str, Any] = {}
        if source_name == "SSE" and hasattr(source, "listing_date"):
            try:
                listing_date, listing_profile = source.listing_date(self.stock_code)
                if listing_date:
                    listing_date_source = "SSE_COMPANY_PROFILE"
            except Exception as exc:  # noqa: BLE001
                listing_profile_error = f"{type(exc).__name__}: {exc}"
        if not listing_date:
            listing_date, listing_date_source = infer_listing_date_from_eastmoney(eastmoney)
        lifecycle = build_security_lifecycle(
            self.stock_code,
            identity.exchange,
            report_dates,
            listing_date,
            listing_date_source,
        )
        periodic_report_dates = lifecycle.periodic_expected_report_dates
        if listing_profile:
            metadata_dir = self.output_dir / "source_metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            (metadata_dir / "sse_company_profile.json").write_text(
                json.dumps(listing_profile, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        self._notify(
            "OFFICIAL_DISCOVERY",
            requested_report_dates=report_dates,
            periodic_expected_report_dates=periodic_report_dates,
            pre_listing_report_dates=lifecycle.pre_listing_report_dates,
            listing_date=lifecycle.listing_date,
            official_source=source_name,
            as_of_date=self.as_of_date,
        )
        source_class = type(source)
        available = (
            source.list_reports(
                self.stock_code,
                begin_date=f"{min(periodic_report_dates)[:4]}-01-01",
                end_date=utc_now()[:10],
            )
            if periodic_report_dates
            else []
        )
        selection = select_report_versions(
            available,
            periodic_report_dates,
            as_of_date=self.as_of_date,
        )
        selected = selection.selected

'''
    text = text[:start] + discovery + text[end:]
    text = replace_once(
        text,
        "        def parse_document(document):\n"
        "            cache_path = parsed_cache_dir / f\"{document.sha256}-{PARSER_CACHE_VERSION}.json\"\n",
        "        def parse_document(document):\n"
        "            document_path = Path(document.local_path)\n"
        "            document_scope_by_report_date[document.report_date] = (\n"
        "                classify_pdf_financial_scope(document_path)\n"
        "            )\n"
        "            cache_path = parsed_cache_dir / f\"{document.sha256}-{PARSER_CACHE_VERSION}.json\"\n",
        "runner document scope",
    )
    text = replace_once(
        text,
        "            facts = parser.extract(document.local_path, document)\n",
        "            facts = parser.extract(document_path, document)\n",
        "runner parser path",
    )
    text = replace_once(
        text,
        "        official_records: list[dict[str, Any]] = []\n"
        "        extraction_by_document: dict[str, int] = {}\n"
        "        parser_cache_hits = 0\n",
        "        official_records: list[dict[str, Any]] = []\n"
        "        extraction_by_document: dict[str, int] = {}\n"
        "        extraction_by_report_date: dict[str, int] = {}\n"
        "        document_scope_by_report_date: dict[str, str] = {}\n"
        "        parser_cache_hits = 0\n",
        "runner extraction maps",
    )
    text = replace_once(
        text,
        "                extraction_by_document[document.title] = len(facts)\n"
        "                official_records.extend(fact.to_dict() for fact in facts)\n",
        "                extraction_by_document[document.title] = len(facts)\n"
        "                extraction_by_report_date[document.report_date] = len(facts)\n"
        "                official_records.extend(fact.to_dict() for fact in facts)\n",
        "runner extraction periods",
    )

    start = text.index('        source_status = {\n', text.index('        documents_frame ='))
    end = text.index('        return official, documents_frame, source_status\n', start)
    source_status = '''        available_dates = sorted({item.report_date for item in downloaded})
        expected_missing = set(periodic_report_dates) - set(available_dates)
        latest_available = max(available_dates or [""])
        not_yet_disclosed = sorted(
            report_date
            for report_date in expected_missing
            if latest_available and report_date > latest_available
        )
        post_listing_missing = sorted(expected_missing - set(not_yet_disclosed))
        summary_only_dates = sorted(
            report_date
            for report_date, scope in document_scope_by_report_date.items()
            if scope == "SUMMARY_ONLY"
        )
        zero_extraction_dates = sorted(
            report_date
            for report_date, count in extraction_by_report_date.items()
            if count == 0 and report_date not in summary_only_dates
        )
        source_status = {
            "source": source_name,
            "exchange": identity.exchange,
            "as_of_date": self.as_of_date,
            "requested_report_dates": report_dates,
            "periodic_expected_report_dates": periodic_report_dates,
            "pre_listing_report_dates": lifecycle.pre_listing_report_dates,
            "available_report_dates": available_dates,
            "missing_report_dates": post_listing_missing,
            "post_listing_missing_report_dates": post_listing_missing,
            "not_yet_disclosed_report_dates": not_yet_disclosed,
            "discovered_but_zero_extraction_dates": zero_extraction_dates,
            "summary_only_report_dates": summary_only_dates,
            "document_scope_by_report_date": document_scope_by_report_date,
            "document_count": len(downloaded),
            "boundary_document_count": len(selection.boundary),
            "boundary_documents": [asdict(item) for item in selection.boundary],
            "document_selection_decisions": selection.decisions,
            "official_fact_count": len(official),
            "parse_suspect_count": parse_suspect_count,
            "extraction_by_document": extraction_by_document,
            "extraction_by_report_date": extraction_by_report_date,
            "parser_cache_hits": parser_cache_hits,
            "parser_cache_version": PARSER_CACHE_VERSION,
            "available_document_count": len(available),
            "security_lifecycle": lifecycle.to_dict(),
            "listing_profile_error": listing_profile_error,
            "pre_listing_alternative_source_status": "NOT_LOADED",
        }
'''
    text = text[:start] + source_status + text[end:]
    text = replace_once(
        text,
        "        comparison = comparator.compare(eastmoney, official)\n"
        "        source_unavailable = source_status.get(\"source\") == \"UNAVAILABLE\"\n",
        "        comparison = comparator.compare(eastmoney, official)\n"
        "        comparison = apply_lifecycle_statuses(comparison, source_status)\n"
        "        source_status[\"not_yet_disclosed_report_dates\"] = sorted(\n"
        "            {\n"
        "                str(value)[:10]\n"
        "                for value in comparison.loc[\n"
        "                    comparison[\"status\"] == \"OFFICIAL_REPORT_NOT_YET_DISCLOSED\",\n"
        "                    \"report_date\",\n"
        "                ]\n"
        "                if value not in (None, \"\") and not pd.isna(value)\n"
        "            }\n"
        "        )\n"
        "        source_unavailable = source_status.get(\"source\") == \"UNAVAILABLE\"\n",
        "runner lifecycle statuses",
    )
    text = replace_once(
        text,
        '                    "FUTURE_FREE_SOURCE_REQUIRED",\n',
        '                    "FUTURE_FREE_SOURCE_REQUIRED",\n'
        '                    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",\n'
        '                    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",\n'
        '                    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",\n'
        '                    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",\n'
        '                    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",\n',
        "runner unresolved statuses",
    )
    path.write_text(text, encoding="utf-8")


def patch_comparator() -> None:
    path = Path("src/ashare_f10/cross_validation/comparator.py")
    text = path.read_text(encoding="utf-8")
    start = text.index("NON_COMPARABLE_STATUSES = {")
    end = text.index("\n\nFAMILY_PRIORITY", start)
    constants = '''NON_COMPARABLE_STATUSES = {
    "NOT_IN_OFFICIAL_SCOPE",
    "SOURCE_SPECIFIC",
    "FUTURE_FREE_SOURCE_REQUIRED",
    "OFFICIAL_PERIOD_NOT_LOADED",
    "OFFICIAL_SOURCE_UNAVAILABLE",
    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",
    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",
}
UNRESOLVED_STATUSES = {
    "MISSING_OFFICIAL",
    "MISSING_EASTMONEY",
    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
    "UNRESOLVED",
}'''
    text = text[:start] + constants + text[end:]
    text = replace_once(
        text,
        "                official_num, official_unit = _normalize_numeric(official_value_num, official_unit)\n"
        "                is_text_method = comparison_method in {\"date\", \"text\", \"set\"}\n",
        "                official_num, official_unit = _normalize_numeric(official_value_num, official_unit)\n"
        "                if (\n"
        "                    comparison_method == \"text\"\n"
        "                    and mode == \"OFFICIAL_DERIVED\"\n"
        "                    and east_num is not None\n"
        "                    and official_num is not None\n"
        "                ):\n"
        "                    comparison_method = \"numeric\"\n"
        "                is_text_method = comparison_method in {\"date\", \"text\", \"set\"}\n",
        "derived numeric fallback",
    )
    text = replace_once(
        text,
        "                        grade = \"A\" if status in MATCH_STATUSES else \"E\"\n"
        "                else:\n",
        "                        grade = \"A\" if status in MATCH_STATUSES else \"E\"\n"
        "                        if status == \"MISMATCH\" and east_num == 0 and official_num != 0:\n"
        "                            notes = (\n"
        "                                f\"{notes}；东方财富明确返回0，但免费官方正式披露为非零；\"\n"
        "                                \"保留为可追溯来源冲突，不自动覆盖或隐藏\"\n"
        "                            )\n"
        "                else:\n",
        "explicit zero conflict note",
    )
    path.write_text(text, encoding="utf-8")


def patch_models_and_tests() -> None:
    models_path = Path("src/ashare_f10/cross_validation/models.py")
    models = models_path.read_text(encoding="utf-8")
    models = replace_once(
        models,
        '    "OFFICIAL_SOURCE_UNAVAILABLE",\n',
        '    "OFFICIAL_SOURCE_UNAVAILABLE",\n'
        '    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",\n'
        '    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",\n'
        '    "OFFICIAL_REPORT_SUMMARY_SCOPE_GAP",\n'
        '    "OFFICIAL_REPORT_NOT_YET_DISCLOSED",\n'
        '    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",\n',
        "lifecycle comparison statuses",
    )
    models_path.write_text(models, encoding="utf-8")

    test_path = Path("tests/test_comparison_policy.py")
    test = test_path.read_text(encoding="utf-8")
    marker = "def test_official_derived_numeric_values_override_accidental_text_policy"
    if marker not in test:
        test += '''


def test_official_derived_numeric_values_override_accidental_text_policy() -> None:
    entry = _registry_entry("NETPROFIT", "净利润")
    entry.validation_mode = "OFFICIAL_DERIVED"
    entry.family = "RPT_F10_FINANCE_DUPONT"
    entry.dataset = "dupont"
    entry.statement_type = "dupont"
    entry.data_semantics = "event"
    entry.comparison_method = "text"
    entry.absolute_tolerance = 1.0

    east = _eastmoney_row("NETPROFIT", "净利润", value_num=100.0, value_text="100")
    east.update(
        family="RPT_F10_FINANCE_DUPONT",
        dataset="dupont",
        statement_type="dupont",
        data_semantics="event",
    )
    official = _official_row(
        "NETPROFIT", "净利润", value_num=100.0, value_text="100.0", unit="元"
    )
    official["statement_type"] = "dupont"

    result = _compare(entry, east, official)
    assert result["status"] == "DERIVED_MATCH"
    assert result["comparison_method"] == "numeric"
    assert result["root_cause"] == "VALUE_MATCH"
'''
        test_path.write_text(test, encoding="utf-8")


def patch_api_workflow_and_navigation() -> None:
    Path("src/ashare_f10/api/app_with_raw_pack.py").write_text(
        '''from __future__ import annotations

from starlette.routing import Mount

from ashare_f10.api.app import app
from ashare_f10.api.raw_pack import router as raw_pack_router
from ashare_f10.api.research_pack import router as research_pack_router
from ashare_f10.api.visual_execution import router as visual_execution_router

# The existing SPA is mounted at "/" as the final route. Insert API routes before
# that catch-all mount without changing the stable base app used by older tests.
static_mounts = [
    route for route in app.router.routes if isinstance(route, Mount) and route.path in {"", "/"}
]
for route in static_mounts:
    app.router.routes.remove(route)
app.include_router(raw_pack_router)
app.include_router(visual_execution_router)
app.include_router(research_pack_router)
app.router.routes.extend(static_mounts)
app.version = "0.6.0"
''',
        encoding="utf-8",
    )
    Path(".github/workflows/test.yml").write_text(
        '''name: Test

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: python -m pip install --upgrade pip
      - run: pip install -e ".[dev]"
      - run: python -m compileall -q src scripts
      - name: Validate browser JavaScript and static search worker
        run: |
          node --check src/ashare_f10/web/research-grid.js
          node --check src/ashare_f10/web/static-search-worker.js
          node --check src/ashare_f10/web/app.js
          node --check src/ashare_f10/web/job-center-v2.js
          node --check src/ashare_f10/web/raw-pack.js
          node --check src/ashare_f10/web/run.js
          node --check src/ashare_f10/web/research-pack.js
          node tests/static-search-worker-smoke.cjs
      - name: Run Ruff
        run: |
          set -o pipefail
          ruff check src tests scripts/run_resilient_fetch.py scripts/run_resilient_command.py --output-format=concise 2>&1 | tee ruff-output.txt
      - name: Upload lint diagnostics
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: lint-diagnostics-${{ github.run_id }}
          path: ruff-output.txt
          if-no-files-found: warn
          retention-days: 7
      - run: pytest --cov=ashare_f10 --cov-report=term-missing
''',
        encoding="utf-8",
    )
    index_path = Path("src/ashare_f10/web/index.html")
    index = index_path.read_text(encoding="utf-8")
    link = '    <button type="button" onclick="window.location.href=\'./research-pack.html\'">Research Pack</button>\n'
    anchor = '    <button data-tab="validation">官方交叉验证</button>\n'
    if link not in index:
        index = replace_once(index, anchor, anchor + link, "Research Pack navigation")
        index_path.write_text(index, encoding="utf-8")


def main() -> None:
    patch_runner()
    patch_comparator()
    patch_models_and_tests()
    patch_api_workflow_and_navigation()


if __name__ == "__main__":
    main()
