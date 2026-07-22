from __future__ import annotations

import hashlib
import json
from collections import Counter, deque
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

import pandas as pd

from ashare_f10.evidence.models import EvidenceEdge, EvidenceNode


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, dict):
        return [value]
    records: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            records.append(item)
        elif hasattr(item, "model_dump"):
            records.append(item.model_dump(mode="json"))
        elif is_dataclass(item):
            records.append(asdict(item))
        elif hasattr(item, "to_dict"):
            records.append(item.to_dict())
        else:
            raise TypeError(f"Unsupported evidence record type: {type(item)!r}")
    return records


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _document_id(row: dict[str, Any]) -> str:
    existing = _text(row.get("document_id"))
    if existing:
        return existing if existing.startswith("doc_") else f"doc_{existing}"
    return _stable_id(
        "doc",
        row.get("security_code"),
        row.get("source_url") or row.get("url"),
        row.get("source_document") or row.get("document_title") or row.get("title"),
        row.get("report_date") or row.get("report_period"),
    )


@dataclass(slots=True)
class EvidenceGraphResult:
    nodes: pd.DataFrame
    edges: pd.DataFrame
    quality: dict[str, Any]

    def trace_observation(self, observation_id: str, max_depth: int = 4) -> EvidenceGraphResult:
        if self.nodes.empty or self.edges.empty:
            return EvidenceGraphResult(self.nodes.copy(), self.edges.copy(), dict(self.quality))
        adjacency: dict[str, list[dict[str, Any]]] = {}
        for edge in self.edges.to_dict("records"):
            adjacency.setdefault(str(edge["from_node_id"]), []).append(edge)
        visited = {observation_id}
        selected_edges: list[dict[str, Any]] = []
        queue: deque[tuple[str, int]] = deque([(observation_id, 0)])
        while queue:
            node_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in adjacency.get(node_id, []):
                selected_edges.append(edge)
                target = str(edge["to_node_id"])
                if target not in visited:
                    visited.add(target)
                    queue.append((target, depth + 1))
        nodes = self.nodes[self.nodes["node_id"].isin(visited)].copy()
        edges = pd.DataFrame(selected_edges, columns=self.edges.columns)
        return EvidenceGraphResult(nodes.reset_index(drop=True), edges.reset_index(drop=True), dict(self.quality))


