from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
from ashare_f10.validation.reconcile.engine import build_logic_checks, build_ttm_checks, reconcile_official_facts
from ashare_f10.validation.reporting import ValidationReportWriter
from ashare_f10.validation.sources.sse import SSEOfficialSource


class OfficialValidationRunner:
    def __init__(self, stock_code: str, run_dir: Path | str, output_dir: Path | str | None = None, annual_year: int = 2025, quarter_year: int = 2026) -> None:
        self.stock_code = stock_code
        self.run_dir = Path(run_dir)
        self.output_dir = Path(output_dir) if output_dir else self.run_dir / "validation"
        self.annual_year = annual_year
        self.quarter_year = quarter_year

    @property
    def duckdb_path(self) -> Path:
        return self.run_dir / "normalized" / "f10.duckdb"

    def run(self) -> dict[str, Any]:
        if not self.duckdb_path.exists():
            raise FileNotFoundError(f"缺少标准事实数据库：{self.duckdb_path}")
        report_dates = [f"{self.annual_year}-12-31", f"{self.quarter_year}-03-31"]
        source = SSEOfficialSource()
        documents = source.select_reports(self.stock_code, report_dates, begin_date=f"{self.quarter_year}-01-01")
        document_dir = self.output_dir / "source_documents"
        downloaded = [source.download(document, document_dir) for document in documents]
        parser = PdfStatementParser()
        official_facts = []
        extraction_by_document: dict[str, int] = {}
        for document in downloaded:
            facts = parser.extract(document.local_path, document)
            extraction_by_document[document.title] = len(facts)
            official_facts.extend(facts)
        reconciliation = reconcile_official_facts(self.duckdb_path, official_facts)
        logic_checks = build_logic_checks(official_facts)
        ttm_checks = build_ttm_checks(self.duckdb_path, self.stock_code, f"{self.quarter_year}-03-31")
        artifacts = ValidationReportWriter(self.output_dir).write(self.stock_code, downloaded, official_facts, reconciliation, logic_checks, ttm_checks)
        summary = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
        summary["extraction_by_document"] = extraction_by_document
        summary["documents"] = [asdict(document) for document in downloaded]
        artifacts.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {**summary, "artifacts": artifacts.to_dict()}


def run_official_validation(stock_code: str, run_dir: Path | str, output_dir: Path | str | None = None, annual_year: int = 2025, quarter_year: int = 2026) -> dict[str, Any]:
    return OfficialValidationRunner(stock_code, run_dir, output_dir, annual_year, quarter_year).run()
