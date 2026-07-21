from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected patch anchor not found in {path}: {old[:120]!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    "from ashare_f10.validation.sources.sse import SSEOfficialSource\n",
    "from ashare_f10.validation.sources.cninfo import CNInfoOfficialSource\n"
    "from ashare_f10.validation.sources.sse import SSEOfficialSource\n",
)
replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    'PARSER_CACHE_VERSION = "1.2.0"',
    'PARSER_CACHE_VERSION = "1.3.0"',
)
replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    '''        identity = parse_security(self.stock_code)
        if identity.exchange != "SH":
            return (
                official_fact_columns(pd.DataFrame()),
                pd.DataFrame(),
                {
                    "source": "UNAVAILABLE",
                    "exchange": identity.exchange,
                    "requested_report_dates": report_dates,
                    "available_report_dates": [],
                    "missing_report_dates": report_dates,
                    "message": (
                        f"{identity.exchange}官方披露适配器尚未接入；"
                        "字段仍完成100%分类，但不伪造官方数值，也不判定为来源冲突"
                    ),
                },
            )

        self._notify("OFFICIAL_DISCOVERY", requested_report_dates=report_dates)
        source = SSEOfficialSource(timeout=60)
''',
    '''        identity = parse_security(self.stock_code)
        if identity.exchange == "SH":
            source = SSEOfficialSource(timeout=60)
            source_name = "SSE"
        elif identity.exchange == "SZ":
            source = CNInfoOfficialSource(timeout=60)
            source_name = "CNINFO"
        else:
            return (
                official_fact_columns(pd.DataFrame()),
                pd.DataFrame(),
                {
                    "source": "UNAVAILABLE",
                    "exchange": identity.exchange,
                    "requested_report_dates": report_dates,
                    "available_report_dates": [],
                    "missing_report_dates": report_dates,
                    "message": (
                        f"{identity.exchange}官方披露适配器尚未接入；"
                        "字段完成分类，但官方数值不可用，不参与双源匹配"
                    ),
                },
            )

        self._notify(
            "OFFICIAL_DISCOVERY",
            requested_report_dates=report_dates,
            official_source=source_name,
        )
        source_class = type(source)
''',
)
replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    "            return SSEOfficialSource(timeout=60).download(copy.copy(document), document_dir)\n",
    "            return source_class(timeout=60).download(copy.copy(document), document_dir)\n",
)
replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    '            "source": "SSE",\n',
    '            "source": source_name,\n',
)
replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    '''        comparison = comparator.compare(eastmoney, official)
        compare_summary = comparator.summary(comparison)
''',
    '''        comparison = comparator.compare(eastmoney, official)
        source_unavailable = source_status.get("source") == "UNAVAILABLE"
        if source_unavailable:
            unavailable_mask = comparison["status"] == "MISSING_OFFICIAL"
            comparison.loc[unavailable_mask, "status"] = "OFFICIAL_SOURCE_UNAVAILABLE"
            comparison.loc[unavailable_mask, "verification_grade"] = "N/A"
            explanation = str(source_status.get("message") or "官方披露来源不可用")
            comparison.loc[unavailable_mask, "notes"] = explanation
        compare_summary = comparator.summary(comparison)
''',
)
replace_once(
    "src/ashare_f10/cross_validation/runner.py",
    '''        elif coverage["classification_coverage"] < 1.0:
            summary["acceptance_status"] = "FAIL_CLASSIFICATION_COVERAGE"
        elif unresolved:
''',
    '''        elif coverage["classification_coverage"] < 1.0:
            summary["acceptance_status"] = "FAIL_CLASSIFICATION_COVERAGE"
        elif source_unavailable:
            summary["acceptance_status"] = "PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE"
        elif unresolved:
''',
)

