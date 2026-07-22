from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ashare_f10.cross_validation.adapters import load_eastmoney_facts, load_official_facts
from ashare_f10.evidence import EvidenceGraphBuilder
from ashare_f10.research_mapping import ResearchMapper, ResearchSectionExtractor
from ashare_f10.research_pack.exporter import (
    RESEARCH_PACK_SCHEMA_VERSION,
    ResearchPackExporter,
    sha256_file,
    validate_research_pack,
)
from ashare_f10.research_pack.models import ResearchPackArtifacts, ResearchPackResult
from ashare_f10.validation.point_in_time import normalize_date

STAGES = (
    "LOAD_INPUTS",
    "MAP_CANONICAL",
    "EXTRACT_SECTIONS",
    "BUILD_EVIDENCE",
    "EXPORT",
    "VALIDATE",
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _resolve_path(run_dir: Path, value: Any, *fallbacks: str) -> Path | None:
    candidates: list[Path] = []
    if value:
        path = Path(str(value))
        candidates.extend(
            [path] if path.is_absolute() else [Path.cwd() / path, run_dir / path, run_dir / path.name]
        )
    candidates.extend(run_dir / fallback for fallback in fallbacks)
    for candidate in candidates:
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def _read_duckdb_table(path: Path | None, table: str) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    connection = duckdb.connect(str(path), read_only=True)
    try:
        available = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
        if table not in available:
            return pd.DataFrame()
        return connection.execute(f'SELECT * FROM "{table}"').fetch_df()
    finally:
        connection.close()


def _normalize_raw_pack_documents(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    for column in ("attachments", "links", "section_index", "table_index"):
        if column not in result:
            continue
        result[column] = result[column].map(
            lambda value: (
                json.loads(value)
                if isinstance(value, str) and value.strip().startswith(("[", "{"))
                else value
            )
        )
    return result


class ResearchPackRunner:
    def __init__(
        self,
        stock_code: str,
        run_dir: Path | str,
        output_dir: Path | str | None = None,
        *,
        as_of_date: str | None = None,
        force: bool = False,
    ) -> None:
        self.stock_code = stock_code
        self.run_dir = Path(run_dir)
        self.output_dir = Path(output_dir) if output_dir else self.run_dir / "research_pack"
        self.as_of_date = normalize_date(as_of_date, default_today=True)
        self.force = force
        self.cache_dir = self.output_dir / "cache"
        self.sections_dir = self.cache_dir / "sections"
        self.checkpoint_path = self.output_dir / "checkpoint.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sections_dir.mkdir(parents=True, exist_ok=True)

    @property
    def artifacts_payload(self) -> dict[str, Any]:
        return _read_json(self.run_dir / "artifacts.json")

    def _input_paths(self) -> dict[str, Path | None]:
        artifacts = self.artifacts_payload
        eastmoney_db = _resolve_path(
            self.run_dir,
            artifacts.get("duckdb"),
            "normalized/f10.duckdb",
        )
        official_direct = _resolve_path(
            self.run_dir,
            None,
            "cross_validation/official_direct_facts.parquet",
        )
        official_parquet = official_direct or _resolve_path(
            self.run_dir,
            artifacts.get("official_parquet"),
            f"cross_validation/{self.stock_code}_official_facts.parquet",
            "validation/official_facts.parquet",
        )
        comparison_duckdb = _resolve_path(
            self.run_dir,
            artifacts.get("comparison_duckdb"),
            f"cross_validation/{self.stock_code}_cross_validation.duckdb",
        )
        raw_pack_parquet = _resolve_path(
            self.run_dir,
            artifacts.get("raw_pack_parquet"),
        )
        if raw_pack_parquet is None and artifacts.get("raw_pack"):
            raw_pack_root = Path(str(artifacts["raw_pack"]))
            if not raw_pack_root.is_absolute():
                raw_pack_root = self.run_dir / raw_pack_root
            candidate = raw_pack_root / "source_index" / "source_documents.parquet"
            if candidate.exists():
                raw_pack_parquet = candidate
        return {
            "eastmoney_db": eastmoney_db,
            "official_parquet": official_parquet,
            "comparison_duckdb": comparison_duckdb,
            "raw_pack_parquet": raw_pack_parquet,
        }

    def _fingerprint(self, paths: dict[str, Path | None]) -> dict[str, Any]:
        file_hashes = {
            key: sha256_file(path)
            for key, path in paths.items()
            if path is not None and path.exists() and path.is_file()
        }
        return {
            "schema_version": RESEARCH_PACK_SCHEMA_VERSION,
            "stock_code": self.stock_code,
            "as_of_date": self.as_of_date,
            "file_hashes": file_hashes,
        }

    def _artifacts_from_checkpoint(self, checkpoint: dict[str, Any]) -> ResearchPackArtifacts | None:
        payload = checkpoint.get("artifacts") or {}
        required = {
            "output_dir",
            "manifest_json",
            "summary_json",
            "package_json",
            "package_excel",
            "package_duckdb",
            "quality_json",
            "checkpoint_json",
        }
        if not required.issubset(payload):
            return None
        return ResearchPackArtifacts(**{key: Path(payload[key]) for key in required})

    def _completed_cache_hit(
        self,
        checkpoint: dict[str, Any],
        fingerprint: dict[str, Any],
    ) -> ResearchPackResult | None:
        if self.force or checkpoint.get("status") != "COMPLETED":
            return None
        if checkpoint.get("input_fingerprint") != fingerprint:
            return None
        artifacts = self._artifacts_from_checkpoint(checkpoint)
        if artifacts is None:
            return None
        quality = validate_research_pack(artifacts)
        if quality["status"] != "PASS":
            return None
        summary = _read_json(artifacts.summary_json)
        summary["cache_hit"] = True
        return ResearchPackResult("COMPLETED", True, summary, artifacts)

    def _save_checkpoint(
        self,
        checkpoint: dict[str, Any],
        *,
        stage: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        completed = list(checkpoint.get("completed_stages") or [])
        if stage not in completed:
            completed.append(stage)
        checkpoint.update(
            {
                "status": "RUNNING",
                "last_successful_step": stage,
                "completed_stages": completed,
                "next_action": STAGES[min(STAGES.index(stage) + 1, len(STAGES) - 1)],
                "updated_at_utc": utc_now(),
            }
        )
        if details:
            checkpoint.setdefault("stage_details", {})[stage] = details
        _write_json(self.checkpoint_path, checkpoint)

    def _load_inputs(
        self,
        paths: dict[str, Path | None],
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        eastmoney_db = paths["eastmoney_db"]
        if eastmoney_db is None:
            raise FileNotFoundError(f"缺少F10事实数据库：{self.run_dir / 'normalized/f10.duckdb'}")
        eastmoney = load_eastmoney_facts(eastmoney_db)
        official = (
            load_official_facts(paths["official_parquet"], include_suspect=True)
            if paths["official_parquet"] is not None
            else pd.DataFrame()
        )
        documents = _read_duckdb_table(paths["comparison_duckdb"], "documents")
        raw_documents = (
            _normalize_raw_pack_documents(pd.read_parquet(paths["raw_pack_parquet"]))
            if paths["raw_pack_parquet"] is not None
            else pd.DataFrame()
        )
        if documents.empty:
            documents = raw_documents
        elif not raw_documents.empty:
            documents = pd.concat([documents, raw_documents], ignore_index=True, sort=False)
            if "document_id" in documents:
                documents = documents.drop_duplicates("document_id", keep="first")
        return eastmoney, official, documents

    def _load_mapping_cache(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        source_facts = pd.read_parquet(self.cache_dir / "source_facts.parquet")
        observations = pd.read_parquet(self.cache_dir / "canonical_observations.parquet")
        lineage = pd.read_parquet(self.cache_dir / "fact_lineage.parquet")
        coverage = _read_json(self.cache_dir / "mapping_coverage.json")
        return source_facts, observations, lineage, coverage

    def _save_mapping_cache(
        self,
        source_facts: pd.DataFrame,
        observations: pd.DataFrame,
        lineage: pd.DataFrame,
        coverage: dict[str, Any],
    ) -> None:
        source_facts.to_parquet(self.cache_dir / "source_facts.parquet", index=False)
        observations.to_parquet(self.cache_dir / "canonical_observations.parquet", index=False)
        lineage.to_parquet(self.cache_dir / "fact_lineage.parquet", index=False)
        _write_json(self.cache_dir / "mapping_coverage.json", coverage)

    def _load_section_cache(self) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
        summary = _read_json(self.sections_dir / "summary.json")
        frames = {
            path.stem: pd.read_parquet(path)
            for path in sorted(self.sections_dir.glob("*.parquet"))
        }
        return frames, summary

    def _save_section_cache(
        self,
        frames: dict[str, pd.DataFrame],
        summary: dict[str, Any],
    ) -> None:
        for name, frame in frames.items():
            frame.to_parquet(self.sections_dir / f"{name}.parquet", index=False)
        _write_json(self.sections_dir / "summary.json", summary)

    def _load_evidence_cache(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        nodes = pd.read_parquet(self.cache_dir / "evidence_nodes.parquet")
        edges = pd.read_parquet(self.cache_dir / "evidence_edges.parquet")
        quality = _read_json(self.cache_dir / "evidence_quality.json")
        return nodes, edges, quality

    def _save_evidence_cache(
        self,
        nodes: pd.DataFrame,
        edges: pd.DataFrame,
        quality: dict[str, Any],
    ) -> None:
        nodes.to_parquet(self.cache_dir / "evidence_nodes.parquet", index=False)
        edges.to_parquet(self.cache_dir / "evidence_edges.parquet", index=False)
        _write_json(self.cache_dir / "evidence_quality.json", quality)

    def _register_artifacts(self, result: ResearchPackResult) -> None:
        path = self.run_dir / "artifacts.json"
        payload = _read_json(path)
        artifacts = result.artifacts.to_dict()
        payload.update(
            {
                "research_pack": artifacts["output_dir"],
                "research_pack_manifest": artifacts["manifest_json"],
                "research_pack_summary": artifacts["summary_json"],
                "research_pack_json": artifacts["package_json"],
                "research_pack_excel": artifacts["package_excel"],
                "research_pack_duckdb": artifacts["package_duckdb"],
                "research_pack_quality": artifacts["quality_json"],
            }
        )
        _write_json(path, payload)

    def run(self) -> dict[str, Any]:
        paths = self._input_paths()
        fingerprint = self._fingerprint(paths)
        checkpoint = _read_json(self.checkpoint_path)
        cached = self._completed_cache_hit(checkpoint, fingerprint)
        if cached is not None:
            self._register_artifacts(cached)
            return cached.to_dict()

        if not checkpoint or checkpoint.get("input_fingerprint") != fingerprint or self.force:
            checkpoint = {
                "task_id": f"research-pack-{self.stock_code}",
                "stock_code": self.stock_code,
                "schema_version": RESEARCH_PACK_SCHEMA_VERSION,
                "as_of_date": self.as_of_date,
                "status": "RUNNING",
                "input_fingerprint": fingerprint,
                "completed_stages": [],
                "last_successful_step": "INITIALIZED",
                "next_action": "LOAD_INPUTS",
                "retry_queue": [],
                "created_at_utc": utc_now(),
                "updated_at_utc": utc_now(),
            }
            _write_json(self.checkpoint_path, checkpoint)

        completed = set(checkpoint.get("completed_stages") or [])
        eastmoney, official, documents = self._load_inputs(paths)
        self._save_checkpoint(
            checkpoint,
            stage="LOAD_INPUTS",
            details={
                "eastmoney_fact_count": len(eastmoney),
                "official_fact_count": len(official),
                "document_count": len(documents),
            },
        )

        mapping_cache_ready = all(
            (self.cache_dir / name).exists()
            for name in (
                "source_facts.parquet",
                "canonical_observations.parquet",
                "fact_lineage.parquet",
                "mapping_coverage.json",
            )
        )
        if "MAP_CANONICAL" in completed and mapping_cache_ready:
            source_facts, observations, lineage, mapping_coverage = self._load_mapping_cache()
        else:
            mapping = ResearchMapper(as_of_date=self.as_of_date).map(eastmoney, official)
            source_facts = mapping.source_facts
            observations = mapping.canonical_observations
            lineage = mapping.lineage
            mapping_coverage = mapping.coverage
            self._save_mapping_cache(source_facts, observations, lineage, mapping_coverage)
        self._save_checkpoint(
            checkpoint,
            stage="MAP_CANONICAL",
            details={
                "source_fact_count": len(source_facts),
                "canonical_observation_count": len(observations),
                "lineage_count": len(lineage),
                "source_conflict_count": mapping_coverage.get("source_conflict_count", 0),
            },
        )

        section_cache_ready = (self.sections_dir / "summary.json").exists() and any(
            self.sections_dir.glob("*.parquet")
        )
        if "EXTRACT_SECTIONS" in completed and section_cache_ready:
            section_frames, section_summary = self._load_section_cache()
        else:
            section_pack = ResearchSectionExtractor().extract(observations, source_facts)
            section_frames = section_pack.tables()
            section_summary = section_pack.summary
            self._save_section_cache(section_frames, section_summary)
        self._save_checkpoint(
            checkpoint,
            stage="EXTRACT_SECTIONS",
            details=section_summary,
        )

        evidence_cache_ready = all(
            (self.cache_dir / name).exists()
            for name in ("evidence_nodes.parquet", "evidence_edges.parquet", "evidence_quality.json")
        )
        if "BUILD_EVIDENCE" in completed and evidence_cache_ready:
            evidence_nodes, evidence_edges, evidence_quality = self._load_evidence_cache()
        else:
            evidence = EvidenceGraphBuilder().build(
                documents=documents,
                source_facts=source_facts,
                canonical_observations=observations,
                lineage=lineage,
            )
            evidence_nodes = evidence.nodes
            evidence_edges = evidence.edges
            evidence_quality = evidence.quality
            self._save_evidence_cache(evidence_nodes, evidence_edges, evidence_quality)
        self._save_checkpoint(
            checkpoint,
            stage="BUILD_EVIDENCE",
            details=evidence_quality,
        )

        frames: dict[str, pd.DataFrame] = {
            "source_facts": source_facts,
            "canonical_observations": observations,
            "fact_lineage": lineage,
            "evidence_nodes": evidence_nodes,
            "evidence_edges": evidence_edges,
            "documents": documents,
            **section_frames,
        }
        summary = {
            "schema_version": RESEARCH_PACK_SCHEMA_VERSION,
            "security_code": self.stock_code,
            "as_of_date": self.as_of_date,
            "generated_at_utc": utc_now(),
            "input_fingerprint": fingerprint,
            "mapping_coverage": mapping_coverage,
            "section_summary": section_summary,
            "evidence_quality": evidence_quality,
            "table_counts": {name: len(frame) for name, frame in frames.items()},
            "canonical_status_counts": dict(Counter(observations.get("status", []))),
            "source_status_counts": dict(Counter(source_facts.get("source_status", []))),
        }
        manifest = {
            "task_id": checkpoint["task_id"],
            "schema_version": RESEARCH_PACK_SCHEMA_VERSION,
            "security_code": self.stock_code,
            "as_of_date": self.as_of_date,
            "input_paths": {key: str(value) if value is not None else None for key, value in paths.items()},
            "input_fingerprint": fingerprint,
            "completed_stages": list(STAGES[:-2]),
            "table_names": list(frames),
        }
        exporter = ResearchPackExporter(self.output_dir)
        artifacts, quality = exporter.write(
            self.stock_code,
            summary,
            manifest,
            frames,
            self.checkpoint_path,
        )
        self._save_checkpoint(
            checkpoint,
            stage="EXPORT",
            details={"artifacts": artifacts.to_dict()},
        )
        if quality["status"] != "PASS":
            checkpoint.update(
                {
                    "status": "FAILED",
                    "last_successful_step": "EXPORT",
                    "next_action": "VALIDATE_RESEARCH_PACK",
                    "retry_queue": quality["failures"],
                    "updated_at_utc": utc_now(),
                }
            )
            _write_json(self.checkpoint_path, checkpoint)
            raise RuntimeError(f"Research Pack质量验证失败：{quality['failures']}")

        self._save_checkpoint(checkpoint, stage="VALIDATE", details=quality)
        checkpoint.update(
            {
                "status": "COMPLETED",
                "last_successful_step": "VALIDATE",
                "next_action": "",
                "artifacts": artifacts.to_dict(),
                "summary": summary,
                "quality": quality,
                "updated_at_utc": utc_now(),
            }
        )
        _write_json(self.checkpoint_path, checkpoint)
        result = ResearchPackResult("COMPLETED", False, summary, artifacts)
        self._register_artifacts(result)
        return result.to_dict()


def run_research_pack(
    stock_code: str,
    run_dir: Path | str,
    output_dir: Path | str | None = None,
    *,
    as_of_date: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    return ResearchPackRunner(
        stock_code,
        run_dir,
        output_dir,
        as_of_date=as_of_date,
        force=force,
    ).run()
