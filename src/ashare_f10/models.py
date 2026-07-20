from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SecurityIdentity(BaseModel):
    code: str
    exchange: Literal["SH", "SZ", "BJ"]
    secucode: str
    page_code: str
    market_id: int
    market_id_code: str


class RequestSpec(BaseModel):
    method: str = "GET"
    scheme: str = "https"
    host: str
    path: str
    params: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    headers: dict[str, str] = Field(default_factory=dict)


class GroupResult(BaseModel):
    group_id: str
    theme: str
    family: str
    strategy: str
    success: bool
    used_fallback: bool = False
    record_count: int = 0
    records: list[dict[str, Any]] = Field(default_factory=list)
    payloads: list[Any] = Field(default_factory=list)
    requests: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    started_at_utc: str
    completed_at_utc: str


class JobState(BaseModel):
    job_id: str
    stock_code: str
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    created_at_utc: str
    updated_at_utc: str
    completed_groups: int = 0
    total_groups: int = 0
    failed_groups: int = 0
    current_group: str = ""
    message: str = ""
    output_dir: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    security_code: str
    theme: str
    family: str
    dataset: str
    report_date: str | None = None
    event_date: str | None = None
    field_key: str
    field_name_cn: str
    value_text: str | None = None
    value_num: float | None = None
    unit: str = ""
    score: float = 0.0
    source_url: str = ""


class FormulaRequest(BaseModel):
    formula: str
    end_period: str | None = None


class TTMRequest(BaseModel):
    field: str
    end_period: str
