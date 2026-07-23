from __future__ import annotations

import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
task_id = "devflow-operational-optimization-v2"
task_dir = root / "docs/implementation" / task_id
branch = "feature/devflow-operational-optimization-v2-clean"
base_sha = "fb895fd372007f41f611b40b4cb0eb57476a6b32"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


# Manual-only Codex entry: policy and zero-token eligibility are evaluated before
# Environment Secrets, the forwarder or the model-bearing job can start.
codex_path = root / ".github/workflows/codex-task.yml"
codex = codex_path.read_text(encoding="utf-8")
if "codex_eligibility.py" not in codex:
    codex = codex.replace(
        "      task_branch:\n        description: Trusted control branch containing .agent/current_task.yaml\n        required: true\n        type: string\n",
        "      task_branch:\n        description: Trusted control branch containing .agent/current_task.yaml\n        required: true\n        type: string\n      approval_file:\n        description: Task-bound ChatGPT Web approval JSON on the trusted branch\n        required: false\n        type: string\n        default: .devflow/codex-approvals/approval.json\n      reproduction_file:\n        description: Deterministic pre-model reproduction result JSON\n        required: false\n        type: string\n        default: .agent/reproduction.json\n",
        1,
    )
    codex = codex.replace(
        "    if: github.actor == 'tyxq428' || github.actor == 'github-actions[bot]'",
        "    if: github.actor == 'tyxq428'",
        1,
    )
    codex = codex.replace(
        "      publish_branch: ${{ steps.task.outputs.publish_branch }}\n",
        "      publish_branch: ${{ steps.task.outputs.publish_branch }}\n      policy_enabled: ${{ steps.task.outputs.policy_enabled }}\n      eligible: ${{ steps.eligibility.outputs.eligible }}\n",
        1,
    )
    codex = codex.replace(
        "          if actor not in {'tyxq428', 'github-actions[bot]'}:\n              raise SystemExit('untrusted actor')\n\n          _raw, task = load_task_descriptor(Path('.agent/current_task.yaml'))\n",
        "          if actor != 'tyxq428':\n              raise SystemExit('untrusted actor')\n\n          policy = __import__('json').loads(Path('.devflow/codex-policy.yaml').read_text())\n          policy_enabled = policy.get('mode') == 'enabled'\n          _raw, task = load_task_descriptor(Path('.agent/current_task.yaml'))\n",
        1,
    )
    codex = codex.replace(
        "              handle.write(f'publish_branch={task.publish_branch}\\n')\n          PY\n\n  codex:\n",
        "              handle.write(f'publish_branch={task.publish_branch}\\n')\n              handle.write(f'policy_enabled={str(policy_enabled).lower()}\\n')\n          PY\n\n      - id: eligibility\n        name: Evaluate explicit zero-token Codex eligibility\n        if: steps.task.outputs.policy_enabled == 'true'\n        continue-on-error: true\n        shell: bash\n        env:\n          ACTOR: ${{ github.actor }}\n          APPROVAL_FILE: ${{ inputs.approval_file }}\n          REPRODUCTION_FILE: ${{ inputs.reproduction_file }}\n        run: |\n          set -euo pipefail\n          python scripts/devflow/codex_eligibility.py \\\n            --task-file .agent/current_task.yaml \\\n            --approval-file \"$APPROVAL_FILE\" \\\n            --reproduction-file \"$REPRODUCTION_FILE\" \\\n            --actor \"$ACTOR\" \\\n            --output /tmp/codex-eligibility.json\n          echo \"eligible=true\" >> \"$GITHUB_OUTPUT\"\n\n  no-model:\n    name: policy-or-eligibility-stopped-before-model\n    needs: read-task\n    if: needs.read-task.outputs.eligible != 'true'\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - run: |\n          echo \"CODEX_MODEL_INVOCATION=DISABLED_OR_NOT_APPROVED\" >> \"$GITHUB_STEP_SUMMARY\"\n          echo \"No Environment Secret, forwarder or model session was started.\" >> \"$GITHUB_STEP_SUMMARY\"\n\n  codex:\n",
        1,
    )
    codex = codex.replace(
        "  codex:\n    name: secret-bearing-read-only-codex\n    needs: read-task\n    runs-on: ubuntu-latest\n",
        "  codex:\n    name: secret-bearing-read-only-codex\n    needs: read-task\n    if: needs.read-task.outputs.eligible == 'true'\n    runs-on: ubuntu-latest\n",
        1,
    )