replace_once(
    "src/ashare_f10/validation/runner.py",
    "from ashare_f10.validation.reporting import ValidationReportWriter\n"
    "from ashare_f10.validation.sources.sse import SSEOfficialSource\n",
    "from ashare_f10.fetch.security import parse_security\n"
    "from ashare_f10.validation.reporting import ValidationReportWriter\n"
    "from ashare_f10.validation.sources.cninfo import CNInfoOfficialSource\n"
    "from ashare_f10.validation.sources.sse import SSEOfficialSource\n",
)
replace_once(
    "src/ashare_f10/validation/runner.py",
    '''        source = SSEOfficialSource()
        documents = source.select_reports(
''',
    '''        exchange = parse_security(self.stock_code).exchange
        if exchange == "SH":
            source = SSEOfficialSource()
        elif exchange == "SZ":
            source = CNInfoOfficialSource()
        else:
            raise RuntimeError(f"{exchange}官方披露适配器尚未接入")
        documents = source.select_reports(
''',
)

replace_once(
    "src/ashare_f10/cross_validation/models.py",
    '    "OFFICIAL_PERIOD_NOT_LOADED",\n',
    '    "OFFICIAL_PERIOD_NOT_LOADED",\n    "OFFICIAL_SOURCE_UNAVAILABLE",\n',
)
replace_once(
    "src/ashare_f10/cross_validation/comparator.py",
    '                    "OFFICIAL_PERIOD_NOT_LOADED",\n',
    '                    "OFFICIAL_PERIOD_NOT_LOADED",\n                    "OFFICIAL_SOURCE_UNAVAILABLE",\n',
)

replace_once(
    "src/ashare_f10/web/index.html",
    '''          <input id="validationCode" maxlength="6" value="688521" placeholder="例如：688521" />
          <button id="startValidation" class="primary">开始完整交叉验证</button>
''',
    '''          <input id="validationCode" maxlength="6" value="688521" placeholder="例如：688521" />
          <label>官方报告期数 <input id="validationMaxPeriods" type="number" min="2" max="80" value="2" title="首次建议2；留空表示全部可发现报告期" /></label>
          <button id="startValidation" class="primary">开始完整交叉验证</button>
''',
)
replace_once(
    "src/ashare_f10/web/index.html",
    '''      <div id="validationProgress" class="panel result-box">尚未创建验证任务</div>
      <div id="validationMetrics" class="metric-grid"></div>
''',
    '''      <div id="validationProgress" class="panel result-box">尚未创建验证任务</div>
      <div id="validationNotice" class="panel" hidden></div>
      <div id="validationMetrics" class="metric-grid"></div>
''',
)
replace_once(
    "src/ashare_f10/web/index.html",
    '<option>MISSING_OFFICIAL</option><option>MISSING_EASTMONEY</option>',
    '<option>MISSING_OFFICIAL</option><option>OFFICIAL_SOURCE_UNAVAILABLE</option><option>MISSING_EASTMONEY</option>',
)

js_path = Path("src/ashare_f10/web/cross-validation.js")
js = js_path.read_text(encoding="utf-8")
old_metrics = '''  function renderMetrics(summary) {
    const metrics = [
      ["字段分类覆盖率", `${((summary.classification_coverage || 0) * 100).toFixed(2)}%`],
      ["东方财富事实", summary.eastmoney_fact_count || 0],
      ["官方事实", summary.official_fact_count || 0],
      ["可比记录", summary.comparable_count || 0],
      ["已匹配", summary.matched_count || 0],
      ["真正冲突", summary.true_conflict_count || 0],
      ["验收状态", summary.acceptance_status || "—"],
    ];
    byId("validationMetrics").innerHTML = metrics
      .map(([label, value]) => `<div class="metric"><div class="label">${escape(label)}</div><div class="value">${escape(value)}</div></div>`)
      .join("");
  }
'''
new_metrics = '''  function renderMetrics(summary) {
    const sourceStatus = summary.official_source_status || {};
    const sourceAvailable = sourceStatus.source && sourceStatus.source !== "UNAVAILABLE";
    const metrics = [
      ["字段分类覆盖率", `${((summary.classification_coverage || 0) * 100).toFixed(2)}%`],
      ["东方财富事实", summary.eastmoney_fact_count || 0],
      ["官方来源", sourceStatus.source || "—"],
      ["官方事实", summary.official_fact_count || 0],
      ["可比记录", sourceAvailable ? (summary.comparable_count || 0) : "—"],
      ["已匹配", sourceAvailable ? (summary.matched_count || 0) : "—"],
      ["真正冲突", sourceAvailable ? (summary.true_conflict_count || 0) : "—"],
      ["验收状态", summary.acceptance_status || "—"],
    ];
    byId("validationMetrics").innerHTML = metrics
      .map(([label, value]) => `<div class="metric"><div class="label">${escape(label)}</div><div class="value">${escape(value)}</div></div>`)
      .join("");
    const notice = byId("validationNotice");
    if (!notice) return;
    const message = sourceStatus.message || "";
    if (!sourceAvailable && message) {
      notice.hidden = false;
      notice.innerHTML = `<strong>当前没有官方双源数据</strong><p>${escape(message)}</p><p>MISSING_OFFICIAL仅代表待验证项目，不是已发现差异；请接入对应交易所官方来源后重新运行。</p>`;
    } else {
      notice.hidden = true;
      notice.innerHTML = "";
    }
  }
'''
if new_metrics not in js:
    if old_metrics not in js:
        raise RuntimeError("renderMetrics anchor was not found")
    js = js.replace(old_metrics, new_metrics, 1)
