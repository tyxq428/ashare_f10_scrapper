from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ResearchPackArtifacts:
    output_dir: Path
    manifest_json: Path
    summary_json: Path
    package_json: Path
    package_excel: Path
    package_duckdb: Path
    quality_json: Path
    checkpoint_json: Path

    def to_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


@dataclass(slots=True)
class ResearchPackResult:
    status: str
    cache_hit: bool
    summary: dict[str, Any]
    artifacts: ResearchPackArtifacts

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "cache_hit": self.cache_hit,
            "summary": self.summary,
            "artifacts": self.artifacts.to_dict(),
        }