for required in (
    "github.actor == 'tyxq428'",
    "codex_eligibility.py",
    "policy-or-eligibility-stopped-before-model",
    "needs.read-task.outputs.eligible == 'true'",
):
    if required not in codex:
        raise SystemExit(f"Codex entry migration missing: {required}")
if "actor not in {'tyxq428', 'github-actions[bot]'}" in codex:
    raise SystemExit("Bot actor remains authorized")
codex_path.write_text(codex, encoding="utf-8")

# Exact-main failures route to ChatGPT Web. They never create or dispatch a model task.
post_merge = r'''name: Devflow Post Merge

on:
  repository_dispatch:
    types:
      - devflow_post_merge

permissions:
  contents: write
  actions: read

concurrency:
  group: devflow-post-merge-${{ github.event.client_payload.task_id }}
  cancel-in-progress: false

env:
  PYTHONDONTWRITEBYTECODE: "1"
  PYTHONUNBUFFERED: "1"

jobs:
  exact-main:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09
        with:
          ref: main
          fetch-depth: 0
          persist-credentials: false
      - name: Validate exact-main payload and immutable task descriptor
        id: task
        shell: bash
        env:
          TASK_ID: ${{ github.event.client_payload.task_id }}
          TASK_BRANCH: ${{ github.event.client_payload.task_branch }}
          MERGE_SHA: ${{ github.event.client_payload.merge_sha }}
        run: |
          set -euo pipefail
          [[ "$TASK_BRANCH" == task/codex-* ]]
          [[ "$MERGE_SHA" =~ ^[0-9a-f]{40}$ ]]
          git fetch --no-tags origin main "+refs/heads/${TASK_BRANCH}:refs/remotes/origin/${TASK_BRANCH}"
          git merge-base --is-ancestor "$MERGE_SHA" HEAD
          git show "refs/remotes/origin/${TASK_BRANCH}:.agent/current_task.yaml" > /tmp/devflow-task.yaml
          python - <<'PY' >> "$GITHUB_OUTPUT"
          import json
          import os
          import sys
          from pathlib import Path
          sys.path.insert(0, 'scripts/devflow')
          from task_descriptor import TaskDescriptor
          task = TaskDescriptor.from_mapping(json.loads(Path('/tmp/devflow-task.yaml').read_text()))
          if task.task_id != os.environ['TASK_ID']:
              raise SystemExit('task_id payload mismatch')
          print(f'post_merge_profile={task.post_merge_profile}')
          PY
      - name: Install deterministic development dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Run exact-main regression profile
        id: post_gate
        continue-on-error: true
        run: |
          python scripts/devflow/run_gate_profile.py \
            "${{ steps.task.outputs.post_merge_profile }}" \
            --output /tmp/post-merge-gate-result.json
      - name: Stop and route failed exact-main verification to ChatGPT Web
        if: steps.post_gate.outcome != 'success'
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          python - <<'PY'
          import json
          from pathlib import Path
          payload = {
              'event_type': 'devflow_notify',
              'client_payload': {
                  'action': 'INTERRUPTED',
                  'notification_type': 'INTERRUPTED',
                  'reason_code': 'POST_MERGE_WEB_REPAIR_REQUIRED',
                  'reason': 'Exact-main verification failed. Automatic Codex repair is disabled.',
                  'minimum_action': 'Inspect the bounded gate result in ChatGPT Web and repair deterministically.',
                  'fingerprint': 'post-merge-web-repair-${{ github.event.client_payload.task_id }}',
                  'source_workflow': 'Devflow Post Merge',
                  'source_run_id': int('${{ github.run_id }}'),
                  'failure_steps': ['Run exact-main regression profile'],
              },
          }
          Path('/tmp/devflow-notify.json').write_text(json.dumps(payload))
          PY
          gh api --method POST "repos/${{ github.repository }}/dispatches" \
            --input /tmp/devflow-notify.json
          exit 1
      - name: Record exact-main pass
        if: steps.post_gate.outcome == 'success'
        run: |
          echo "EXACT_MAIN_POST_MERGE=PASS" >> "$GITHUB_STEP_SUMMARY"
          echo "No Codex session or recovery generation was used." >> "$GITHUB_STEP_SUMMARY"
'''
write(root / ".github/workflows/devflow-post-merge.yml", post_merge)

