from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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


SearchOperation = Literal["include", "exclude", "or"]
SearchMatchType = Literal["fuzzy", "contains", "exact", "prefix", "regex", "empty", "not_empty"]
FilterOperator = Literal[
    "in",
    "not_in",
    "contains",
    "not_contains",
    "exact",
    "not_equal",
    "prefix",
    "gte",
    "lte",
    "between",
    "is_empty",
    "not_empty",
]
SortDirection = Literal["asc", "desc"]


class SearchStep(BaseModel):
    query: str = ""
    operation: SearchOperation = "include"
    match_type: SearchMatchType = "fuzzy"
    columns: list[str] = Field(default_factory=list)
    threshold: float = Field(default=60.0, ge=0, le=100)
    enabled: bool = True

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 200:
            raise ValueError("搜索词不能超过200个字符")
        return value

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, value: list[str]) -> list[str]:
        if len(value) > 10:
            raise ValueError("单个搜索步骤最多选择10列")
        return list(dict.fromkeys(value))


class SearchColumnFilter(BaseModel):
    column: str
    operator: FilterOperator
    value: Any = None
    values: list[Any] = Field(default_factory=list)
    lower: Any = None
    upper: Any = None
    enabled: bool = True


class SearchSort(BaseModel):
    column: str
    direction: SortDirection = "asc"


class SearchQueryRequest(BaseModel):
    base_query: str = ""
    base_match_type: SearchMatchType = "fuzzy"
    base_columns: list[str] = Field(default_factory=list)
    base_threshold: float = Field(default=60.0, ge=0, le=100)
    search_steps: list[SearchStep] = Field(default_factory=list)
    filters: list[SearchColumnFilter] = Field(default_factory=list)
    sort: list[SearchSort] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=200, ge=1, le=1000)

    @field_validator("base_query")
    @classmethod
    def validate_base_query(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 200:
            raise ValueError("基础搜索词不能超过200个字符")
        return value

    @field_validator("search_steps")
    @classmethod
    def validate_steps(cls, value: list[SearchStep]) -> list[SearchStep]:
        if len(value) > 10:
            raise ValueError("二次搜索最多支持10个步骤")
        return value

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value: list[SearchColumnFilter]) -> list[SearchColumnFilter]:
        if len(value) > 30:
            raise ValueError("逐列筛选条件最多30个")
        return value

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, value: list[SearchSort]) -> list[SearchSort]:
        if len(value) > 5:
            raise ValueError("最多支持5级排序")
        return value


class SearchFacetRequest(BaseModel):
    query: SearchQueryRequest = Field(default_factory=SearchQueryRequest)
    column: str
    term: str = ""
    limit: int = Field(default=200, ge=1, le=500)

    @field_validator("term")
    @classmethod
    def validate_term(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 100:
            raise ValueError("筛选值搜索词不能超过100个字符")
        return value


class SearchExportRequest(BaseModel):
    query: SearchQueryRequest = Field(default_factory=SearchQueryRequest)
    format: Literal["csv", "json"] = "csv"
    max_rows: int = Field(default=100_000, ge=1, le=500_000)

    @model_validator(mode="after")
    def reset_pagination(self) -> SearchExportRequest:
        self.query.page = 1
        self.query.page_size = min(self.max_rows, 1000)
        return self


class FormulaRequest(BaseModel):
    formula: str
    end_period: str | None = None


class TTMRequest(BaseModel):
    field: str
    end_period: str
