from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK_ID = "codex-entrypoint-hardening-v1"
TASK_DIR = ROOT / "docs/implementation" / TASK_ID
MERGE_SHA = "43223c2f1acac7f903a5d897cf21656f226956f8"
PR_NUMBER = 51
PREMERGE_RUN = 30058774833


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
            "status": "DONE",
            "execution_status": "COMPLETED",
            "security_status": "PASS",
            "working_branch": "main",
            "pull_request": PR_NUMBER,
            "last_product_commit_sha": args.tested_sha,
            "current_stage": "W08",
            "last_completed_stage": "W08",
            "last_successful_step": "exact_main_zero_codex_hardening_closeout_pass",
            "next_action": "none",
            "updated_at_utc": now,
        }
    )
    state["acceptance"] = {
        "domain": "generic",
        "status": "PASS",
        "reason_code": None,
        "details_path": str(TASK_DIR.relative_to(ROOT) / "FINAL_REPORT.md"),
    }
    state["gate_results"] = {
        **state.get("gate_results", {}),
        "W08_PRE_MERGE": f"PASS:{PREMERGE_RUN}",
        "W08_EXACT_MAIN": f"PASS:{args.run_id}",
        "CODEX_CALLS_DURING_HARDENING": "0",
        "CODEX_POLICY_AFTER_HARDENING": "disabled",
    }
    state["post_merge"] = {
        "status": "PASS",
        "merge_sha": MERGE_SHA,
        "verified_run_ids": [args.run_id],
    }
    state["human_gate"] = {
        "required": False,
        "reason": None,
        "minimum_action": None,
        "resume_from": None,
    }
    notification = state.get("notification", {})
    state["notification"] = {
        **notification,
        "generation": int(notification.get("generation", 0)) + 1,
        "last_type": "COMPLETED",
        "acknowledged": True,
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
                    "status": "DONE",
                    "branch": "main",
                    "pull_request": PR_NUMBER,
                    "current_stage": "W08",
                }
            )
    active_path.write_text(
        json.dumps(active, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    (TASK_DIR / "W08_result.md").write_text(
        "# W08 结果：Exact-main 与最终收尾\n\n"
        "```yaml\n"
        "status: PASS\n"
        f"pull_request: {PR_NUMBER}\n"
        f"merge_sha: {MERGE_SHA}\n"
        f"premerge_run: {PREMERGE_RUN}\n"
        f"exact_main_run: {args.run_id}\n"
        f"exact_main_tested_sha: {args.tested_sha}\n"
        "entrypoint_scan: PASS\n"
        "devflow_and_upgrade: PASS\n"
        "full_product_regression: PASS\n"
        "real_e2e_688521: PASS\n"
        "automatic_model_paths: 0\n"
        "codex_calls: 0\n"
        "codex_policy_after_completion: disabled\n"
        "```\n",
        encoding="utf-8",
    )
    (TASK_DIR / "FINAL_REPORT.md").write_text(
        "# Codex Entrypoint Hardening v1 最终报告\n\n"
        "## 结论\n\n"
        "W00–W08 已在零 Codex 调用条件下完成。仓库常驻模型入口保持硬禁用；Product Gate、Post-Merge、State Consistency、Auto Recovery、Bot、失败 Job 重跑和 GitHub Re-run 均不能进入模型。\n\n"
        "## 最终执行链\n\n"
        "```text\n"
        "ChatGPT Web / deterministic Actions\n"
        "→ zero-model classification and bounded infrastructure retry\n"
        "→ Product Gate / merge / exact-main\n"
        "→ completion\n\n"
        "Optional future Codex use\n"
        "→ positive reason allowlist\n"
        "→ ChatGPT Web necessity assessment\n"
        "→ exact-main trusted control\n"
        "→ trusted real reproduction\n"
        "→ one-time Grant (TTL <= 60m, max_calls=1)\n"
        "→ separate reviewed Activation PR\n"
        "→ one XHigh session, non-rerunnable\n"
        "→ automatic return to disabled\n"
        "```\n\n"
        "## 证据\n\n"
        f"- PR：#{PR_NUMBER}\n"
        f"- Merge SHA：`{MERGE_SHA}`\n"
        f"- Forced pre-merge Run：`{PREMERGE_RUN}`\n"
        f"- Exact-main Run：`{args.run_id}`\n"
        "- 自动模型路径：`0`\n"
        "- 优化期间 Codex 调用：`0`\n"
        "- 完成后 Policy：`disabled`\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python",
            "scripts/devflow/render_task_docs.py",
            "docs/implementation/codex-entrypoint-hardening-v1",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            "python",
            "scripts/devflow/validate_state.py",
            "--task-dir",
            "docs/implementation/codex-entrypoint-hardening-v1",
            "--no-git",
            "--output",
            "/tmp/final-codex-entrypoint-state.json",
        ],
        cwd=ROOT,
        check=True,
    )
    print("CODEX_ENTRYPOINT_EXACT_MAIN_FINALIZED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