old_click = '''  byId("startValidation")?.addEventListener("click", async () => {
    try {
      await startFullCrossValidation(byId("validationCode").value.trim());
    } catch (error) { alert(error.message); }
  });
'''
new_click = '''  byId("startValidation")?.addEventListener("click", async () => {
    try {
      const rawPeriods = byId("validationMaxPeriods")?.value.trim() || "";
      const maxPeriods = rawPeriods ? Number(rawPeriods) : null;
      if (maxPeriods !== null && (!Number.isInteger(maxPeriods) || maxPeriods < 2 || maxPeriods > 80)) {
        throw new Error("官方报告期数必须为2到80的整数；留空表示全部可发现报告期");
      }
      await startFullCrossValidation(byId("validationCode").value.trim(), { max_periods: maxPeriods });
    } catch (error) { alert(error.message); }
  });
'''
if new_click not in js:
    if old_click not in js:
        raise RuntimeError("start validation click anchor was not found")
    js = js.replace(old_click, new_click, 1)
js_path.write_text(js, encoding="utf-8")

replace_once(
    "docs/full-dual-source-validation.md",
    '''## 当前免费官方来源边界

- 上交所股票：已接入上交所正式披露文件；
- 深交所、创业板及北交所：字段仍100%分类，但官方适配器需要后续接入巨潮/深交所和北交所公开披露来源；
- 不接入Wind、Choice商业终端、iFinD、CSMAR、RESSET、聚源或其他收费数据源。
''',
    '''## 当前免费官方来源边界

- 上交所、科创板：使用上交所正式披露文件；
- 深交所主板、创业板：使用巨潮资讯网免费正式披露文件；
- 北交所：字段完成分类，但官方适配器仍待接入北交所公开披露来源；
- 不接入Wind、Choice商业终端、iFinD、CSMAR、RESSET、聚源或其他收费数据源。

如果官方适配器尚不可用，任务返回 `PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE`，可比和匹配指标显示为“—”，而不是错误显示为零匹配的通过状态。
''',
)
replace_once(
    "README.md",
    '''网页默认采用一次输入模式：输入六位股票代码后，系统完成东方财富固定接口拉取、免费官方报告发现、官方事实解析、字段验证分类和双源对账。
''',
    '''网页默认采用一次输入模式：输入六位股票代码后，系统完成东方财富固定接口拉取、免费官方报告发现、官方事实解析、字段验证分类和双源对账。上交所股票使用上交所正式披露文件，深交所主板和创业板使用巨潮资讯网免费正式披露文件；北交所官方适配器仍待接入。
''',
)

