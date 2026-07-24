from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

BASE_BEFORE_HTTP_CHANGE = "05f6ee833e8623d6f918375f4af484db75cdcd8f"
ROOT = Path('.')
COMMENTS = Path('/tmp/issue61-comments.json')
CHANNELS = ROOT / '.devflow/notification-channels.yaml'
INCIDENT = ROOT / '.github/workflows/devflow-incident.yml'
CHANNEL_VALIDATOR = ROOT / 'scripts/devflow/validate_notification_channels.py'
WORKFLOW_VALIDATOR = ROOT / 'scripts/devflow/validate_workflows.py'
WORKFLOW_TEST = ROOT / 'tests/test_devflow_bark_workflow.py'
POLICY = ROOT / 'docs/process/DEVFLOW_NOTIFICATION_POLICY.md'
REPORT = ROOT / 'docs/process/BARK_HTTP_ALL_STATUS_RETEST_REPORT.md'
SOURCE_MAIN_SHA = os.environ['SOURCE_MAIN_SHA']
FINALIZER_RUN_ID = int(os.environ['FINALIZER_RUN_ID'])


def git_show(path: str) -> str:
    return subprocess.run(
        ['git', 'show', f'{BASE_BEFORE_HTTP_CHANGE}:{path}'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'REPLACE_COUNT_MISMATCH:{label}:{count}:{old[:100]!r}')
    return text.replace(old, new, 1)


def parse_result() -> dict[str, object]:
    values = json.loads(COMMENTS.read_text(encoding='utf-8'))
    if not isinstance(values, list):
        raise SystemExit('ISSUE_COMMENTS_MUST_BE_ARRAY')
    bodies = [
        item.get('body', '')
        for item in values
        if isinstance(item, dict)
        and '[BARK][ALL_STATUS_HTTP_RETEST]' in str(item.get('body', ''))
    ]
    if len(bodies) != 1:
        raise SystemExit(f'HTTP_RETEST_RESULT_COMMENT_COUNT={len(bodies)}')
    body = bodies[0]

    def capture(pattern: str, label: str) -> str:
        match = re.search(pattern, body)
        if not match:
            raise SystemExit(f'MISSING_HTTP_RETEST_FIELD:{label}')
        return match.group(1)

    run_id = int(capture(r'/actions/runs/([1-9][0-9]*)', 'run_id'))
    expected = int(capture(r'Expected requests:\s*`([0-9]+)`', 'expected_requests'))
    actual = int(capture(r'Actual requests:\s*`([0-9]+)`', 'actual_requests'))
    all_delivered = capture(r'All delivered:\s*`(true|false)`', 'all_delivered') == 'true'
    statuses = [
        'COMPLETED',
        'INTERRUPTED',
        'HUMAN_REQUIRED',
        'SECURITY_BLOCKED',
    ]
    rows: list[dict[str, object]] = []
    for status in statuses:
        match = re.search(
            rf"\| `{status}` \| (.*?) \| `([^`]+)` \| `([^`]+)` \| `([^`]+)` \|",
            body,
        )
        if not match:
            raise SystemExit(f'MISSING_HTTP_RETEST_ROW:{status}')
        title, delivery, curl_raw, http_raw = match.groups()
        if f'[{status}]' not in title:
            raise SystemExit(f'TITLE_STATUS_MISSING:{status}')
        curl_code = None if curl_raw in {'None', 'null'} else int(curl_raw)
        http_status = None if http_raw in {'None', 'null'} else int(http_raw)
        rows.append(
            {
                'status': status,
                'title': title,
                'delivery_status': delivery,
                'curl_exit_code': curl_code,
                'http_status': http_status,
            }
        )

    if expected != 4 or actual not in {0, 4}:
        raise SystemExit('HTTP_RETEST_REQUEST_COUNT_INVALID')
    if all_delivered:
        valid = all(
            row['delivery_status'] == 'DELIVERED'
            and row['curl_exit_code'] == 0
            and isinstance(row['http_status'], int)
            and 200 <= int(row['http_status']) <= 299
            for row in rows
        )
        if actual != 4 or not valid:
            raise SystemExit('HTTP_RETEST_SUCCESS_MATRIX_INVALID')

    return {
        'schema_version': 1,
        'run_id': run_id,
        'expected_requests': expected,
        'actual_requests': actual,
        'all_delivered': all_delivered,
        'allowed_protocols': ['http', 'https'],
        'automatic_retries': 0,
        'response_body_stored': False,
        'response_headers_stored': False,
        'endpoint_stored': False,
        'raw_error_stored': False,
        'secret_value_stored': False,
        'results': rows,
    }


result = parse_result()

# Remove all known one-time and branch-local surfaces. This is intentionally
# idempotent so it also repairs an interrupted earlier cleanup.
for relative in (
    '.github/workflows/devflow-bark-all-status-http-retest.yml',
    '.devflow/bark-all-status-http-retest-activation.json',
    '.github/workflows/temporary-prepare-bark-http-retest.yml',
    '.github/workflows/temporary-cleanup-bark-http-retest.yml',
    '.github/workflows/temporary-finalize-bark-http-retest-v2.yml',
    'scripts/devflow/prepare_bark_http_retest.py',
    'scripts/devflow/prepare_bark_http_retest_v2.py',
    'scripts/devflow/prepare_bark_http_retest_cleanup.py',
    'scripts/devflow/finalize_bark_http_retest_v2.py',
):
    path = ROOT / relative
    if path.exists():
        path.unlink()

# Rebuild the permanent manifest from the exact pre-change source and add only
# the reviewed HTTP/HTTPS production boundary.
manifest = json.loads(git_show('.devflow/notification-channels.yaml'))
bark = manifest['channels']['bark']
bark['allowed_protocols'] = ['http', 'https']
bark['http_transport_scope'] = 'trusted_network_or_private_tunnel_only'
CHANNELS.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)