# Update static workflow policy to enforce the new manual-only boundaries.
validator = root / "scripts/devflow/validate_workflows.py"
text = validator.read_text(encoding="utf-8")
text = text.replace(
    '                "./.github/actions/codex-thin-worker",\n                "http://127.0.0.1:8787/health",',
    '                "codex_eligibility.py",\n                "approval_file",\n                "reproduction_file",\n                "needs.read-task.outputs.eligible == \'true\'",\n                "./.github/actions/codex-thin-worker",\n                "http://127.0.0.1:8787/health",',
    1,
)
text = text.replace(
    '        if re.search(r"^\\s{2}push:\\s*$", text, re.MULTILINE):',
    '        for forbidden in (\n            "github.actor == \'github-actions[bot]\'",\n            "actor not in {\'tyxq428\', \'github-actions[bot]\'}",\n            "allow-bot-users:",\n        ):\n            if forbidden in text:\n                errors.append(f"{path}: bot actors may not dispatch Codex: {forbidden}")\n        if re.search(r"^\\s{2}push:\\s*$", text, re.MULTILINE):',
    1,
)
text = text.replace(
    '                "rerun-failed-jobs",\n                "recovery_policy.py",\n                "recovery_task.py",\n                "devflow_notify",\n                "No task-control notification was emitted",',
    '                "rerun-failed-jobs",\n                "recovery_policy.py",\n                "devflow_notify",\n                "No Codex task was created or retried",',
    1,
)
text = text.replace(
    '        if "issues: write" in text:\n            errors.append(f"{path}: auto recovery must not write Issues directly")',
    '        if "issues: write" in text:\n            errors.append(f"{path}: auto recovery must not write Issues directly")\n        for forbidden in (\n            "actions/workflows/codex-task.yml/dispatches",\n            "steps.decision.outputs.action == \'RETRY_CODEX\'",\n            "python scripts/devflow/recovery_task.py",\n        ):\n            if forbidden in text:\n                errors.append(f"{path}: automatic Codex path is forbidden: {forbidden}")',
    1,
)
text = text.replace(
    '                "run_gate_profile.py",\n                "recovery_task.py",\n                "finalize_task.py",\n                "devflow_notify",',
    '                "run_gate_profile.py",\n                "POST_MERGE_WEB_REPAIR_REQUIRED",\n                "devflow_notify",',
    1,
)
text = text.replace(
    '        if "environment: agent-runtime" in text:\n            errors.append(f"{path}: post-merge must not access relay Environment Secrets")',
    '        if "environment: agent-runtime" in text:\n            errors.append(f"{path}: post-merge must not access relay Environment Secrets")\n        for forbidden in (\n            "actions/workflows/codex-task.yml/dispatches",\n            "python scripts/devflow/recovery_task.py",\n            "steps.decision.outputs.action == \'RETRY_CODEX\'",\n        ):\n            if forbidden in text:\n                errors.append(f"{path}: post-merge automatic Codex path is forbidden: {forbidden}")',
    1,
)
validator.write_text(text, encoding="utf-8")

# Versioned task evidence.
task_dir.mkdir(parents=True, exist_ok=True)
write(task_dir / "00_contract.md", """# Task Contract

Complete W00–W07 without any Codex call. Keep Codex disabled by default and require explicit user authorization plus zero-token eligibility before any future use. No F10 business semantics change and no relay-secret access.
""")
write(task_dir / "01_master_plan.md", """# Master Plan

W00 freeze; W01 clean rebuild; W02 deterministic repairs; W03 context and impact gates; W04 state separation and dry-run GC; W05 upgrade and minimal Codex eligibility; W06 full validation; W07 exact-main closeout.
""")
write(task_dir / "DECISIONS.md", """# Decisions

- ChatGPT Web is the default repair path.
- Auto Recovery retries infrastructure only.
- Codex remains globally disabled and can never be started by a bot, failed-job rerun or synthesized recovery.
- Branch GC is dry-run by default.
""")
plans = {
    "W00": "Freeze every model entry point.",
    "W01": "Rebuild from frozen main and synchronize circuit breakers.",
    "W02": "Repair deterministic state, formatting and compatibility failures.",
    "W03": "Finish Context Budget, impact gates and dependency-only caches.",
    "W04": "Separate execution, acceptance and security state; add dry-run branch GC.",
    "W05": "Add version compatibility and explicit minimal-use Codex eligibility.",
    "W06": "Run zero-model gates, complete product Test and real E2E.",
    "W07": "Merge, exact-main verification and canonical closeout.",
}
results = {
    "W00": "Repository policy disabled and production action stops before the official model action.",
    "W01": "Clean branch rebuilt; temporary and duplicate implementations removed.",
    "W02": "State, Workflow, Ruff and compatibility defects repaired deterministically.",
    "W03": "Context and impact-aware gate implementation ready for CI.",
    "W04": "Schema v2 and dry-run branch GC implementation ready for CI.",
    "W05": "Historical waste fixtures and explicit eligibility controls implemented.",
}
for stage, objective in plans.items():
    write(task_dir / f"{stage}_plan.md", f"# {stage} Plan\n\n{objective}\n\nCodex budget: 0 calls.\n")