Path("tests/test_cninfo_source.py").write_text(
    '''from __future__ import annotations

import hashlib

from ashare_f10.validation.sources.cninfo import CNInfoOfficialSource


def test_cninfo_report_discovery_prefers_corrected_and_excludes_summary(monkeypatch) -> None:
    source = CNInfoOfficialSource()
    monkeypatch.setattr(source, "resolve_org_id", lambda _code: "9900010448")
    payload = {
        "announcements": [
            {
                "announcementTitle": "顺丰控股：2025年年度报告",
                "announcementTime": 1774886400000,
                "adjunctUrl": "finalpage/2026-03-31/annual-original.PDF",
                "adjunctType": "PDF",
            },
            {
                "announcementTitle": "顺丰控股：2025年年度报告（修订版）",
                "announcementTime": 1774972800000,
                "adjunctUrl": "finalpage/2026-04-01/annual-corrected.PDF",
                "adjunctType": "PDF",
            },
            {
                "announcementTitle": "顺丰控股：2025年年度报告摘要",
                "announcementTime": 1774886400000,
                "adjunctUrl": "finalpage/2026-03-31/annual-summary.PDF",
                "adjunctType": "PDF",
            },
            {
                "announcementTitle": "顺丰控股：2026年一季度报告",
                "announcementTime": 1777392000000,
                "adjunctUrl": "finalpage/2026-04-29/q1.PDF",
                "adjunctType": "PDF",
            },
        ],
        "hasMore": False,
        "totalpages": 1,
    }
    monkeypatch.setattr(source, "_post_json", lambda _url, _data, _referer: payload)
    selected = source.select_reports(
        "002352",
        ["2025-12-31", "2026-03-31"],
        begin_date="2025-01-01",
        end_date="2026-07-21",
    )
    assert len(selected) == 2
    annual = next(item for item in selected if item.report_kind == "annual")
    quarter = next(item for item in selected if item.report_kind == "q1")
    assert annual.version_label == "corrected"
    assert annual.url.endswith("annual-corrected.PDF")
    assert quarter.report_date == "2026-03-31"
    assert all("摘要" not in item.title for item in selected)


def test_cninfo_stock_lookup_uses_exact_code(monkeypatch) -> None:
    source = CNInfoOfficialSource()
    monkeypatch.setattr(source, "_warmup", lambda _code: None)
    monkeypatch.setattr(
        source,
        "_post_json",
        lambda _url, _data, _referer: [
            {"code": "00235", "orgId": "wrong", "category": "A股"},
            {"code": "002352", "orgId": "9900010448", "category": "A股"},
        ],
    )
    assert source.resolve_org_id("002352") == "9900010448"


def test_cninfo_download_validates_pdf_and_hash(tmp_path) -> None:
    content = b"%PDF-1.7\\nCNINFO test document"

    class Response:
        headers = {"content-type": "application/pdf"}
        status_code = 200

        def __init__(self) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class Session:
        headers: dict[str, str] = {}

        def get(self, *_args, **_kwargs):
            return Response()

    source = CNInfoOfficialSource(session=Session())
    from ashare_f10.validation.models import OfficialDocument

    document = OfficialDocument(
        "CNINFO",
        "002352",
        "顺丰控股：2025年年度报告",
        "2026-03-31",
        "2025-12-31",
        "annual",
        "original",
        "https://static.cninfo.com.cn/finalpage/2026-03-31/test.PDF",
    )
    downloaded = source.download(document, tmp_path)
    assert downloaded.local_path
    assert downloaded.sha256 == hashlib.sha256(content).hexdigest()
    assert (tmp_path / "002352_2025-12-31_annual.pdf").read_bytes() == content
''',
    encoding="utf-8",
)

Path("tests/test_cross_validation_source_unavailable.py").write_text(
    '''from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.comparator import CrossSourceComparator


def test_official_source_unavailable_is_not_counted_as_comparable() -> None:
    frame = pd.DataFrame(
        [
            {"status": "OFFICIAL_SOURCE_UNAVAILABLE"},
            {"status": "NOT_IN_OFFICIAL_SCOPE"},
            {"status": "SOURCE_SPECIFIC"},
        ]
    )
    summary = CrossSourceComparator.summary(frame)
    assert summary["comparison_count"] == 3
    assert summary["comparable_count"] == 0
    assert summary["matched_count"] == 0
    assert summary["true_conflict_count"] == 0
''',
    encoding="utf-8",
)
