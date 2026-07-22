from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_f10.cross_validation.comparison_policy import infer_comparison_policy
from ashare_f10.cross_validation.models import RegistryEntry, ValidationMode


class FieldValidationRegistry:
    def __init__(self, config: Mapping[str, Any]) -> None:
        self.config = dict(config)
        self.schema_version = str(self.config.get("schema_version", "1.0.0"))
        self.statement_families: dict[str, dict[str, Any]] = dict(self.config.get("statement_families", {}))
        self.official_event_patterns = tuple(self.config.get("official_event_family_patterns", []))
        self.official_metadata_keys = set(self.config.get("official_metadata_keys", []))
        self.source_specific_patterns = tuple(self.config.get("source_specific_family_patterns", []))
        self.not_periodic_patterns = tuple(self.config.get("not_periodic_family_patterns", []))
        self.technical_tokens = tuple(self.config.get("technical_category_tokens", []))
        self.formulas: dict[str, str] = dict(self.config.get("formula_overrides", {}))
        self.comparison_overrides: dict[str, dict[str, Any]] = dict(
            self.config.get("comparison_overrides", {})
        )

    @classmethod
    def load(cls, path: Path | str | None = None) -> FieldValidationRegistry:
        if path is None:
            resource = files("ashare_f10.resources").joinpath("field_validation_registry_v1.json")
            payload = json.loads(resource.read_text(encoding="utf-8"))
        else:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(payload)

    @staticmethod
    def _contains_any(value: str, patterns: Iterable[str]) -> bool:
        upper = value.upper()
        return any(pattern.upper() in upper for pattern in patterns)

    @staticmethod
    def _statement_from_family(family: str) -> str:
        if "GBALANCE" in family:
            return "balance_sheet"
        if "GINCOME" in family:
            return "income_statement"
        if "GCASHFLOW" in family:
            return "cash_flow"
        return ""

    def _entry(
        self,
        theme: str,
        family: str,
        dataset: str,
        key: str,
        name: str,
        mode: ValidationMode,
        *,
        statement_type: str = "",
        scope: str = "",
        data_semantics: str = "",
        unit: str = "",
        formula: str = "",
        reason: str = "",
        registry_rule: str = "",
        confidence: str = "high",
    ) -> RegistryEntry:
        policy = infer_comparison_policy(key, name, unit, data_semantics)
        override = self.comparison_overrides.get(key, {})
        return RegistryEntry(
            theme,
            family,
            dataset,
            key,
            name,
            mode,
            statement_type=statement_type,
            scope=scope,
            data_semantics=data_semantics,
            unit=unit,
            formula=formula,
            reason=reason,
            registry_rule=registry_rule,
            confidence=confidence,
            comparison_method=str(override.get("comparison_method") or policy.method),
            canonical_unit=str(override.get("canonical_unit") or policy.canonical_unit),
            absolute_tolerance=(
                float(override["absolute_tolerance"])
                if override.get("absolute_tolerance") is not None
                else policy.absolute_tolerance
            ),
            relative_tolerance=(
                float(override["relative_tolerance"])
                if override.get("relative_tolerance") is not None
                else policy.relative_tolerance
            ),
            display_decimals=(
                int(override["display_decimals"])
                if override.get("display_decimals") is not None
                else policy.display_decimals
            ),
        )

    def classify(self, fact: Mapping[str, Any]) -> RegistryEntry:
        theme = str(fact.get("theme") or "")
        family = str(fact.get("family") or "")
        dataset = str(fact.get("dataset") or "")
        key = str(fact.get("field_key") or "")
        name = str(fact.get("field_name_cn") or key)
        unit = str(fact.get("unit") or "")
        semantics = str(fact.get("data_semantics") or "")
        category = str(fact.get("field_category") or "")

        family_rule = self.statement_families.get(family)
        if family_rule:
            if key in self.official_metadata_keys:
                family_mode: ValidationMode = family_rule["mode"]
                metadata_mode: ValidationMode = (
                    "OFFICIAL_DERIVED" if family_mode == "OFFICIAL_DERIVED" else "OFFICIAL_METADATA"
                )
                return self._entry(
                    theme,
                    family,
                    dataset,
                    key,
                    name,
                    metadata_mode,
                    statement_type="metadata",
                    scope="entity",
                    data_semantics=semantics,
                    unit=unit,
                    reason=(
                        "独立季度或计算型数据集的报告元数据由对应官方报告派生"
                        if metadata_mode == "OFFICIAL_DERIVED"
                        else "财务报告元数据可由官方披露文件验证"
                    ),
                    registry_rule="statement_family_metadata",
                )
            mode: ValidationMode = family_rule["mode"]
            return self._entry(
                theme,
                family,
                dataset,
                key,
                name,
                mode,
                statement_type=str(family_rule.get("statement_type") or self._statement_from_family(family)),
                scope=str(family_rule.get("scope") or "consolidated"),
                data_semantics=semantics,
                unit=unit,
                formula=self.formulas.get(key, ""),
                reason=str(family_rule.get("reason") or "定期报告财务事实或可由其推导"),
                registry_rule=f"statement_family:{family}",
            )

        if self._contains_any(category, self.technical_tokens) or key.startswith("_"):
            return self._entry(
                theme,
                family,
                dataset,
                key,
                name,
                "EASTMONEY_SOURCE_SPECIFIC",
                data_semantics=semantics,
                unit=unit,
                reason="接口或技术元数据，不属于公司定期报告项目",
                registry_rule="technical_metadata",
            )

        if self._contains_any(family, self.not_periodic_patterns):
            return self._entry(
                theme,
                family,
                dataset,
                key,
                name,
                "NOT_IN_PERIODIC_REPORT_SCOPE",
                data_semantics=semantics,
                unit=unit,
                reason="该数据属于行情、交易、新闻或临时事件，通常不在定期报告中披露",
                registry_rule="not_periodic_family",
            )

        if self._contains_any(family, self.source_specific_patterns):
            return self._entry(
                theme,
                family,
                dataset,
                key,
                name,
                "EASTMONEY_SOURCE_SPECIFIC",
                data_semantics=semantics,
                unit=unit,
                reason="东方财富平台自定义口径、标签、排名或预测",
                registry_rule="source_specific_family",
            )

        if key in self.official_metadata_keys:
            return self._entry(
                theme,
                family,
                dataset,
                key,
                name,
                "OFFICIAL_METADATA",
                statement_type="metadata",
                scope="entity",
                data_semantics=semantics,
                unit=unit,
                reason="公司或报告元数据可由官方披露文件验证",
                registry_rule="official_metadata_key",
            )

        if self._contains_any(family, self.official_event_patterns):
            mode: ValidationMode = (
                "OFFICIAL_METADATA"
                if self._contains_any(family, ("BASICINFO", "ORGINFO"))
                else "OFFICIAL_DOCUMENT_EVENT"
            )
            return self._entry(
                theme,
                family,
                dataset,
                key,
                name,
                mode,
                statement_type="document_event" if mode == "OFFICIAL_DOCUMENT_EVENT" else "metadata",
                scope="entity",
                data_semantics=semantics,
                unit=unit,
                reason="可从定期报告、临时公告或官方公司资料中验证",
                registry_rule="official_event_family",
            )

        return self._entry(
            theme,
            family,
            dataset,
            key,
            name,
            "FUTURE_FREE_SOURCE_REQUIRED",
            data_semantics=semantics,
            unit=unit,
            reason="当前定期报告解析范围未覆盖；保留至后续免费官方来源路由",
            registry_rule="safe_default_future_source",
            confidence="medium",
        )

    def build_frame(self, eastmoney_facts: pd.DataFrame) -> pd.DataFrame:
        context_columns = ["theme", "family", "dataset", "field_key"]
        if eastmoney_facts.empty:
            return pd.DataFrame(columns=list(RegistryEntry.__dataclass_fields__))
        unique = eastmoney_facts.drop_duplicates(context_columns, keep="first")
        records = [self.classify(row).to_dict() for row in unique.to_dict("records")]
        return pd.DataFrame(records)

    def coverage(self, registry_frame: pd.DataFrame) -> dict[str, Any]:
        total = len(registry_frame)
        classified = int(registry_frame["validation_mode"].notna().sum()) if total else 0
        return {
            "unique_field_contexts": total,
            "classified_field_contexts": classified,
            "classification_coverage": 1.0 if total == 0 else classified / total,
            "mode_counts": dict(Counter(registry_frame.get("validation_mode", []))),
            "comparison_method_counts": dict(Counter(registry_frame.get("comparison_method", []))),
            "registry_version": self.schema_version,
        }
