from __future__ import annotations

import json
from pathlib import Path

from ashare_f10.api.jobs_v2 import JobManager, extract_security_name
from ashare_f10.config import Settings
from ashare_f10.fetch.client_v2 import build_quote_headers, build_quote_params, is_eastmoney_quote_request
from ashare_f10.models import JobState, RequestSpec


def test_security_name_requires_matching_code() -> None:
    payload = {
        "records": [
            {"SECURITY_CODE": "300795", "SECURITY_NAME_ABBR": "米奥会展"},
            {"SECURITY_CODE": "300308", "SECURITY_NAME_ABBR": "中际旭创"},
        ]
    }
    assert extract_security_name(payload, "300308") == "中际旭创"
    assert extract_security_name(payload, "688041") == ""


def test_quote_payload_name_is_code_validated() -> None:
    payload = {"data": {"f57": "688041", "f58": "海光信息"}}
    assert extract_security_name(payload, "688041") == "海光信息"
    assert extract_security_name(payload, "300308") == ""


def test_quote_transport_profile_uses_stable_headers_and_dynamic_cache_buster() -> None:
    spec = RequestSpec(
        method="GET",
        host="push2.eastmoney.com",
        path="/api/qt/stock/get",
        params={
            "secid": "0.300308",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fields": "f57,f58,f43",
        },
        headers={"ct": "expired", "ut": "expired", "Cookie": "stale=1"},
    )
    assert is_eastmoney_quote_request(spec)
    headers = build_quote_headers(spec)
    assert "ct" not in {key.lower() for key in headers}
    assert "ut" not in {key.lower() for key in headers}
    assert "cookie" not in {key.lower() for key in headers}
    assert headers["Connection"] == "close"
    assert "SZ300308" in headers["pageurl"]

    first = build_quote_params(spec)
    second = build_quote_params(spec)
    assert first["ut"] == "bd1d9ddb04089700cf9c27f6f7426281"
    assert first["v"] != second["v"]


def test_legacy_name_repair_ignores_unrelated_company(tmp_path: Path) -> None:
    manager = JobManager(Settings(data_dir=tmp_path, max_workers=1, page_workers=1, retries=1))
    group_id, definition = next(iter(manager.group_definitions.items()))
    job_id = "legacy-name-job"
    output_dir = tmp_path / "300308" / job_id
    (output_dir / "groups").mkdir(parents=True)
    state = JobState(
        job_id=job_id,
        stock_code="300308",
        stock_name="米奥会展",
        status="PARTIAL",
        created_at_utc="2026-07-20T10:00:00Z",
        updated_at_utc="2026-07-20T10:00:00Z",
        total_groups=len(manager.group_definitions),
        output_dir=str(output_dir),
    )
    manager._save(state)
    manager._initialize_group_rows(job_id)
    payload = {
        "group_id": group_id,
        "theme": definition["theme"],
        "family": definition["family"],
        "strategy": definition["strategy"],
        "success": True,
        "used_fallback": False,
        "record_count": 0,
        "records": [],
        "payloads": [
            {
                "items": [
                    {"SECURITY_CODE": "300795", "SECURITY_NAME_ABBR": "米奥会展"},
                    {"SECURITY_CODE": "300308", "SECURITY_NAME_ABBR": "中际旭创"},
                ]
            }
        ],
        "requests": [],
        "errors": [],
        "started_at_utc": "2026-07-20T10:00:00Z",
        "completed_at_utc": "2026-07-20T10:00:01Z",
    }
    (output_dir / "groups" / f"{group_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    manager._sync_group_files(state)
    assert state.stock_name == "中际旭创"


def test_task_center_preserves_expanded_subtask_dom() -> None:
    source = Path("src/ashare_f10/web/job-center-v2.js").read_text(encoding="utf-8")
    assert "newGroups.replaceWith(oldGroups)" in source
    assert "center.groupUi" in source
    assert "event.stopPropagation()" in source
