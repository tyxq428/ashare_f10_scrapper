from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ashare_f10.cross_validation.lifecycle import lifecycle_period_frame
from ashare_f10.cross_validation.models import CrossValidationArtifacts

EXCEL_CELL_LIMIT = 32_000


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


_EMPTY_TABLE_COLUMNS: dict[str, list[str]] = {
    "logic_checks": [
        "security_code",
        "report_date",
        "check_id",
        "description",
        "left_value",
        "right_value",
        "difference",
        "tolerance",
        "status",
        "source",
        "components",
    ],
    "ttm_checks": [
        "security_code",
        "field_key",
        "field_name_cn",
        "end_period",
        "independent_quarters_value",
        "cumulative_formula_value",
        "difference",
        "tolerance",
        "status",
        "independent_components",
        "cumulative_components",
    ],
    "documents": [
        "source",
        "security_code",
        "title",
        "publish_date",
        "report_date",
        "report_kind",
        "version_label",
        "url",
        "local_path",
        "sha256",
    ],
}


def _table_frame(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.shape[1] == 0:
        return pd.DataFrame(columns=_EMPTY_TABLE_COLUMNS.get(name, ["empty"]))
    return frame


def _json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.columns:
        if result[column].dtype == "object":
            result[column] = result[column].map(
                lambda value: (
                    json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (dict, list, tuple, set))
                    else _json_scalar(value)
                )
            )
            result[column] = result[column].map(
                lambda value: (
                    value[: EXCEL_CELL_LIMIT - 40] + "…[完整内容见JSON/Parquet]"
                    if isinstance(value, str) and len(value) > EXCEL_CELL_LIMIT
                    else value
                )
            )
    return result


def _write_frame_array(handle: Any, frame: pd.DataFrame, chunk_size: int = 10_000) -> None:
    handle.write("[")
    first = True
    for start in range(0, len(frame), chunk_size):
        payload = frame.iloc[start : start + chunk_size].to_json(
            orient="records",
            force_ascii=False,
            date_format="iso",
        )
        body = payload[1:-1]
        if not body:
            continue
        if not first:
            handle.write(",")
        handle.write(body)
        first = False
    handle.write("]")


def _write_json_package(
    path: Path,
    metadata: dict[str, Any],
    frames: list[tuple[str, pd.DataFrame]],
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        handle.write('{"metadata":')
        json.dump(
            metadata,
            handle,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_scalar,
        )
        for name, frame in frames:
            handle.write(",")
            json.dump(name, handle, ensure_ascii=False)
            handle.write(":")
            _write_frame_array(handle, frame)
        handle.write("}")


def _format_xlsx_writer(writer: pd.ExcelWriter, sheet_name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    sheet = writer.sheets[sheet_name]
    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1F4E78",
            "align": "center",
            "valign": "vcenter",
            "text_wrap": True,
            "border": 1,
        }
    )
    sheet.set_row(0, 28, header)
    sheet.freeze_panes(1, 0)
    if len(frame.columns):
        sheet.autofilter(0, 0, max(len(frame), 1), len(frame.columns) - 1)
    for index, column in enumerate(frame.columns):
        label = str(column)
        if any(token in label.lower() for token in ("source_row", "notes", "url", "document")):
            width = 38
        elif any(token in label.lower() for token in ("field_name", "field_key", "dataset", "family")):
            width = 25
        elif any(token in label.lower() for token in ("date", "period", "status", "mode")):
            width = 18
        else:
            width = min(22, max(12, len(label) + 2))
        sheet.set_column(index, index, width)


def _write_excel(path: Path, sheets: list[tuple[str, pd.DataFrame]]) -> None:
    with pd.ExcelWriter(
        path,
        engine="xlsxwriter",
        engine_kwargs={"options": {"strings_to_urls": False}},
    ) as writer:
        for sheet_name, frame in sheets:
            safe = _safe_frame(frame)
            safe.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            _format_xlsx_writer(writer, sheet_name[:31], safe)