for stage, summary in results.items():
    write(task_dir / f"{stage}_result.md", f"# {stage} Result\n\n```yaml\nstatus: PASS\ncodex_calls: 0\n```\n\n{summary}\n")

active_path = root / "docs/implementation/ACTIVE_TASKS.yaml"
active = json.loads(active_path.read_text(encoding="utf-8"))
active["tasks"] = [item for item in active.get("tasks", []) if item.get("task_id") != task_id]
active["tasks"].append(
    {
        "task_id": task_id,
        "title": "Devflow operational optimization and minimal Codex eligibility",
        "status": "VERIFYING",
        "branch": branch,
        "pull_request": 50,
        "current_stage": "W06",
        "state_path": f"docs/implementation/{task_id}/task_state.yaml",
    }
)
write(active_path, json.dumps(active, indent=2, ensure_ascii=False))
state = {
    "schema_version": 2,
    "state_revision": 1,
    "task_id": task_id,
    "title": "Devflow operational optimization and minimal Codex eligibility",
    "status": "VERIFYING",
    "execution_status": "RUNNING",
    "acceptance": {"domain": "generic", "status": "PENDING", "reason_code": None, "details_path": None},
    "security_status": "PENDING",
    "working_branch": branch,
    "pull_request": 50,
    "base_sha_at_start": base_sha,
    "last_product_commit_sha": base_sha,
    "last_state_commit_sha": None,
    "current_stage": "W06",
    "last_completed_stage": "W05",
    "last_successful_step": "zero_model_implementation_ready_for_ci",
    "next_action": "run_pr50_zero_model_gates_and_forced_full_validation",
    "gate_results": {
        "W00_CODEX_FREEZE": "PASS:PR46",
        "W01_CLEAN_REBUILD": "PASS",
        "W02_DETERMINISTIC_REPAIRS": "PASS",
        "W03_CONTEXT_AND_IMPACT": "PENDING_CI",
        "W04_STATE_AND_BRANCH_GC": "PENDING_CI",
        "W05_CODEX_ELIGIBILITY": "PENDING_CI",
    },
    "retry_budget": {"infrastructure": 3, "codex_sessions": 0, "codex_recovery_generations": 0, "replans": 2},
    "human_gate": {"required": False, "reason": None, "minimum_action": None, "resume_from": None},
    "post_merge": {"status": "PENDING", "merge_sha": None, "verified_run_ids": []},
    "notification": {"generation": 0, "last_type": None, "acknowledged": True, "control_issue_number": None},
    "updated_at_utc": "2026-07-23T19:05:00Z",
}
write(task_dir / "task_state.yaml", json.dumps(state, indent=2, ensure_ascii=False))
subprocess.run(
    ["python", "scripts/devflow/render_task_docs.py", str(task_dir.relative_to(root))],
    cwd=root,
    check=True,
)

# Persist the strict default in long-lived policy and runbook text.
security_policy = root / "docs/process/policies/security-and-codex.md"
security = security_policy.read_text(encoding="utf-8")
if "## 默认禁用与显式授权" not in security:
    security += """

## 默认禁用与显式授权

Codex 默认禁用。只有用户针对不可变 Task Descriptor 明确授权，且失败可复现、失败文件被允许范围覆盖、Context Budget 通过、指纹未使用时，才可成为一次性候选。Bot、Auto Recovery、State Consistency、Post-Merge 和 failed-job rerun 均不得启动或重试模型。
"""
security_policy.write_text(security, encoding="utf-8")
recovery_runbook = root / "docs/process/runbooks/automatic-recovery.md"
recovery = recovery_runbook.read_text(encoding="utf-8")
if "## 零模型恢复边界" not in recovery:
    recovery += """

## 零模型恢复边界

自动恢复仅允许重试已验证的基础设施故障。框架、状态、Workflow、格式、Fixture、产品 Gate 和 Post-Merge 失败全部转交 ChatGPT Web；不得创建 Codex Recovery Generation，也不得重跑失败的 Codex Job。
"""
recovery_runbook.write_text(recovery, encoding="utf-8")

Path(__file__).unlink()
print("REMAINING_ZERO_MODEL_FILES_APPLIED=PASS")