class EvidenceGraphBuilder:
    def __init__(self) -> None:
        self._nodes: dict[str, EvidenceNode] = {}
        self._edges: dict[str, EvidenceEdge] = {}

    def _add_node(
        self,
        node_id: str,
        node_type: str,
        security_code: str,
        label: str,
        attributes: dict[str, Any],
    ) -> str:
        node = EvidenceNode(node_id, node_type, security_code, label, _json(attributes))
        existing = self._nodes.get(node_id)
        if existing is None:
            self._nodes[node_id] = node
        elif existing.node_type != node_type:
            raise ValueError(f"Evidence node identity collision: {node_id}")
        return node_id

    def _add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        edge_id = _stable_id("edge", from_node_id, to_node_id, edge_type, _json(attributes or {}))
        self._edges.setdefault(
            edge_id,
            EvidenceEdge(edge_id, from_node_id, to_node_id, edge_type, _json(attributes or {})),
        )
        return edge_id

    def _security_node(self, security_code: str) -> str:
        return self._add_node(
            f"security_{security_code}",
            "SECURITY",
            security_code,
            security_code,
            {"security_code": security_code},
        )

    def _add_documents(self, documents: list[dict[str, Any]]) -> None:
        for row in documents:
            security_code = _text(row.get("security_code"))
            if not security_code:
                continue
            security_node = self._security_node(security_code)
            document_id = _document_id(row)
            title = _text(row.get("document_title") or row.get("title") or row.get("source_document"))
            attributes = {
                "source": row.get("source"),
                "source_id": row.get("source_id"),
                "source_tier": row.get("source_tier"),
                "source_organization": row.get("source_organization"),
                "source_domain": row.get("source_domain"),
                "source_url": row.get("source_url") or row.get("url"),
                "canonical_url": row.get("canonical_url"),
                "document_title": title,
                "document_type": row.get("document_type") or row.get("report_kind"),
                "publish_date": row.get("publish_date"),
                "report_date": row.get("report_date") or row.get("report_period"),
                "effective_at": row.get("effective_at"),
                "available_at": row.get("available_at") or row.get("publish_date"),
                "retrieved_at": row.get("retrieved_at") or row.get("retrieved_at_utc"),
                "version_label": row.get("version_label"),
                "status": row.get("status"),
                "access_status": row.get("access_status"),
                "sha256": row.get("sha256"),
                "text_sha256": row.get("text_sha256"),
                "original_file_path": row.get("original_file_path") or row.get("local_path"),
                "parsed_text_path": row.get("parsed_text_path"),
                "page_count": row.get("page_count"),
                "entity_match_status": row.get("entity_match_status"),
                "entity_match_confidence": row.get("entity_match_confidence"),
                "notes": row.get("notes"),
            }
            self._add_node(document_id, "DOCUMENT", security_code, title or document_id, attributes)
            self._add_edge(document_id, security_node, "DESCRIBES_SECURITY")
            supersedes = _text(row.get("supersedes_document_id"))
            if supersedes:
                predecessor_id = supersedes if supersedes.startswith("doc_") else f"doc_{supersedes}"
                self._add_node(
                    predecessor_id,
                    "DOCUMENT",
                    security_code,
                    predecessor_id,
                    {"placeholder": True, "reason": "Referenced by document version chain"},
                )
                self._add_edge(document_id, predecessor_id, "SUPERSEDES")

            parsed_path = _text(row.get("parsed_text_path"))
            text_sha = _text(row.get("text_sha256"))
            if parsed_path or text_sha:
                parsed_id = _stable_id("parsed", document_id, parsed_path, text_sha)
                self._add_node(
                    parsed_id,
                    "PARSED_TEXT",
                    security_code,
                    parsed_path or text_sha,
                    {
                        "parsed_text_path": parsed_path,
                        "text_sha256": text_sha,
                        "language": row.get("language"),
                    },
                )
                self._add_edge(parsed_id, document_id, "PARSED_FROM")

            for attachment in row.get("attachments") or []:
                item = attachment if isinstance(attachment, dict) else attachment.model_dump(mode="json")
                attachment_id = _text(item.get("attachment_id")) or _stable_id(
                    "attachment", document_id, item.get("source_url"), item.get("file_name")
                )
                if not attachment_id.startswith("attachment_"):
                    attachment_id = f"attachment_{attachment_id}"
                self._add_node(
                    attachment_id,
                    "ATTACHMENT",
                    security_code,
                    _text(item.get("file_name")) or attachment_id,
                    item,
                )
                self._add_edge(attachment_id, document_id, "ATTACHED_TO")

    def _ensure_document_for_fact(self, row: dict[str, Any]) -> str | None:
        if not any(
            _text(row.get(key))
            for key in ("document_id", "source_url", "source_document")
        ):
            return None
        document_id = _document_id(row)
        if document_id not in self._nodes:
            security_code = _text(row.get("security_code"))
            title = _text(row.get("source_document")) or _text(row.get("source_url")) or document_id
            self._add_node(
                document_id,
                "DOCUMENT",
                security_code,
                title,
                {
                    "placeholder": True,
                    "source_url": row.get("source_url"),
                    "source_document": row.get("source_document"),
                    "reason": "Created from source fact lineage; no separate document record supplied",
                },
            )
            self._add_edge(document_id, self._security_node(security_code), "DESCRIBES_SECURITY")
        return document_id

    def _add_source_facts(self, source_facts: list[dict[str, Any]]) -> None:
        for row in source_facts:
            source_fact_id = _text(row.get("source_fact_id"))
            if not source_fact_id:
                continue
            security_code = _text(row.get("security_code"))
            attributes = dict(row)
            self._add_node(
                source_fact_id,
                "SOURCE_FACT",
                security_code,
                _text(row.get("metric_name_cn") or row.get("field_name_cn") or row.get("field_key")),
                attributes,
            )
            self._add_edge(source_fact_id, self._security_node(security_code), "DESCRIBES_SECURITY")
            document_id = self._ensure_document_for_fact(row)
            if document_id:
                self._add_edge(source_fact_id, document_id, "DERIVED_FROM_DOCUMENT")
            page = row.get("source_page")
            source_row = _text(row.get("source_row"))
            if document_id and (page not in (None, "") or source_row):
                location_id = _stable_id("loc", document_id, page, source_row)
                self._add_node(
                    location_id,
                    "EVIDENCE_LOCATION",
                    security_code,
                    f"{document_id} p.{page or '?'}",
                    {
                        "document_id": document_id,
                        "page": page,
                        "source_row": source_row,
                    },
                )
                self._add_edge(source_fact_id, location_id, "LOCATED_AT")
                self._add_edge(location_id, document_id, "PART_OF_DOCUMENT")

    def _add_observations(self, observations: list[dict[str, Any]]) -> None:
        for row in observations:
            observation_id = _text(row.get("observation_id"))
            if not observation_id:
                continue
            security_code = _text(row.get("security_code"))
            self._add_node(
                observation_id,
                "CANONICAL_OBSERVATION",
                security_code,
                _text(row.get("metric_name_cn") or row.get("metric_id")),
                dict(row),
            )
            self._add_edge(observation_id, self._security_node(security_code), "DESCRIBES_SECURITY")

    def _add_lineage(self, lineage: list[dict[str, Any]]) -> None:
        edge_type_by_role = {
            "SELECTED": "SELECTED_FOR",
            "SUPPORTING": "SUPPORTS",
            "CONFLICTING": "CONFLICTS_WITH",
            "QUARANTINED": "QUARANTINED_FOR",
        }
        for row in lineage:
            observation_id = _text(row.get("observation_id"))
            source_fact_id = _text(row.get("source_fact_id"))
            if not observation_id or not source_fact_id:
                continue
            self._add_edge(
                observation_id,
                source_fact_id,
                edge_type_by_role.get(_text(row.get("role")), "SUPPORTS"),
                {
                    "lineage_id": row.get("lineage_id"),
                    "role": row.get("role"),
                    "source_priority": row.get("source_priority"),
                    "source_name": row.get("source_name"),
                    "source_status": row.get("source_status"),
                    "selection_reason": row.get("selection_reason"),
                },
            )

    def _quality(self, nodes: pd.DataFrame, edges: pd.DataFrame) -> dict[str, Any]:
        node_ids = set(nodes.get("node_id", []))
        dangling = edges[
            ~edges["from_node_id"].isin(node_ids) | ~edges["to_node_id"].isin(node_ids)
        ] if not edges.empty else pd.DataFrame()
        observations = nodes[nodes["node_type"] == "CANONICAL_OBSERVATION"] if not nodes.empty else nodes
        lineage_edges = edges[
            edges["edge_type"].isin({"SELECTED_FOR", "SUPPORTS", "CONFLICTS_WITH", "QUARANTINED_FOR"})
        ] if not edges.empty else edges
        observations_with_lineage = set(lineage_edges.get("from_node_id", []))

        fact_to_location = set(
            edges.loc[edges["edge_type"] == "LOCATED_AT", "from_node_id"]
        ) if not edges.empty else set()
        fact_to_document = set(
            edges.loc[edges["edge_type"] == "DERIVED_FROM_DOCUMENT", "from_node_id"]
        ) if not edges.empty else set()
        evidenced_facts = fact_to_location | fact_to_document
        observations_with_evidence = set(
            lineage_edges.loc[lineage_edges["to_node_id"].isin(evidenced_facts), "from_node_id"]
        ) if not lineage_edges.empty else set()
        observation_count = len(observations)
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_type_counts": dict(Counter(nodes.get("node_type", []))),
            "edge_type_counts": dict(Counter(edges.get("edge_type", []))),
            "duplicate_node_id_count": int(nodes.get("node_id", pd.Series(dtype="object")).duplicated().sum()),
            "duplicate_edge_id_count": int(edges.get("edge_id", pd.Series(dtype="object")).duplicated().sum()),
            "dangling_edge_count": len(dangling),
            "observation_count": observation_count,
            "observation_lineage_coverage": (
                None if observation_count == 0 else len(observations_with_lineage) / observation_count
            ),
            "observation_evidence_coverage": (
                None if observation_count == 0 else len(observations_with_evidence) / observation_count
            ),
            "status": (
                "PASS"
                if len(dangling) == 0
                and len(observations_with_lineage) == observation_count
                and not nodes.get("node_id", pd.Series(dtype="object")).duplicated().any()
                and not edges.get("edge_id", pd.Series(dtype="object")).duplicated().any()
                else "FAIL"
            ),
        }

    def build(
        self,
        *,
        documents: Any = None,
        source_facts: Any = None,
        canonical_observations: Any = None,
        lineage: Any = None,
    ) -> EvidenceGraphResult:
        self._nodes = {}
        self._edges = {}
        self._add_documents(_records(documents))
        self._add_source_facts(_records(source_facts))
        self._add_observations(_records(canonical_observations))
        self._add_lineage(_records(lineage))
        nodes = pd.DataFrame([item.to_dict() for item in self._nodes.values()])
        edges = pd.DataFrame([item.to_dict() for item in self._edges.values()])
        if not nodes.empty:
            nodes = nodes.sort_values(["node_type", "node_id"]).reset_index(drop=True)
        if not edges.empty:
            edges = edges.sort_values(["edge_type", "from_node_id", "to_node_id"]).reset_index(drop=True)
        return EvidenceGraphResult(nodes, edges, self._quality(nodes, edges))