# Ensure the production Transport is HTTP/HTTPS-only, with no TLS-only flag.
incident = INCIDENT.read_text(encoding='utf-8')
https_only = "              --proto '=https' \\\n              --tlsv1.2 \\\n"
http_https = "              --proto '=http,https' \\\n"
if https_only in incident:
    incident = replace_once(incident, https_only, http_https, 'incident_protocol')
elif http_https not in incident or '--tlsv1.2' in incident:
    raise SystemExit('INCIDENT_PROTOCOL_STATE_INVALID')
if 'BARK_ALLOWED_PROTOCOLS=HTTP_HTTPS' not in incident:
    incident = replace_once(
        incident,
        '          echo "BARK_ENDPOINT_DIAGNOSTICS_PRINTED=0" >> "$GITHUB_STEP_SUMMARY"\n',
        '          echo "BARK_ENDPOINT_DIAGNOSTICS_PRINTED=0" >> "$GITHUB_STEP_SUMMARY"\n'
        '          echo "BARK_ALLOWED_PROTOCOLS=HTTP_HTTPS" >> "$GITHUB_STEP_SUMMARY"\n',
        'incident_summary',
    )
INCIDENT.write_text(incident, encoding='utf-8')

# Rebuild the permanent notification validator with no one-time allowances.
validator = git_show('scripts/devflow/validate_notification_channels.py')
validator = replace_once(
    validator,
    '        "failure_changes_task_state": False,\n'
    '    }\n'
    '    for key, expected in expected_bark.items():\n',
    '        "failure_changes_task_state": False,\n'
    '        "allowed_protocols": ["http", "https"],\n'
    '        "http_transport_scope": "trusted_network_or_private_tunnel_only",\n'
    '    }\n'
    '    for key, expected in expected_bark.items():\n',
    'validator_bark_policy',
)
validator = replace_once(
    validator,
    '        "--proto \'=https\'",\n'
    '        "--tlsv1.2",\n',
    '        "--proto \'=http,https\'",\n',
    'validator_protocol',
)
CHANNEL_VALIDATOR.write_text(validator, encoding='utf-8')