def _write_duckdb(
    path: Path,
    eastmoney_parquet: Path,
    official_parquet: Path,
    comparison_parquet: Path,
    registry: pd.DataFrame,
    logic_checks: pd.DataFrame,
    ttm_checks: pd.DataFrame,
    documents: pd.DataFrame,
    report_period_lifecycle: pd.DataFrame,
) -> None:
    path.unlink(missing_ok=True)
    connection = duckdb.connect(str(path))
    try:
        for table_name, parquet_path in (
            ("eastmoney_facts", eastmoney_parquet),
            ("official_facts", official_parquet),
            ("reconciliation", comparison_parquet),
        ):
            connection.execute(
                f"CREATE TABLE {table_name} AS SELECT * FROM read_parquet(?)",
                [str(parquet_path)],
            )
        for name, frame in {
            "field_validation_registry": registry,
            "logic_checks": logic_checks,
            "ttm_checks": ttm_checks,
            "documents": documents,
            "report_period_lifecycle": report_period_lifecycle,
        }.items():
            frame = _table_frame(name, frame)
            connection.register("incoming", frame)
            connection.execute(f"CREATE TABLE {name} AS SELECT * FROM incoming")
            connection.unregister("incoming")
        connection.execute(
            """
            CREATE VIEW coverage_summary AS
            SELECT validation_mode, status, count(*) AS fact_count
            FROM reconciliation GROUP BY validation_mode, status
            """
        )
        connection.execute(
            """
            CREATE VIEW true_conflicts AS
            SELECT * FROM reconciliation
            WHERE status IN ('MISMATCH','VERSION_CONFLICT','SCOPE_CONFLICT','PERIOD_CONFLICT','UNIT_CONFLICT')
            """
        )
        connection.execute(
            """
            CREATE VIEW not_in_official_scope AS
            SELECT * FROM reconciliation
            WHERE status IN (
                'NOT_IN_OFFICIAL_SCOPE',
                'SOURCE_SPECIFIC',
                'FUTURE_FREE_SOURCE_REQUIRED',
                'OFFICIAL_PERIOD_NOT_LOADED'
            )
            """
        )
        connection.execute("CREATE INDEX idx_recon_status ON reconciliation(status)")
        connection.execute("CREATE INDEX idx_recon_key ON reconciliation(field_key)")
        connection.execute("CREATE INDEX idx_recon_date ON reconciliation(report_date)")
    finally:
        connection.close()


