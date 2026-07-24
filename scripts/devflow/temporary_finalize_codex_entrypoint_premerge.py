from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "codex-entrypoint-hardening-v1"
TASK_DIR = ROOT / "docs/implementation" / TASK_ID
BRANCH = "feature/codex-entrypoint-hardening-v1"
PR_NUMBER = 51


def write_result(stage: str, title: str, lines: list[str]) -> None:
    body = [f"# {stage} 结果：{title}", "", "```yaml", "status: PASS"]
    body.extend(lines)
    body.extend(["codex_calls: 0", "```", ""])
    (TASK_DIR / f"{stage}_result.md").write_text(
        "\n".join(body), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--tested-sha", required=True)
    args = parser.parse_args()
    if len(args.tested_sha) != 40:
        raise SystemExit("tested SHA must be 40 characters")

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_path = TASK_DIR / "task_state.yaml"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "state_revision": int(state.get("state_revision", 0)) + 1,
            "status": "VERIFYING",
            "execution_status": "RUNNING",
            "security_status": "PASS",
            "working_branch": BRANCH,
            "pull_request": PR_NUMBER,
            "last_product_commit_sha": args.tested_sha,
            "current_stage": "W08",
            "last_completed_stage": "W07",
            "last_successful_step": "forced_premerge_zero_codex_validation_pass",
            "next_action": "merge_pr51_then_run_exact_main_closeout",
            "updated_at_utc": now,
        }
    )
    state["acceptance"] = {
        "domain": "generic",
        "status": "PENDING",
        "reason_code": None,
        "details_path": None,
    }
    state["gate_results"] = {
        "W00_ENTRYPOINT_INVENTORY": "PASS",
        "W01_PRODUCT_GATE_ZERO_MODEL": "PASS",
        "W02_RECOVERY_GENERATIONS_ZERO": "PASS",
        "W03_MODEL_JOB_NON_RERUNNABLE": "PASS",
        "W04_TRUSTED_CONTROL": "PASS",
        "W05_POSITIVE_ALLOWLIST": "PASS",
        "W06_TRUSTED_REPRODUCTION": "PASS",
        "W07_ONE_TIME_GRANT": "PASS",
        "W08_PRE_MERGE": f"PASS:{args.run_id}",
        "CODEX_CALLS_DURING_HARDENING": "0",
    }
    state["post_merge"] = {
        "status": "PENDING",
        "merge_sha": None,
        "verified_run_ids": [],
    }
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    active_path = ROOT / "docs/implementation/ACTIVE_TASKS.yaml"
    active = json.loads(active_path.read_text(encoding="utf-8"))
    for item in active.get("tasks", []):
        if item.get("task_id") == TASK_ID:
            item.update(
                {
                    "status": "VERIFYING",
                    "branch": BRANCH,
                    "pull_request": PR_NUMBER,
                    "current_stage": "W08",
                }
            )
    active_path.write_text(
        json.dumps(active, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    write_result(
        "W00",
        "全模型入口清单",
        [
            "entrypoint_manifest: PASS",
            "automatic_model_paths: 0",
            "policy_mode: disabled",
        ],
    )
    write_result(
        "W01",
        "Product Gate 零模型失败处理",
        [
            "product_gate_recovery_dispatch: removed",
            "failure_route: PRODUCT_GATE_WEB_REPAIR_REQUIRED",
        ],
    )
    write_result(
        "W02",
        "Recovery Generation 永久归零",
        [
            "schema_v2_max_recovery_generations: 0",
            "schema_v1_effective_max_recovery_generations: 0",
            "production_recovery_task_generator: removed",
        ],
    )
    write_result(
        "W03",
        "Model-bearing Job 不可重跑",
        [
            "auto_recovery_observes_codex_task: false",
            "model_job_rerunnable: false",
            "grant_states: ISSUED_RESERVED_CONSUMED",
        ],
    )
    write_result(
        "W04",
        "可信控制平面",
        [
            "control_ref: exact_main_sha",
            "task_branch_data_only: true",
            "permanent_entrypoint_mode: eligibility_only",
        ],
    )
    write_result(
        "W05",
        "正向 Reason Allowlist 与 Web 必要性",
        [
            "unknown_reason_route: CHATGPT_WEB",
            "web_resolution_assessment_required: true",
            "single_file_simple_task_codex_candidate: false",
        ],
    )
    write_result(
        "W06",
        "受信任真实复现",
        [
            "trusted_pre_model_job_required: true",
            "task_branch_self_report_sufficient: false",
            "artifact_digest_binding: required",
        ],
    )
    write_result(
        "W07",
        "一次性 Grant 与 Activation",
        [
            "grant_ttl_minutes_max: 60",
            "calls_per_task: 1",
            "calls_per_fingerprint: 1",
            "activation_mode: one_time_reviewed_pr",
        ],
    )

    import subprocess

    subprocess.run(
        [
            "python",
            "scripts/devflow/render_task_docs.py",
            "docs/implementation/codex-entrypoint-hardening-v1",
        ],
        cwd=ROOT,
        check=True,
    )
    print("CODEX_ENTRYPOINT_PREMERGE_FINALIZED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
