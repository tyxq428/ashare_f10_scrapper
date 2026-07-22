from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            return
        raise SystemExit(f"{label} marker not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1. Official SSE listing lifecycle metadata.
sse = ROOT / "src/ashare_f10/validation/sources/sse.py"
replace_once(
    sse,
    'SSE_QUERY_URL = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"\n',
    'SSE_QUERY_URL = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"\n'
    'SSE_COMMON_QUERY_URL = "https://query.sse.com.cn/commonQuery.do"\n'
    'SSE_COMPANY_PROFILE_SQL_ID = "COMMON_SSE_CP_GPJCTPZ_GPLB_GPGK_GSGK_C"\n',
    "add SSE company profile endpoint",
)
profile_methods = '''    def _get_common_json(self, params: dict[str, str]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = self.session.get(
                    SSE_COMMON_QUERY_URL,
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                text = response.text.strip()
                try:
                    payload = response.json()
                except ValueError:
                    match = re.search(r"\\((\\{.*\\})\\)\\s*;?\\s*$", text, flags=re.S)
                    if not match:
                        raise OfficialSourceError(
                            f"SSE公司概况查询返回非JSON内容：{text[:200]}"
                        ) from None
                    payload = json.loads(match.group(1))
                if not isinstance(payload, dict):
                    raise OfficialSourceError("SSE公司概况查询返回结构不是对象")
                return payload
            except (requests.RequestException, ValueError, OfficialSourceError) as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(2**attempt)
        raise OfficialSourceError(f"SSE公司概况查询失败：{last_error}")

    def company_profile(self, security_code: str) -> dict[str, Any]:
        return self._get_common_json(
            {
                "isPagination": "false",
                "sqlId": SSE_COMPANY_PROFILE_SQL_ID,
                "COMPANY_CODE": security_code,
                "type": "inParams",
            }
        )

    def listing_date(self, security_code: str) -> tuple[str | None, dict[str, Any]]:
        payload = self.company_profile(security_code)
        candidates: list[str] = []
        for item in _iter_dicts(payload):
            for raw_key, raw_value in item.items():
                key = re.sub(r"[^A-Z0-9]", "_", str(raw_key).upper()).strip("_")
                if "DELIST" in key:
                    continue
                if key in {
                    "LISTING_DATE",
                    "LIST_DATE",
                    "LISTED_DATE",
                    "A_LIST_DATE",
                    "A_SHARE_LISTING_DATE",
                    "LISTINGDATE",
                    "LISTDATE",
                } or ("LIST" in key and "DATE" in key):
                    value = _date_text(raw_value)
                    if re.fullmatch(r"(?:19|20)\\d{2}-\\d{2}-\\d{2}", value):
                        candidates.append(value)
        return (min(candidates) if candidates else None), payload

'''
replace_once(
    sse,
    "    def list_reports(\n",
    profile_methods + "    def list_reports(\n",
    "add SSE company profile methods",
)

# 2. Status contract.
models = ROOT / "src/ashare_f10/cross_validation/models.py"
replace_once(
    models,
    '    "OFFICIAL_SOURCE_UNAVAILABLE",\n',
    '    "OFFICIAL_SOURCE_UNAVAILABLE",\n'
    '    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",\n'
    '    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",\n'
    '    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",\n',
    "add lifecycle coverage statuses",
)

# 3. Lifecycle post-processing and exportable period table.
lifecycle = ROOT / "src/ashare_f10/cross_validation/lifecycle.py"
text = lifecycle.read_text(encoding="utf-8")
append = '''


def apply_lifecycle_statuses(
    comparison: pd.DataFrame,
    source_status: dict[str, Any],
) -> pd.DataFrame:
    if comparison.empty or "status" not in comparison.columns:
        return comparison
    result = comparison.copy()
    dates = result.get("report_date", pd.Series(index=result.index, dtype="object"))
    date_values = dates.fillna("").astype(str).str[:10]
    pre_listing = set(source_status.get("pre_listing_report_dates") or [])
    zero_extraction = set(source_status.get("discovered_but_zero_extraction_dates") or [])
    post_listing_missing = set(source_status.get("post_listing_missing_report_dates") or [])

    pre_mask = date_values.isin(pre_listing) & result["status"].isin(
        ["MISSING_OFFICIAL", "OFFICIAL_PERIOD_NOT_LOADED", "PERIOD_CONFLICT"]
    )
    result.loc[pre_mask, "status"] = "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED"
    result.loc[pre_mask, "verification_grade"] = "N/A"
    result.loc[pre_mask, "notes"] = (
        "该期间早于证券上市日期，不存在同代码上市公司定期报告；"
        "应由招股说明书或发行上市申报文件验证，当前不判为来源冲突"
    )

    zero_mask = date_values.isin(zero_extraction) & result["status"].isin(
        ["MISSING_OFFICIAL", "OFFICIAL_PERIOD_NOT_LOADED"]
    )
    result.loc[zero_mask, "status"] = "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
    result.loc[zero_mask, "verification_grade"] = "E"
    result.loc[zero_mask, "notes"] = "官方定期报告已发现并下载，但当前解析器未提取到可比事实"

    missing_mask = date_values.isin(post_listing_missing) & result["status"].isin(
        ["MISSING_OFFICIAL", "OFFICIAL_PERIOD_NOT_LOADED"]
    )
    result.loc[missing_mask, "status"] = "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND"
    result.loc[missing_mask, "verification_grade"] = "E"
    result.loc[missing_mask, "notes"] = "证券已上市且该期间理论上应有定期报告，但官方查询未发现对应文件"
    return result


def lifecycle_period_frame(source_status: dict[str, Any]) -> pd.DataFrame:
    lifecycle = source_status.get("security_lifecycle") or {}
    requested = lifecycle.get("requested_report_dates") or source_status.get("requested_report_dates") or []
    pre_listing = set(lifecycle.get("pre_listing_report_dates") or source_status.get("pre_listing_report_dates") or [])
    transition = set(lifecycle.get("listing_transition_report_dates") or [])
    available = set(source_status.get("available_report_dates") or [])
    zero_extraction = set(source_status.get("discovered_but_zero_extraction_dates") or [])
    post_missing = set(source_status.get("post_listing_missing_report_dates") or [])
    extraction = source_status.get("extraction_by_report_date") or {}
    rows: list[dict[str, Any]] = []
    for report_date in requested:
        if report_date in pre_listing:
            period_class = "PRE_LISTING_PERIOD"
            coverage_status = "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED"
        elif report_date in transition:
            period_class = "LISTING_TRANSITION_PERIOD"
            coverage_status = "OFFICIAL_DOCUMENT_EXTRACTION_FAILED" if report_date in zero_extraction else (
                "AVAILABLE" if report_date in available else "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND"
            )
        else:
            period_class = "POST_LISTING_PERIODIC_EXPECTED"
            coverage_status = "OFFICIAL_DOCUMENT_EXTRACTION_FAILED" if report_date in zero_extraction else (
                "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND" if report_date in post_missing else (
                    "AVAILABLE" if report_date in available else "UNRESOLVED"
                )
            )
        rows.append(
            {
                "security_code": lifecycle.get("security_code") or "",
                "exchange": lifecycle.get("exchange") or source_status.get("exchange") or "",
                "listing_date": lifecycle.get("listing_date"),
                "listing_date_source": lifecycle.get("listing_date_source") or "",
                "report_date": report_date,
                "period_class": period_class,
                "coverage_status": coverage_status,
                "official_document_found": report_date in available,
                "extracted_fact_count": int(extraction.get(report_date) or 0),
            }
        )
    return pd.DataFrame(rows)
'''
if "def apply_lifecycle_statuses(" not in text:
    lifecycle.write_text(text.rstrip() + append + "\n", encoding="utf-8")

# 4. Runner: resolve official listing date, query only applicable periodic reports,
# classify gaps and preserve the complete lifecycle in outputs.
runner = ROOT / "src/ashare_f10/cross_validation/runner.py"
replace_once(
    runner,
    "from ashare_f10.cross_validation.exporter import CrossValidationExporter\n",
    "from ashare_f10.cross_validation.exporter import CrossValidationExporter\n"
    "from ashare_f10.cross_validation.lifecycle import (\n"
    "    apply_lifecycle_statuses,\n"
    "    build_security_lifecycle,\n"
    "    infer_listing_date_from_eastmoney,\n"
    ")\n",
    "import lifecycle helpers",
)
replace_once(
    runner,
    '''        self._notify(
            "OFFICIAL_DISCOVERY",
            requested_report_dates=report_dates,
            official_source=source_name,
        )
        source_class = type(source)
        available = source.list_reports(
            self.stock_code,
            begin_date=f"{min(report_dates)[:4]}-01-01",
            end_date=utc_now()[:10],
        )
        selected = []
        for report_date in report_dates:
''',
    '''        listing_date = None
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
        selected = []
        for report_date in periodic_report_dates:
''',
    "integrate lifecycle into report discovery",
)
replace_once(
    runner,
    '''        extraction_by_document: dict[str, int] = {}
        parser_cache_hits = 0
''',
    '''        extraction_by_document: dict[str, int] = {}
        extraction_by_report_date: dict[str, int] = {}
        parser_cache_hits = 0
''',
    "track extraction by report date",
)
replace_once(
    runner,
    '''                extraction_by_document[document.title] = len(facts)
                official_records.extend(fact.to_dict() for fact in facts)
''',
    '''                extraction_by_document[document.title] = len(facts)
                extraction_by_report_date[document.report_date] = len(facts)
                official_records.extend(fact.to_dict() for fact in facts)
''',
    "record report-date extraction counts",
)
replace_once(
    runner,
    '''        source_status = {
            "source": source_name,
            "exchange": identity.exchange,
            "requested_report_dates": report_dates,
            "available_report_dates": sorted({item.report_date for item in downloaded}),
            "missing_report_dates": sorted(set(report_dates) - {item.report_date for item in downloaded}),
            "document_count": len(downloaded),
            "official_fact_count": len(official),
            "extraction_by_document": extraction_by_document,
            "parser_cache_hits": parser_cache_hits,
            "parser_cache_version": PARSER_CACHE_VERSION,
            "available_document_count": len(available),
        }
''',
    '''        available_dates = sorted({item.report_date for item in downloaded})
        post_listing_missing = sorted(set(periodic_report_dates) - set(available_dates))
        zero_extraction_dates = sorted(
            report_date for report_date, count in extraction_by_report_date.items() if count == 0
        )
        source_status = {
            "source": source_name,
            "exchange": identity.exchange,
            "requested_report_dates": report_dates,
            "periodic_expected_report_dates": periodic_report_dates,
            "pre_listing_report_dates": lifecycle.pre_listing_report_dates,
            "available_report_dates": available_dates,
            # Backward-compatible field now means a true post-listing discovery gap.
            "missing_report_dates": post_listing_missing,
            "post_listing_missing_report_dates": post_listing_missing,
            "discovered_but_zero_extraction_dates": zero_extraction_dates,
            "document_count": len(downloaded),
            "official_fact_count": len(official),
            "extraction_by_document": extraction_by_document,
            "extraction_by_report_date": extraction_by_report_date,
            "parser_cache_hits": parser_cache_hits,
            "parser_cache_version": PARSER_CACHE_VERSION,
            "available_document_count": len(available),
            "security_lifecycle": lifecycle.to_dict(),
            "listing_profile_error": listing_profile_error,
            "pre_listing_alternative_source_status": "NOT_LOADED",
        }
''',
    "write lifecycle-aware source status",
)
replace_once(
    runner,
    '''        comparison = comparator.compare(eastmoney, official)
        source_unavailable = source_status.get("source") == "UNAVAILABLE"
''',
    '''        comparison = comparator.compare(eastmoney, official)
        comparison = apply_lifecycle_statuses(comparison, source_status)
        source_unavailable = source_status.get("source") == "UNAVAILABLE"
''',
    "apply lifecycle statuses before summary",
)
replace_once(
    runner,
    '''                    "FUTURE_FREE_SOURCE_REQUIRED",
                ]
''',
    '''                    "FUTURE_FREE_SOURCE_REQUIRED",
                    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
                    "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
                    "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                ]
''',
    "include lifecycle gaps in acceptance status",
)

# 5. Comparable metric excludes periods that were not yet listed.
comparator = ROOT / "src/ashare_f10/cross_validation/comparator.py"
replace_once(
    comparator,
    '                    "OFFICIAL_SOURCE_UNAVAILABLE",\n',
    '                    "OFFICIAL_SOURCE_UNAVAILABLE",\n'
    '                    "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",\n',
    "exclude pre-listing records from theoretical comparable count",
)

# 6. Excel and DuckDB lifecycle views.
exporter = ROOT / "src/ashare_f10/cross_validation/exporter.py"
replace_once(
    exporter,
    "from ashare_f10.cross_validation.models import CrossValidationArtifacts\n",
    "from ashare_f10.cross_validation.lifecycle import lifecycle_period_frame\n"
    "from ashare_f10.cross_validation.models import CrossValidationArtifacts\n",
    "import lifecycle period frame",
)
replace_once(
    exporter,
    '''    documents: pd.DataFrame,
) -> None:
''',
    '''    documents: pd.DataFrame,
    report_period_lifecycle: pd.DataFrame,
) -> None:
''',
    "extend DuckDB writer signature",
)
replace_once(
    exporter,
    '''            "documents": documents,
        }.items():
''',
    '''            "documents": documents,
            "report_period_lifecycle": report_period_lifecycle,
        }.items():
''',
    "write lifecycle DuckDB table",
)
replace_once(
    exporter,
    '''        summary_frame = pd.DataFrame([summary])
        comparison_columns = [
''',
    '''        summary_frame = pd.DataFrame([summary])
        period_lifecycle = lifecycle_period_frame(summary.get("official_source_status") or {})
        comparison_columns = [
''',
    "build lifecycle Excel frame",
)
replace_once(
    exporter,
    '''            comparison_excel_frame[comparison_excel_frame["status"] == "OFFICIAL_PERIOD_NOT_LOADED"]
''',
    '''            comparison_excel_frame[
                comparison_excel_frame["status"].isin(
                    [
                        "OFFICIAL_PERIOD_NOT_LOADED",
                        "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
                        "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
                        "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                    ]
                )
            ]
''',
    "expand report gap summary statuses",
)
replace_once(
    exporter,
    '''            ("05_官方未提取汇总", missing_official_summary),
            ("06_未加载报告期汇总", unavailable_summary),
''',
    '''            ("05_官方未提取汇总", missing_official_summary),
            ("06_报告期生命周期", period_lifecycle),
            ("06A_报告缺口汇总", unavailable_summary),
''',
    "add lifecycle Excel sheet",
)
replace_once(
    exporter,
    '''            documents,
        )
''',
    '''            documents,
            period_lifecycle,
        )
''',
    "pass lifecycle into DuckDB writer",
)

# 7. Web status filters and metric naming.
index = ROOT / "src/ashare_f10/web/index.html"
replace_once(
    index,
    '<option value="OFFICIAL_PERIOD_NOT_LOADED">官方报告期未加载（OFFICIAL_PERIOD_NOT_LOADED）</option>',
    '<option value="OFFICIAL_PERIOD_NOT_LOADED">官方报告期未加载（OFFICIAL_PERIOD_NOT_LOADED）</option>'
    '<option value="PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED">上市前官方替代来源未加载（PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED）</option>'
    '<option value="OFFICIAL_DOCUMENT_EXTRACTION_FAILED">官方文档已找到但解析失败（OFFICIAL_DOCUMENT_EXTRACTION_FAILED）</option>'
    '<option value="POST_LISTING_OFFICIAL_REPORT_NOT_FOUND">上市后官方报告未发现（POST_LISTING_OFFICIAL_REPORT_NOT_FOUND）</option>',
    "add lifecycle statuses to Web filter",
)

# 8. Verifier requires lifecycle table and guarantees pre-listing dates are not
# reported as ordinary missing periodic reports.
verify = ROOT / "scripts/verify_full_cross_validation.py"
replace_once(
    verify,
    '            "documents",\n',
    '            "documents",\n            "report_period_lifecycle",\n',
    "require lifecycle DuckDB table",
)

# 9. Unit tests for lifecycle status post-processing.
test_path = ROOT / "tests/test_security_lifecycle_statuses.py"
if not test_path.exists():
    test_path.write_text(
        '''from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.lifecycle import apply_lifecycle_statuses, lifecycle_period_frame


def test_lifecycle_statuses_separate_prelisting_and_parser_gaps() -> None:
    comparison = pd.DataFrame(
        [
            {"report_date": "2019-12-31", "status": "OFFICIAL_PERIOD_NOT_LOADED", "verification_grade": "E", "notes": ""},
            {"report_date": "2020-09-30", "status": "MISSING_OFFICIAL", "verification_grade": "E", "notes": ""},
            {"report_date": "2021-06-30", "status": "OFFICIAL_PERIOD_NOT_LOADED", "verification_grade": "E", "notes": ""},
        ]
    )
    source_status = {
        "pre_listing_report_dates": ["2019-12-31"],
        "discovered_but_zero_extraction_dates": ["2020-09-30"],
        "post_listing_missing_report_dates": ["2021-06-30"],
    }
    result = apply_lifecycle_statuses(comparison, source_status)
    assert result["status"].tolist() == [
        "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
        "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
        "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
    ]


def test_lifecycle_period_frame_is_complete() -> None:
    source_status = {
        "exchange": "SH",
        "security_lifecycle": {
            "security_code": "688521",
            "exchange": "SH",
            "listing_date": "2020-08-18",
            "listing_date_source": "SSE_COMPANY_PROFILE",
            "requested_report_dates": ["2019-12-31", "2020-09-30", "2020-12-31"],
            "pre_listing_report_dates": ["2019-12-31"],
            "periodic_expected_report_dates": ["2020-09-30", "2020-12-31"],
            "listing_transition_report_dates": ["2020-09-30"],
        },
        "available_report_dates": ["2020-09-30", "2020-12-31"],
        "discovered_but_zero_extraction_dates": ["2020-09-30"],
        "post_listing_missing_report_dates": [],
        "extraction_by_report_date": {"2020-09-30": 0, "2020-12-31": 91},
    }
    frame = lifecycle_period_frame(source_status)
    assert len(frame) == 3
    assert frame.loc[frame["report_date"] == "2019-12-31", "coverage_status"].iloc[0] == "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED"
    assert frame.loc[frame["report_date"] == "2020-09-30", "coverage_status"].iloc[0] == "OFFICIAL_DOCUMENT_EXTRACTION_FAILED"
    assert frame.loc[frame["report_date"] == "2020-12-31", "coverage_status"].iloc[0] == "AVAILABLE"
''',
        encoding="utf-8",
    )

print("SSE lifecycle patch materialized")
