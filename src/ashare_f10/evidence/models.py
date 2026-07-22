from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    node_type: str
    security_code: str
    label: str
    attributes_json: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: str
    attributes_json: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