# Keep the global Workflow validator aligned with the production boundary.
workflow_validator = WORKFLOW_VALIDATOR.read_text(encoding='utf-8')
if "--proto '=http,https'" not in workflow_validator:
    workflow_validator = replace_once(
        workflow_validator,
        '            "--retry 0",\n'
        '            "--output /dev/null",\n',
        '            "--retry 0",\n'
        '            "--proto \'=http,https\'",\n'
        '            "--output /dev/null",\n',
        'workflow_validator_protocol',
    )
WORKFLOW_VALIDATOR.write_text(workflow_validator, encoding='utf-8')

# Rebuild the permanent regression file and retain only production protocol tests.
test_text = git_show('tests/test_devflow_bark_workflow.py')
test_text = replace_once(
    test_text,
    '    assert "--proto \'=https\'" in text\n'
    '    assert "--tlsv1.2" in text\n',
    '    assert "--proto \'=http,https\'" in text\n'
    '    assert "--tlsv1.2" not in text\n',
    'workflow_test_protocol',
)
WORKFLOW_TEST.write_text(test_text, encoding='utf-8')

policy_text = POLICY.read_text(encoding='utf-8')
section = '## Bark HTTP/HTTPS transport boundary'
if section not in policy_text:
    policy_text = policy_text.rstrip() + '''\n\n## Bark HTTP/HTTPS transport boundary\n\nBark Transport permits only `http` and `https`. Plain HTTP is acceptable only on a trusted private network or an encrypted tunnel; public Internet transport should use HTTPS. The full endpoint remains an Environment Secret and is never printed, copied into an Artifact, or included in an Issue.\n'''
POLICY.write_text(policy_text.rstrip() + '\n', encoding='utf-8')

status = 'PASS' if result['all_delivered'] else 'FAIL'
lines = [
    '# Bark HTTP/HTTPS 四状态真实重测报告',
    '',
    '## 前序状态确认',
    '',
    '- 前序 preliminary Run `30106305192` 已结束；',
    '- 前序 recovery Run `30106850649` 已结束；',
    '- PR #66 已清理旧一次性测试面；',
    '- 用户暂停聊天输出不代表存在后台任务；',
    '- 本次修改开始前开放实现 PR 数量为 `0`。',
    '',
    '## 执行结果',
    '',
    '```yaml',
    f'status: {status}',
    f"source_run_id: {result['run_id']}",
    f"expected_requests: {result['expected_requests']}",
    f"actual_requests: {result['actual_requests']}",
    f"all_delivered: {str(result['all_delivered']).lower()}",
    'allowed_protocols:',
    '  - http',
    '  - https',
    'automatic_retries: 0',
    f'closeout_source_main_sha: {SOURCE_MAIN_SHA}',
    f'closeout_finalizer_run_id: {FINALIZER_RUN_ID}',
    '```',
    '',
    '## 四状态矩阵',
    '',
    '| 状态 | 标题 | 投递 | curl | HTTP |',
    '|---|---|---|---:|---:|',
]
for row in result['results']:
    lines.append(
        f"| `{row['status']}` | {row['title']} | "
        f"`{row['delivery_status']}` | `{row['curl_exit_code']}` | "
        f"`{row['http_status']}` |"
    )
lines.extend(
    [
        '',
        '## 最终安全状态',
        '',
        '- 一次性 Workflow、Activation 和 preparer 已移除；',
        '- 生产 Bark Transport 只允许 `http` 与 `https`；',
        '- `--retry 0` 保持不变；',
        '- 未保存响应正文、响应头、Endpoint、原始错误或 Secret；',
        '- 明文 HTTP 仅适用于可信私网或加密隧道；',
        '- Codex Policy 保持 disabled。',
        '',
    ]
)
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text('\n'.join(lines), encoding='utf-8')

Path('/tmp/bark-http-final-result.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)
