from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_f10.cross_validation.adapters import (
    load_eastmoney_facts,
    load_official_facts,
    official_fact_columns,
)
from ashare_f10.cross_validation.comparator import CrossSourceComparator
from ashare_f10.cross_validation.derived import (
    derive_document_metadata,
    derive_formula_facts,
    derive_independent_quarters,
)
from ashare_f10.cross_validation.exporter import CrossValidationExporter
from ashare_f10.cross_validation.process_policy import ensure_process_policy
from ashare_f10.cross_validation.registry import FieldValidationRegistry
from ashare_f10.cross_validation.targets import build_dynamic_targets
from ashare_f10.fetch.security import parse_security
from ashare_f10.validation.documents.pdf_parser import PdfStatementParser
from ashare_f10.validation.models import OfficialFact
from ashare_f10.validation.reconcile.engine import build_logic_checks, build_ttm_checks
from ashare_f10.validation.sources.cninfo import CNInfoOfficialSource
from ashare_f10.validation.sources.sse import SSEOfficialSource

PARSER_CACHE_VERSION = "1.3.0"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_artifact_path(run_dir: Path, key: str, fallback: str) -> Path:
    artifacts_path = run_dir / "artifacts.json"
    if artifacts_path.exists():
        payload = json.loads(artifacts_path.read_text(encoding="utf-8"))
        value = payload.get(key)
        if value:
            path = Path(value)
            if not path.is_absolute():
                candidates = [Path.cwd() / path, run_dir / path, run_dir / path.name]
                for candidate in candidates:
                    if candidate.exists():
                        return candidate
            elif path.exists():
                return path
    path = run_dir / fallback
    if not path.exists():
        raise FileNotFoundError(f"缺少{key}数据文件：{path}")
    return path


def _official_report_dates(eastmoney: pd.DataFrame, max_periods: int | None = None) -> list[str]:
    frame = eastmoney[
        eastmoney["family"].isin(
            [
                "RPT_F10_FINANCE_GBALANCE",
                "RPT_F10_FINANCE_GINCOME",
                "RPT_F10_FINANCE_GCASHFLOW",
            ]
        )
        & eastmoney["report_date"].notna()
    ]
    dates = sorted({str(value)[:10] for value in frame["report_date"] if value})
    if max_periods:
        dates = dates[-max_periods:]
    return dates


