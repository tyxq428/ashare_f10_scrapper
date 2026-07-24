from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

BASE_BEFORE_HTTP_CHANGE = "05f6ee833e8623d6f918375f4af484db75cdcd8f"
ROOT = Path('.')
COMMENTS = Path('/tmp/issue61-comments.json')
CHANNELS = ROOT / '.devflow/notification-channels.yaml'
CHANNEL_VALIDATOR = ROOT / 'scripts/devflow/validate_notification_channels.py'
WORKFLOW_TEST = ROOT / 'tests/test_devflow_bark_workflow.py'
REPORT = ROOT / 'docs/process/BARK_HTTP_ALL_STATUS_RETEST_REPORT.md'
LIVE_WORKFLOW = ROOT / '.github/workflows/devflow-bark-all-status-http-retest.yml'
ACTIVATION = ROOT / '.devflow/bark-all-status-http-retest-activation.json'


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
    candidates = []
    for item in values:
        if not isinstance(item, dict):
            continue
        body = item.get('body')
        if isinstance(body, str) and '[BARK][ALL_STATUS_HTTP_RETEST]' in body:
            candidates.append(body)
    if len(candidates) != 1:
        raise SystemExit(f'HTTP_RETEST_RESULT_COMMENT_COUNT={len(candidates)}')
    body = candidates[0]

    def capture(pattern: str, label: str) -> str:
        match = re.search(pattern, body)
        if not match:
            raise SystemExit(f'MISSING_HTTP_RETEST_FIELD:{label}')
        return match.group(1)

    run_id = int(capture(r'/actions/runs/([1-9][0-9]*)', 'run_id'))
    expected = int(capture(r'Expected requests:\s*`([0-9]+)`', 'expected_requests'))
    actual = int(capture(r'Actual requests:\s*`([0-9]+)`', 'actual_requests'))
    delivered = capture(r'All delivered:\s*`(true|false)`', 'all_delivered') == 'true'

    statuses = [
        'COMPLETED',
        'INTERRUPTED',
        'HUMAN_REQUIRED',
        'SECURITY_BLOCKED',
    ]
    rows: list[dict[str, object]] = []
    for status in statuses:
        pattern = (
            rf"\| `{status}` \| (.*?) \| `([^`]+)` \| "
            rf"`([^`]+)` \| `([^`]+)` \|"
        )
        match = re.search(pattern, body)
        if not match:
            raise SystemExit(f'MISSING_HTTP_RETEST_ROW:{status}')
        title, delivery_status, curl_raw, http_raw = match.groups()
        if f'[{status}]' not in title:
            raise SystemExit(f'HTTP_RETEST_TITLE_MISSING_STATUS:{status}')
        curl_value = None if curl_raw in {'None', 'null'} else int(curl_raw)
        http_value = None if http_raw in {'None', 'null'} else int(http_raw)
        rows.append(
            {
                'status': status,
                'title': title,
                'delivery_status': delivery_status,
                'curl_exit_code': curl_value,
                'http_status': http_value,
            }
        )

    if expected != 4 or actual not in {0, 4}:
        raise SystemExit('HTTP_RETEST_REQUEST_COUNT_INVALID')
    if delivered:
        if actual != 4:
            raise SystemExit('DELIVERED_HTTP_RETEST_MUST_HAVE_FOUR_REQUESTS')
        if not all(
            row['delivery_status'] == 'DELIVERED'
            and row['curl_exit_code'] == 0
            and isinstance(row['http_status'], int)
            and 200 <= int(row['http_status']) <= 299
            for row in rows
        ):
            raise SystemExit('HTTP_RETEST_DELIVERED_MATRIX_INVALID')

    return {
        'schema_version': 1,
        'run_id': run_id,
        'expected_requests': expected,
        'actual_requests': actual,
        'all_delivered': delivered,
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

# Remove the one-time Workflow and activation after an observable safe result.
for path in (LIVE_WORKFLOW, ACTIVATION):
    if path.exists():
        path.unlink()

# Keep permanent HTTP/HTTPS transport policy, remove only the one-time retest section.
manifest = json.loads(CHANNELS.read_text(encoding='utf-8'))
manifest.pop('one_time_http_retest', None)
bark = manifest['channels']['bark']
bark['allowed_protocols'] = ['http', 'https']
bark['http_transport_scope'] = 'trusted_network_or_private_tunnel_only'
CHANNELS.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)

# Rebuild the permanent validator from the exact pre-change version, then retain only
# the production HTTP/HTTPS policy. This removes every temporary retest allowance.
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
    'validator_expected_bark',
)
validator = replace_once(
    validator,
    '        "--proto \'=https\'",\n'
    '        "--tlsv1.2",\n',
    '        "--proto \'=http,https\'",\n',
    'validator_protocol',
)
CHANNEL_VALIDATOR.write_text(validator, encoding='utf-8')

# Rebuild the permanent Workflow regression from the exact pre-change version and
# retain only the production protocol assertions plus the permanent status titles.
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

status = 'PASS' if result['all_delivered'] else 'FAIL'
lines = [
    '# Bark HTTP/HTTPS 四状态真实重测报告',
    '',
    '## 执行状态',
    '',
    '```yaml',
    f"status: {status}",
    f"run_id: {result['run_id']}",
    f"expected_requests: {result['expected_requests']}",
    f"actual_requests: {result['actual_requests']}",
    f"all_delivered: {str(result['all_delivered']).lower()}",
    'allowed_protocols:',
    '  - http',
    '  - https',
    'automatic_retries: 0',
    '```',
    '',
    '## 状态矩阵',
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
        '## 安全边界',
        '',
        '- 自动重试：`0`；',
        '- 未保存响应正文或响应头；',
        '- 未保存 Endpoint、原始 curl 错误或 Secret 值；',
        '- 一次性 Workflow 和 Activation 已在本清理变更中移除；',
        '- 生产 Transport 仅允许 `http` 与 `https`；',
        '- 明文 HTTP 仅适用于可信私网或加密隧道。',
        '',
    ]
)
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text('\n'.join(lines), encoding='utf-8')

# Remove the deterministic preparer and its branch-local trigger from the final tree.
for temporary in (
    ROOT / 'scripts/devflow/prepare_bark_http_retest_cleanup.py',
    ROOT / '.github/workflows/temporary-cleanup-bark-http-retest.yml',
):
    if temporary.exists():
        temporary.unlink()

Path('/tmp/bark-http-retest-result.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)
