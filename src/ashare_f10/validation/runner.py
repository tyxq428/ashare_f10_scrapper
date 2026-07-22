from __future__ import annotations

import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ashare_f10.validation.documents import pdf_parser as pdf_parser_module
from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
from ashare_f10.validation.reconcile.engine import (
    build_logic_checks,
    build_ttm_checks,
    reconcile_official_facts,
)
from ashare_f10.fetch.security import parse_security
from ashare_f10.validation.reporting import ValidationReportWriter
from ashare_f10.validation.sources.cninfo import CNInfoOfficialSource
from ashare_f10.validation.sources.sse import SSEOfficialSource


class OfficialValidationRunner:
    def __init__(
        self,
        stock_code: str,
        run_dir: Path | str,
        output_dir: Path | str | None = None,
        annual_year: int = 2025,
        quarter_year: int = 2026,
    ) -> None:
        self.stock_code = stock_code
        self.run_dir = Path(run_dir)
        self.output_dir = Path(output_dir) if output_dir else self.run_dir / "validation"
        self.annual_year = annual_year
        self.quarter_year = quarter_year

    @property
    def duckdb_path(self) -> Path:
        return self.run_dir / "normalized" / "f10.duckdb"

    @staticmethod
    def _install_explicit_yuan_unit_guard():
        """Distinguish an explicitly disclosed yuan unit from a missing unit marker.

        The PDF parser carries a prior page's unit forward only when the current page
        has no explicit unit.  Its legacy condition compares the numeric scale with
        ``1.0``, so explicit ``单位：元`` and an absent unit are otherwise indistinguishable.
        A next-representable float preserves the monetary value within sub-micro-yuan
        precision while making the explicit unit observable to that condition.
        """

        original = pdf_parser_module._unit_info

        def guarded(text: str) -> tuple[str, float]:
            unit, scale = original(text)
            compact = pdf_parser_module._compact(text)
            if unit == "元" and re.search(r"单位[：:]元", compact):
                return unit, math.nextafter(1.0, 2.0)
            return unit, scale

        pdf_parser_module._unit_info = guarded
        return original

    def run(self) -> dict[str, Any]:
        if not self.duckdb_path.exists():
            raise FileNotFoundError(f"缺少标准事实数据库：{self.duckdb_path}")

        report_dates = [f"{self.annual_year}-12-31", f"{self.quarter_year}-03-31"]
        exchange = parse_security(self.stock_code).exchange
        if exchange == "SH":
            source = SSEOfficialSource()
        elif exchange == "SZ":
            source = CNInfoOfficialSource()
        else:
            raise RuntimeError(f"{exchange}官方披露适配器尚未接入")
        documents = source.select_reports(
            self.stock_code,
            report_dates,
            begin_date=f"{self.quarter_year}-01-01",
        )
        document_dir = self.output_dir / "source_documents"
        downloaded = [source.download(document, document_dir) for document in documents]

        original_unit_info = self._install_explicit_yuan_unit_guard()
        try:
            parser = PdfStatementParser()
            official_facts = []
            extraction_by_document: dict[str, int] = {}
            for document in downloaded:
                facts = parser.extract(document.local_path, document)
                extraction_by_document[document.title] = len(facts)
                official_facts.extend(facts)
        finally:
            pdf_parser_module._unit_info = original_unit_info

        reconciliation = reconcile_official_facts(self.duckdb_path, official_facts)
        logic_checks = build_logic_checks(official_facts)
        ttm_checks = build_ttm_checks(
            self.duckdb_path,
            self.stock_code,
            f"{self.quarter_year}-03-31",
        )
        artifacts = ValidationReportWriter(self.output_dir).write(
            self.stock_code,
            downloaded,
            official_facts,
            reconciliation,
            logic_checks,
            ttm_checks,
        )
        summary = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
        summary["extraction_by_document"] = extraction_by_document
        summary["documents"] = [asdict(document) for document in downloaded]
        artifacts.summary_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {**summary, "artifacts": artifacts.to_dict()}


def run_official_validation(
    stock_code: str,
    run_dir: Path | str,
    output_dir: Path | str | None = None,
    annual_year: int = 2025,
    quarter_year: int = 2026,
) -> dict[str, Any]:
    return OfficialValidationRunner(
        stock_code,
        run_dir,
        output_dir,
        annual_year,
        quarter_year,
    ).run()