class FullCrossValidationRunner:
    def __init__(
        self,
        stock_code: str,
        run_dir: Path | str,
        output_dir: Path | str | None = None,
        max_periods: int | None = None,
        registry_path: Path | str | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.stock_code = stock_code
        self.run_dir = Path(run_dir)
        self.output_dir = Path(output_dir) if output_dir else self.run_dir / "cross_validation"
        self.max_periods = max_periods
        self.registry_path = registry_path
        self.progress = progress

    def _notify(self, stage: str, **details: Any) -> None:
        if self.progress is not None:
            self.progress({"stage": stage, "updated_at_utc": utc_now(), **details})

    @property
    def eastmoney_db(self) -> Path:
        return _load_artifact_path(self.run_dir, "duckdb", "normalized/f10.duckdb")

    @property
    def eastmoney_excel(self) -> Path | None:
        try:
            return _load_artifact_path(
                self.run_dir,
                "excel",
                f"exports/{self.stock_code}_F10_full.xlsx",
            )
        except FileNotFoundError:
            return None

    def _build_official_source_package(
        self, eastmoney: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        report_dates = _official_report_dates(eastmoney, self.max_periods)
        if not report_dates:
            raise RuntimeError("东方财富事实表中没有可用于官方报告发现的财务报告期")

        identity = parse_security(self.stock_code)
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
        available = source.list_reports(
            self.stock_code,
            begin_date=f"{min(report_dates)[:4]}-01-01",
            end_date=utc_now()[:10],
        )
        selected = []
        for report_date in report_dates:
            candidates = [
                item
                for item in available
                if item.report_date == report_date and item.version_label != "withdrawn"
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda item: (
                    {"corrected": 3, "original": 2}.get(item.version_label, 1),
                    item.publish_date,
                ),
                reverse=True,
            )
            selected.append(candidates[0])

        document_dir = self.output_dir / "source_documents"
        document_dir.mkdir(parents=True, exist_ok=True)

        def cached_or_download(document):
            target = document_dir / (
                f"{document.security_code}_{document.report_date}_{document.report_kind}.pdf"
            )
            if target.exists() and target.stat().st_size > 100 and target.read_bytes()[:4] == b"%PDF":
                cached = copy.copy(document)
                cached.local_path = str(target)
                cached.sha256 = _sha256_file(target)
                return cached
            return source_class(timeout=60).download(copy.copy(document), document_dir)

        downloaded = []
        with ThreadPoolExecutor(max_workers=max(1, min(4, len(selected) or 1))) as executor:
            futures = [executor.submit(cached_or_download, document) for document in selected]
            completed_downloads = 0
            for future in as_completed(futures):
                downloaded.append(future.result())
                completed_downloads += 1
                self._notify(
                    "OFFICIAL_DOWNLOAD",
                    completed=completed_downloads,
                    total=len(selected),
                )
        downloaded.sort(key=lambda item: item.report_date)

        targets = build_dynamic_targets(self.eastmoney_db)
        parsed_cache_dir = self.output_dir / "cache" / "parsed"
        parsed_cache_dir.mkdir(parents=True, exist_ok=True)

        def parse_document(document):
            cache_path = parsed_cache_dir / f"{document.sha256}-{PARSER_CACHE_VERSION}.json"
            if cache_path.exists():
                try:
                    payload = json.loads(cache_path.read_text(encoding="utf-8"))
                    return (
                        document,
                        [OfficialFact(**record) for record in payload],
                        True,
                    )
                except Exception:  # noqa: BLE001
                    cache_path.unlink(missing_ok=True)
            parser = PdfStatementParser(targets)
            facts = parser.extract(document.local_path, document)
            temporary = cache_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps([fact.to_dict() for fact in facts], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(cache_path)
            return document, facts, False

        official_records: list[dict[str, Any]] = []
        extraction_by_document: dict[str, int] = {}
        parser_cache_hits = 0
        with ThreadPoolExecutor(max_workers=max(1, min(3, len(downloaded) or 1))) as executor:
            futures = [executor.submit(parse_document, document) for document in downloaded]
            completed_parses = 0
            for future in as_completed(futures):
                document, facts, cache_hit = future.result()
                parser_cache_hits += int(cache_hit)
                extraction_by_document[document.title] = len(facts)
                official_records.extend(fact.to_dict() for fact in facts)
                completed_parses += 1
                self._notify(
                    "OFFICIAL_PARSE",
                    completed=completed_parses,
                    total=len(downloaded),
                    cache_hits=parser_cache_hits,
                )

        official_raw = pd.DataFrame(official_records)
        if official_raw.empty:
            official = official_fact_columns(pd.DataFrame())
        else:
            temporary = self.output_dir / "official_direct_facts.parquet"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            official_raw.to_parquet(temporary, index=False)
            official = official_fact_columns(load_official_facts(temporary))
            quarters = derive_independent_quarters(official)
            registry = FieldValidationRegistry.load(self.registry_path)
            names = {
                str(row.field_key): str(row.field_name_cn)
                for row in eastmoney[["field_key", "field_name_cn"]].drop_duplicates().itertuples(index=False)
            }
            formulas = derive_formula_facts(official, registry.formulas, names)
            official = pd.concat([official, quarters, formulas], ignore_index=True, sort=False)

        documents_frame = pd.DataFrame([asdict(document) for document in downloaded])
        metadata = official_fact_columns(derive_document_metadata(documents_frame))
        if not metadata.empty:
            official = pd.concat([official, metadata], ignore_index=True, sort=False)
        source_status = {
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
        return official, documents_frame, source_status

    def run(self) -> dict[str, Any]:
        policy_path = ensure_process_policy()
        self._notify("PROCESS_POLICY_CHECK", policy_path=str(policy_path))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = self.output_dir / "checkpoint.json"
        checkpoint = {
            "task_id": f"full-cross-validation-{self.stock_code}",
            "stock_code": self.stock_code,
            "status": "RUNNING",
            "last_successful_step": "PROCESS_POLICY_CHECK",
            "process_policy": str(policy_path),
            "updated_at_utc": utc_now(),
        }
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")

        self._notify("EASTMONEY_NORMALIZE")
        eastmoney = load_eastmoney_facts(self.eastmoney_db)
        registry_engine = FieldValidationRegistry.load(self.registry_path)
        registry_frame = registry_engine.build_frame(eastmoney)
        coverage = registry_engine.coverage(registry_frame)
        checkpoint.update(
            {
                "last_successful_step": "EASTMONEY_AND_REGISTRY_READY",
                "eastmoney_fact_count": len(eastmoney),
                **coverage,
                "updated_at_utc": utc_now(),
            }
        )
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")

        official, documents, source_status = self._build_official_source_package(eastmoney)
        self._notify(
            "RECONCILIATION",
            eastmoney_fact_count=len(eastmoney),
            official_fact_count=len(official),
        )
        comparator = CrossSourceComparator(registry_frame)
        comparison = comparator.compare(eastmoney, official)
        source_unavailable = source_status.get("source") == "UNAVAILABLE"
        if source_unavailable:
            unavailable_mask = comparison["status"] == "MISSING_OFFICIAL"
            comparison.loc[unavailable_mask, "status"] = "OFFICIAL_SOURCE_UNAVAILABLE"
            comparison.loc[unavailable_mask, "verification_grade"] = "N/A"
            explanation = str(source_status.get("message") or "官方披露来源不可用")
            comparison.loc[unavailable_mask, "notes"] = explanation
        compare_summary = comparator.summary(comparison)

        logic_objects = build_logic_checks_from_frame(official)
        q1_dates = sorted(
            {
                str(value)[:10]
                for value in eastmoney.loc[eastmoney["report_date"].notna(), "report_date"]
                if str(value)[:10].endswith("03-31")
            }
        )
        ttm_objects = build_ttm_checks(self.eastmoney_db, self.stock_code, q1_dates[-1]) if q1_dates else []
        logic_frame = pd.DataFrame([item.to_dict() for item in logic_objects])
        ttm_frame = pd.DataFrame([item.to_dict() for item in ttm_objects])

        mode_counts = dict(Counter(registry_frame["validation_mode"]))
        summary = {
            "schema_version": "1.0.0",
            "security_code": self.stock_code,
            "registry_version": registry_engine.schema_version,
            "eastmoney_fact_count": len(eastmoney),
            "official_fact_count": len(official),
            **coverage,
            **compare_summary,
            "mode_counts": mode_counts,
            "paid_sources_used": False,
            "official_source_status": source_status,
            "logic_check_counts": dict(Counter(logic_frame.get("status", []))),
            "ttm_check_counts": dict(Counter(ttm_frame.get("status", []))),
            "completed_at_utc": utc_now(),
        }
        unresolved = int(
            comparison["status"]
            .isin(
                [
                    "MISSING_OFFICIAL",
                    "MISSING_EASTMONEY",
                    "UNRESOLVED",
                    "FUTURE_FREE_SOURCE_REQUIRED",
                ]
            )
            .sum()
        )
        if summary["true_conflict_count"]:
            summary["acceptance_status"] = "FAIL_SOURCE_CONFLICT"
        elif coverage["classification_coverage"] < 1.0:
            summary["acceptance_status"] = "FAIL_CLASSIFICATION_COVERAGE"
        elif source_unavailable:
            summary["acceptance_status"] = "PARTIAL_OFFICIAL_SOURCE_UNAVAILABLE"
        elif unresolved:
            summary["acceptance_status"] = "PASS_WITH_COVERAGE_GAPS"
        else:
            summary["acceptance_status"] = "PASS"
        summary["manual_review_required"] = bool(summary["true_conflict_count"])

        self._notify("EXPORT", comparison_count=len(comparison))
        artifacts = CrossValidationExporter(self.output_dir).write(
            self.stock_code,
            eastmoney,
            official,
            registry_frame,
            comparison,
            summary,
            logic_checks=logic_frame,
            ttm_checks=ttm_frame,
            documents=documents,
            source_document_dir=self.output_dir / "source_documents",
            eastmoney_source_excel=self.eastmoney_excel,
            eastmoney_source_duckdb=self.eastmoney_db,
        )
        summary["artifacts"] = artifacts.to_dict()
        (self.output_dir / "cross_validation_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        checkpoint.update(
            {
                "status": "COMPLETED",
                "last_successful_step": "EXPORT_AND_VALIDATION_COMPLETE",
                "next_action": "",
                "artifacts": artifacts.to_dict(),
                "summary": summary,
                "updated_at_utc": utc_now(),
            }
        )
        checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts_path = self.run_dir / "artifacts.json"
        existing_artifacts = (
            json.loads(artifacts_path.read_text(encoding="utf-8")) if artifacts_path.exists() else {}
        )
        existing_artifacts.update(artifacts.to_dict())
        artifacts_path.write_text(
            json.dumps(existing_artifacts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._notify("COMPLETED", acceptance_status=summary["acceptance_status"])
        return summary


def build_logic_checks_from_frame(official: pd.DataFrame) -> list[Any]:
    from ashare_f10.validation.models import OfficialFact

    facts = []
    required = set(OfficialFact.__dataclass_fields__)
    for row in official.to_dict("records"):
        if row.get("source_status") == "FACT_CALCULATED":
            continue
        payload = {
            "security_code": row.get("security_code"),
            "report_date": row.get("report_date"),
            "statement_type": row.get("statement_type"),
            "scope": row.get("scope"),
            "field_key": row.get("field_key"),
            "field_name_report": row.get("field_name_cn"),
            "value": row.get("value_num"),
            "unit": row.get("unit"),
            "normalized_unit": row.get("normalized_unit"),
            "source_document": row.get("source_document"),
            "source_url": row.get("source_url"),
            "source_page": int(row.get("source_page") or 0),
            "source_row": row.get("source_row"),
            "extraction_method": row.get("extraction_method") or "PDF_TABLE",
            "precision_tolerance": float(row.get("precision_tolerance") or 1.0),
            "confidence": row.get("confidence") or "high",
        }
        if payload["value"] is None:
            continue
        facts.append(OfficialFact(**{key: payload[key] for key in required}))
    return build_logic_checks(facts)


def run_full_cross_validation(
    stock_code: str,
    run_dir: Path | str,
    output_dir: Path | str | None = None,
    max_periods: int | None = None,
    registry_path: Path | str | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    return FullCrossValidationRunner(
        stock_code, run_dir, output_dir, max_periods, registry_path, progress
    ).run()