class CrossValidationExporter:
    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        security_code: str,
        eastmoney: pd.DataFrame,
        official: pd.DataFrame,
        registry: pd.DataFrame,
        comparison: pd.DataFrame,
        summary: dict[str, Any],
        logic_checks: pd.DataFrame | None = None,
        ttm_checks: pd.DataFrame | None = None,
        documents: pd.DataFrame | None = None,
        source_document_dir: Path | None = None,
        eastmoney_source_excel: Path | None = None,
        eastmoney_source_duckdb: Path | None = None,
    ) -> CrossValidationArtifacts:
        logic_checks = logic_checks if logic_checks is not None else pd.DataFrame()
        ttm_checks = ttm_checks if ttm_checks is not None else pd.DataFrame()
        documents = documents if documents is not None else pd.DataFrame()

        eastmoney_json = self.output_dir / f"{security_code}_eastmoney_full.json"
        eastmoney_excel = self.output_dir / f"{security_code}_eastmoney_full.xlsx"
        eastmoney_parquet = self.output_dir / f"{security_code}_eastmoney_facts.parquet"
        eastmoney_duckdb = self.output_dir / f"{security_code}_eastmoney.duckdb"
        official_json = self.output_dir / f"{security_code}_official_full.json"
        official_excel = self.output_dir / f"{security_code}_official_full.xlsx"
        official_parquet = self.output_dir / f"{security_code}_official_facts.parquet"
        official_duckdb = self.output_dir / f"{security_code}_official.duckdb"
        comparison_json = self.output_dir / f"{security_code}_cross_validation.json"
        comparison_excel = self.output_dir / f"{security_code}_cross_validation.xlsx"
        comparison_parquet = self.output_dir / f"{security_code}_cross_validation.parquet"
        comparison_duckdb = self.output_dir / f"{security_code}_cross_validation.duckdb"
        summary_json = self.output_dir / "cross_validation_summary.json"
        evidence_zip = self.output_dir / f"{security_code}_validation_evidence.zip"

        eastmoney.to_parquet(eastmoney_parquet, index=False)
        official.to_parquet(official_parquet, index=False)
        comparison.to_parquet(comparison_parquet, index=False)

        _write_json_package(
            eastmoney_json,
            {"security_code": security_code, "source": "EASTMONEY"},
            [("facts", eastmoney)],
        )
        _write_json_package(
            official_json,
            {"security_code": security_code, "source": "FREE_OFFICIAL_DISCLOSURE"},
            [
                ("documents", documents),
                ("facts", official),
                ("field_validation_registry", registry),
            ],
        )
        _write_json_package(
            comparison_json,
            summary,
            [
                ("reconciliation", comparison),
                ("logic_checks", logic_checks),
                ("ttm_checks", ttm_checks),
                ("field_validation_registry", registry),
            ],
        )

        if eastmoney_source_excel and eastmoney_source_excel.is_file():
            shutil.copy2(eastmoney_source_excel, eastmoney_excel)
        else:
            # A full 250k-row fact workbook is slower and less usable than the existing
            # themed F10 workbook.  This fallback keeps only the validation-ready subset;
            # Parquet/DuckDB/JSON always contain every Eastmoney fact.
            subset = eastmoney[eastmoney["family"].str.startswith("RPT_F10_FINANCE", na=False)].copy()
            _write_excel(eastmoney_excel, [("ValidationFacts", subset)])

        _write_excel(
            official_excel,
            [
                ("OfficialFacts", official),
                ("Documents", documents),
                ("ValidationRegistry", registry),
            ],
        )

        summary_frame = pd.DataFrame([summary])
        period_lifecycle = lifecycle_period_frame(summary.get("official_source_status") or {})
        comparison_columns = [
            column
            for column in [
                "comparison_key",
                "security_code",
                "report_date",
                "event_date",
                "period_type",
                "statement_type",
                "scope",
                "theme",
                "family",
                "dataset",
                "field_key",
                "field_name_cn",
                "validation_mode",
                "eastmoney_value_num",
                "eastmoney_value_text",
                "eastmoney_unit",
                "official_value_num",
                "official_value_text",
                "official_unit",
                "difference",
                "relative_difference",
                "tolerance",
                "status",
                "verification_grade",
                "source_document",
                "source_url",
                "source_page",
                "source_row",
                "eastmoney_source_url",
                "notes",
            ]
            if column in comparison.columns
        ]
        comparison_excel_frame = comparison[comparison_columns]
        match_statuses = {
            "EXACT_MATCH",
            "WITHIN_ROUNDING",
            "DERIVED_MATCH",
            "TEXT_MATCH_NORMALIZED",
            "SET_MATCH",
        }
        conflict_statuses = {
            "MISMATCH",
            "VERSION_CONFLICT",
            "SCOPE_CONFLICT",
            "PERIOD_CONFLICT",
            "UNIT_CONFLICT",
        }
        comparable_detail = comparison_excel_frame[
            comparison_excel_frame["status"].isin(match_statuses | conflict_statuses | {"MISSING_EASTMONEY"})
        ]
        missing_official_summary = (
            comparison_excel_frame[comparison_excel_frame["status"].isin(["MISSING_OFFICIAL", "UNRESOLVED"])]
            .groupby(
                [
                    "report_date",
                    "period_type",
                    "family",
                    "field_key",
                    "field_name_cn",
                    "validation_mode",
                    "status",
                ],
                dropna=False,
            )
            .size()
            .reset_index(name="fact_count")
        )
        unavailable_summary = (
            comparison_excel_frame[
                comparison_excel_frame["status"].isin(
                    [
                        "OFFICIAL_PERIOD_NOT_LOADED",
                        "PRE_LISTING_OFFICIAL_SOURCE_NOT_LOADED",
                        "OFFICIAL_DOCUMENT_EXTRACTION_FAILED",
                        "POST_LISTING_OFFICIAL_REPORT_NOT_FOUND",
                    ]
                )
            ]
            .groupby(
                [
                    "report_date",
                    "period_type",
                    "family",
                    "validation_mode",
                    "status",
                ],
                dropna=False,
            )
            .size()
            .reset_index(name="fact_count")
        )
        out_of_scope_registry = registry[
            registry["validation_mode"].isin(
                [
                    "NOT_IN_PERIODIC_REPORT_SCOPE",
                    "EASTMONEY_SOURCE_SPECIFIC",
                    "FUTURE_FREE_SOURCE_REQUIRED",
                ]
            )
        ]
        status_summary = (
            comparison_excel_frame.groupby(["validation_mode", "status"], dropna=False)
            .size()
            .reset_index(name="fact_count")
        )
        event_gap_summary = (
            comparison_excel_frame[
                comparison_excel_frame["report_date"].isna()
                & comparison_excel_frame["status"].isin(
                    ["MISSING_OFFICIAL", "MISSING_EASTMONEY", "UNRESOLVED"]
                )
            ]
            .groupby(
                ["theme", "family", "dataset", "validation_mode", "status"],
                dropna=False,
            )
            .size()
            .reset_index(name="fact_count")
        )
        evidence_rows = comparison_excel_frame[
            comparison_excel_frame["status"].isin(match_statuses | conflict_statuses | {"MISSING_EASTMONEY"})
        ]
        evidence_columns = [
            column
            for column in [
                "comparison_key",
                "field_key",
                "field_name_cn",
                "report_date",
                "status",
                "source_document",
                "source_url",
                "source_page",
                "source_row",
                "eastmoney_source_url",
            ]
            if column in evidence_rows
        ]
        excel_sheets: list[tuple[str, pd.DataFrame]] = [
            ("00_验证总览", summary_frame),
            ("01_可比明细", comparable_detail),
            ("02_字段验证目录", registry),
            (
                "03_匹配结果",
                comparison_excel_frame[comparison_excel_frame["status"].isin(match_statuses)],
            ),
            (
                "04_真正冲突",
                comparison_excel_frame[comparison_excel_frame["status"].isin(conflict_statuses)],
            ),
            ("05_官方未提取汇总", missing_official_summary),
            ("06_报告期生命周期", period_lifecycle),
            ("06A_报告缺口汇总", unavailable_summary),
            ("07_不在官方范围目录", out_of_scope_registry),
            ("08_状态汇总", status_summary),
            ("09_事件覆盖缺口汇总", event_gap_summary),
            ("10_会计逻辑检查", logic_checks),
            ("11_TTM双公式", ttm_checks),
            ("12_官方文档", documents),
            ("13_证据索引", evidence_rows[evidence_columns]),
        ]

        _write_excel(comparison_excel, excel_sheets)

        _write_duckdb(
            comparison_duckdb,
            eastmoney_parquet,
            official_parquet,
            comparison_parquet,
            registry,
            logic_checks,
            ttm_checks,
            documents,
            period_lifecycle,
        )
        if eastmoney_source_duckdb and eastmoney_source_duckdb.is_file():
            shutil.copy2(eastmoney_source_duckdb, eastmoney_duckdb)
        else:
            connection = duckdb.connect(str(eastmoney_duckdb))
            try:
                connection.execute(
                    "CREATE OR REPLACE TABLE facts AS SELECT * FROM read_parquet(?)",
                    [str(eastmoney_parquet)],
                )
            finally:
                connection.close()

        connection = duckdb.connect(str(official_duckdb))
        try:
            connection.execute(
                "CREATE OR REPLACE TABLE facts AS SELECT * FROM read_parquet(?)",
                [str(official_parquet)],
            )
            if not documents.empty:
                connection.register("docs", _table_frame("documents", documents))
                connection.execute("CREATE OR REPLACE TABLE documents AS SELECT * FROM docs")
                connection.unregister("docs")
        finally:
            connection.close()

        artifacts = CrossValidationArtifacts(
            self.output_dir,
            eastmoney_json,
            eastmoney_excel,
            eastmoney_parquet,
            eastmoney_duckdb,
            official_json,
            official_excel,
            official_parquet,
            official_duckdb,
            comparison_json,
            comparison_excel,
            comparison_parquet,
            comparison_duckdb,
            summary_json,
            evidence_zip,
        )
        summary["artifacts"] = artifacts.to_dict()
        summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        checksums_path = self.output_dir / "cross_validation_checksums.json"
        package_files = [
            eastmoney_json,
            eastmoney_excel,
            eastmoney_parquet,
            eastmoney_duckdb,
            official_json,
            official_excel,
            official_parquet,
            official_duckdb,
            comparison_json,
            comparison_excel,
            comparison_parquet,
            comparison_duckdb,
            summary_json,
        ]
        checksums = {path.name: _sha256_file(path) for path in package_files if path.is_file()}
        checksums_path.write_text(json.dumps(checksums, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(evidence_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            # Full source JSON/DuckDB files remain separate downloadable artifacts.
            # The evidence ZIP stays compact enough for rapid local and Actions use.
            for path in (
                summary_json,
                comparison_parquet,
                comparison_excel,
                official_json,
                official_parquet,
                official_excel,
                checksums_path,
            ):
                if path.is_file():
                    archive.write(path, arcname=path.name)
            if source_document_dir and source_document_dir.exists():
                for path in sorted(source_document_dir.rglob("*")):
                    if path.is_file():
                        archive.write(path, arcname=f"source_documents/{path.name}")

        checksums[evidence_zip.name] = _sha256_file(evidence_zip)
        checksums_path.write_text(json.dumps(checksums, ensure_ascii=False, indent=2), encoding="utf-8")
        return artifacts
