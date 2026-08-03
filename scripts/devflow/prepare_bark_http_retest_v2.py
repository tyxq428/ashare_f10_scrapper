from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('.')
INCIDENT = ROOT / '.github/workflows/devflow-incident.yml'
CHANNELS = ROOT / '.devflow/notification-channels.yaml'
CHANNEL_VALIDATOR = ROOT / 'scripts/devflow/validate_notification_channels.py'
WORKFLOW_VALIDATOR = ROOT / 'scripts/devflow/validate_workflows.py'
WORKFLOW_TEST = ROOT / 'tests/test_devflow_bark_workflow.py'
POLICY = ROOT / 'docs/process/DEVFLOW_NOTIFICATION_POLICY.md'
LIVE_WORKFLOW = ROOT / '.github/workflows/devflow-bark-all-status-http-retest.yml'
ACTIVATION = ROOT / '.devflow/bark-all-status-http-retest-activation.json'


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'REPLACE_COUNT_MISMATCH:{path}:{count}:{old[:80]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


# Production transport: allow only HTTP or HTTPS. Other schemes remain blocked.
replace_once(
    INCIDENT,
    "              --proto '=https' \\\n              --tlsv1.2 \\\n",
    "              --proto '=http,https' \\\n",
)
replace_once(
    INCIDENT,
    '          echo "BARK_ENDPOINT_DIAGNOSTICS_PRINTED=0" >> "$GITHUB_STEP_SUMMARY"\n',
    '          echo "BARK_ENDPOINT_DIAGNOSTICS_PRINTED=0" >> "$GITHUB_STEP_SUMMARY"\n'
    '          echo "BARK_ALLOWED_PROTOCOLS=HTTP_HTTPS" >> "$GITHUB_STEP_SUMMARY"\n',
)

# Permanent manifest records the explicit protocol boundary; one-time retest is temporary.
manifest = json.loads(CHANNELS.read_text(encoding='utf-8'))
bark = manifest['channels']['bark']
bark['allowed_protocols'] = ['http', 'https']
bark['http_transport_scope'] = 'trusted_network_or_private_tunnel_only'
manifest['one_time_http_retest'] = {
    'activation_id': 'bark-all-status-http-retest-v1-20260724',
    'workflow': '.github/workflows/devflow-bark-all-status-http-retest.yml',
    'activation_file': '.devflow/bark-all-status-http-retest-activation.json',
    'issue_number': 61,
    'statuses': [
        'COMPLETED',
        'INTERRUPTED',
        'HUMAN_REQUIRED',
        'SECURITY_BLOCKED',
    ],
    'expected_requests': 4,
    'run_attempt_must_equal': 1,
    'automatic_retry': False,
    'allowed_protocols': ['http', 'https'],
    'response_body_stored': False,
    'response_headers_stored': False,
    'endpoint_stored': False,
    'raw_error_stored': False,
    'secret_value_stored': False,
}
CHANNELS.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)

activation = {
    'schema_version': 1,
    'activation_id': 'bark-all-status-http-retest-v1-20260724',
    'approved_by': 'tyxq428',
    'issue_number': 61,
    'active': True,
    'statuses': [
        'COMPLETED',
        'INTERRUPTED',
        'HUMAN_REQUIRED',
        'SECURITY_BLOCKED',
    ],
    'expected_requests': 4,
    'automatic_retry': False,
    'allowed_protocols': ['http', 'https'],
}
ACTIVATION.write_text(
    json.dumps(activation, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)

# Update permanent validator and add tightly bounded temporary retest validation.
replace_once(
    CHANNEL_VALIDATOR,
    'AUTO_RECOVERY = WORKFLOW_ROOT / "devflow-auto-recovery.yml"\n',
    'AUTO_RECOVERY = WORKFLOW_ROOT / "devflow-auto-recovery.yml"\n'
    'LIVE_HTTP_RETEST = WORKFLOW_ROOT / "devflow-bark-all-status-http-retest.yml"\n'
    'LIVE_HTTP_ACTIVATION = Path(\n'
    '    ".devflow/bark-all-status-http-retest-activation.json"\n'
    ')\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '        "failure_changes_task_state": False,\n'
    '    }\n'
    '    for key, expected in expected_bark.items():\n',
    '        "failure_changes_task_state": False,\n'
    '        "allowed_protocols": ["http", "https"],\n'
    '        "http_transport_scope": "trusted_network_or_private_tunnel_only",\n'
    '    }\n'
    '    for key, expected in expected_bark.items():\n',
)

live_validation = '''\n    live_test = manifest.get("one_time_http_retest")\n    expected_live_test = {\n        "activation_id": "bark-all-status-http-retest-v1-20260724",\n        "workflow": LIVE_HTTP_RETEST.as_posix(),\n        "activation_file": LIVE_HTTP_ACTIVATION.as_posix(),\n        "issue_number": 61,\n        "statuses": expected_types,\n        "expected_requests": 4,\n        "run_attempt_must_equal": 1,\n        "automatic_retry": False,\n        "allowed_protocols": ["http", "https"],\n        "response_body_stored": False,\n        "response_headers_stored": False,\n        "endpoint_stored": False,\n        "raw_error_stored": False,\n        "secret_value_stored": False,\n    }\n    if live_test != expected_live_test:\n        errors.append("one-time Bark HTTP retest policy mismatch")\n\n    try:\n        live_activation = _load_object(LIVE_HTTP_ACTIVATION)\n    except ValueError as exc:\n        errors.append(str(exc))\n        live_activation = {}\n    expected_live_activation = {\n        "schema_version": 1,\n        "activation_id": "bark-all-status-http-retest-v1-20260724",\n        "approved_by": "tyxq428",\n        "issue_number": 61,\n        "active": True,\n        "statuses": expected_types,\n        "expected_requests": 4,\n        "automatic_retry": False,\n        "allowed_protocols": ["http", "https"],\n    }\n    if live_activation != expected_live_activation:\n        errors.append("one-time Bark HTTP retest activation mismatch")\n\n'''
replace_once(
    CHANNEL_VALIDATOR,
    '    workflow_text: dict[Path, str] = {}\n',
    live_validation + '    workflow_text: dict[Path, str] = {}\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '    if environment_users != [INCIDENT.as_posix()]:\n'
    '        errors.append(\n'
    '            "notification-runtime must be referenced only by Devflow Incident: "\n'
    '            f"{environment_users}"\n'
    '        )\n',
    '    expected_environment_users = sorted(\n'
    '        [INCIDENT.as_posix(), LIVE_HTTP_RETEST.as_posix()]\n'
    '    )\n'
    '    if environment_users != expected_environment_users:\n'
    '        errors.append(\n'
    '            "notification-runtime may be referenced only by Incident and the "\n'
    '            "owner-approved HTTP retest: "\n'
    '            f"{environment_users}"\n'
    '        )\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '    if secret_users != [INCIDENT.as_posix()]:\n'
    '        errors.append(\n'
    '            "BARK_PUSH_URL must be referenced only by Devflow Incident: "\n'
    '            f"{secret_users}"\n'
    '        )\n',
    '    expected_secret_users = sorted(\n'
    '        [INCIDENT.as_posix(), LIVE_HTTP_RETEST.as_posix()]\n'
    '    )\n'
    '    if secret_users != expected_secret_users:\n'
    '        errors.append(\n'
    '            "BARK_PUSH_URL may be referenced only by Incident and the "\n'
    '            "owner-approved HTTP retest: "\n'
    '            f"{secret_users}"\n'
    '        )\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '    for path in (INCIDENT, STATE_CONSISTENCY, TERMINAL_PRODUCER):\n',
    '    for path in (\n'
    '        INCIDENT, STATE_CONSISTENCY, TERMINAL_PRODUCER, LIVE_HTTP_RETEST\n'
    '    ):\n',
)
text = CHANNEL_VALIDATOR.read_text(encoding='utf-8')
text = text.replace('        "--proto \'=https\'",\n', '        "--proto \'=http,https\'",\n', 1)
text = text.replace('        "--tlsv1.2",\n', '', 1)
CHANNEL_VALIDATOR.write_text(text, encoding='utf-8')

live_workflow_validation = '''\n    live_text = workflow_text.get(LIVE_HTTP_RETEST, "")\n    for fragment in (\n        "issues:",\n        "      - assigned",\n        "github.event.issue.number == 61",\n        "github.event.assignee.login == 'tyxq428'",\n        "github.run_attempt == 1",\n        "name: notification-runtime",\n        "${{ secrets.BARK_PUSH_URL }}",\n        "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)",\n        "render_bark_message",\n        "BARK_TITLE_MISSING_STATUS",\n        "--retry 0",\n        "--proto '=http,https'",\n        "--output /dev/null",\n        "EXPECTED_REAL_BARK_REQUESTS=4",\n        "ACTUAL_REAL_BARK_REQUESTS=",\n        "BARK_ALL_STATUS_HTTP_RETEST=DELIVERED",\n        "gh issue comment 61",\n        UPLOAD_ARTIFACT_REF,\n        "bark-all-status-http-retest-${{ github.run_id }}",\n        "retention-days: 14",\n        "compression-level: 0",\n    ):\n        if fragment not in live_text:\n            errors.append(f"Bark HTTP retest missing guard: {fragment}")\n    if live_text.count("--request POST") != 1:\n        errors.append("Bark HTTP retest must contain exactly one POST loop")\n    if live_text.count("actions/upload-artifact@") != 1:\n        errors.append("Bark HTTP retest must upload exactly one result Artifact")\n    for forbidden in (\n        "repository_dispatch:",\n        "workflow_run:",\n        "agent-runtime",\n        "secrets.AGENT_",\n        "openai/codex-action@",\n        "private_responses_forwarder.py",\n        "relay_health.py",\n        "--show-error",\n        "--tlsv1.2",\n    ):\n        if forbidden in live_text:\n            errors.append(f"Bark HTTP retest contains forbidden path: {forbidden}")\n\n'''
replace_once(
    CHANNEL_VALIDATOR,
    '    comment_text = (\n',
    live_workflow_validation + '    comment_text = (\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '        "automatic_bark_retries": 0 if not errors else None,\n'
    '        "errors": errors,\n',
    '        "automatic_bark_retries": 0 if not errors else None,\n'
    '        "one_time_http_retest": live_test,\n'
    '        "errors": errors,\n',
)

# General workflow policy records the production protocol guard.
replace_once(
    WORKFLOW_VALIDATOR,
    '            "--retry 0",\n'
    '            "--output /dev/null",\n',
    '            "--retry 0",\n'
    '            "--proto \'=http,https\'",\n'
    '            "--output /dev/null",\n',
)

# Regression tests distinguish the trusted-network HTTP allowance from arbitrary schemes.
replace_once(
    WORKFLOW_TEST,
    '    assert "--proto \'=https\'" in text\n'
    '    assert "--tlsv1.2" in text\n',
    '    assert "--proto \'=http,https\'" in text\n'
    '    assert "--tlsv1.2" not in text\n',
)
replace_once(
    WORKFLOW_TEST,
    'RECEIPT_COMMENT = DEVFLOW / "bark_delivery_receipt_comment.py"\n',
    'RECEIPT_COMMENT = DEVFLOW / "bark_delivery_receipt_comment.py"\n'
    'LIVE_HTTP_RETEST = ROOT / ".github/workflows/devflow-bark-all-status-http-retest.yml"\n',
)
new_test = '''\n\ndef test_owner_approved_http_retest_is_bounded_and_status_labelled() -> None:\n    text = LIVE_HTTP_RETEST.read_text(encoding="utf-8")\n    assert "github.event.issue.number == 61" in text\n    assert "github.event.assignee.login == 'tyxq428'" in text\n    assert "github.run_attempt == 1" in text\n    assert "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)" in text\n    assert "--proto '=http,https'" in text\n    assert "--tlsv1.2" not in text\n    assert "--retry 0" in text\n    assert text.count("--request POST") == 1\n    assert "EXPECTED_REAL_BARK_REQUESTS=4" in text\n    assert "BARK_ALL_STATUS_HTTP_RETEST=DELIVERED" in text\n    assert "BARK_PUSH_URL: ${{ secrets.BARK_PUSH_URL }}" in text\n\n'''
replace_once(
    WORKFLOW_TEST,
    '\ndef test_auto_recovery_binds_terminal_events_without_retrying_bark() -> None:\n',
    new_test + '\ndef test_auto_recovery_binds_terminal_events_without_retrying_bark() -> None:\n',
)
replace_once(
    WORKFLOW_TEST,
    '    assert summary["automatic_bark_retries"] == 0\n',
    '    assert summary["automatic_bark_retries"] == 0\n'
    '    assert summary["one_time_http_retest"]["expected_requests"] == 4\n',
)

if POLICY.exists():
    policy_text = POLICY.read_text(encoding='utf-8')
    marker = '## Bark HTTP/HTTPS transport boundary'
    if marker not in policy_text:
        policy_text = policy_text.rstrip() + '''\n\n## Bark HTTP/HTTPS transport boundary\n\nBark Transport permits only `http` and `https`. Plain HTTP is acceptable only on a trusted private network or an encrypted tunnel; public Internet transport should use HTTPS. The full endpoint remains an Environment Secret and is never printed, copied into an Artifact, or included in an Issue.\n'''
        POLICY.write_text(policy_text + '\n', encoding='utf-8')

LIVE_WORKFLOW.write_text(r'''name: Bark All-Status HTTP Retest

on:
  issues:
    types:
      - assigned

permissions:
  contents: read
  issues: write

concurrency:
  group: bark-all-status-http-retest-v1
  cancel-in-progress: false

jobs:
  live-test:
    if: >-
      github.event.issue.number == 61 &&
      github.event.assignee.login == 'tyxq428' &&
      github.run_attempt == 1
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
      issues: write
    environment:
      name: notification-runtime
      deployment: false
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09
        with:
          ref: main
          persist-credentials: false

      - name: Reserve this owner-approved HTTP retest exactly once
        id: reserve
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          RESERVATION_MARKER='bark-all-status-http-retest-reservation:v1-20260724'
          RESULT_MARKER='[BARK][ALL_STATUS_HTTP_RETEST]'
          gh api --paginate \
            "repos/${{ github.repository }}/issues/61/comments?per_page=100" \
            --jq '.[].body' > /tmp/bark-http-retest-existing-comments.txt
          if grep -Fq -- "$RESERVATION_MARKER" \
               /tmp/bark-http-retest-existing-comments.txt || \
             grep -Fq -- "$RESULT_MARKER" \
               /tmp/bark-http-retest-existing-comments.txt; then
            echo "should_run=false" >> "$GITHUB_OUTPUT"
            echo "BARK_HTTP_RETEST=ALREADY_RESERVED_OR_COMPLETED" \
              >> "$GITHUB_STEP_SUMMARY"
            exit 0
          fi
          cat > /tmp/bark-http-retest-reservation.md <<EOF
          [BARK][ALL_STATUS_HTTP_RETEST_RESERVED]

          - Run: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
          - Expected real requests: 4
          - Allowed protocols: http, https
          - Automatic retries: 0

          <!-- ${RESERVATION_MARKER} -->
          EOF
          gh issue comment 61 --repo "${{ github.repository }}" \
            --body-file /tmp/bark-http-retest-reservation.md
          echo "should_run=true" >> "$GITHUB_OUTPUT"
          echo "BARK_HTTP_RETEST=RESERVED" >> "$GITHUB_STEP_SUMMARY"

      - name: Validate activation and build status-labelled messages
        if: steps.reserve.outputs.should_run == 'true'
        shell: bash
        env:
          REPOSITORY_VALUE: ${{ github.repository }}
          RUN_ID_VALUE: ${{ github.run_id }}
        run: |
          set -euo pipefail
          python - <<'PY'
          from __future__ import annotations

          import json
          import os
          import sys
          from pathlib import Path

          sys.path.insert(0, str(Path('scripts/devflow').resolve()))
          from notification_event import render_bark_message

          statuses = [
              'COMPLETED',
              'INTERRUPTED',
              'HUMAN_REQUIRED',
              'SECURITY_BLOCKED',
          ]
          activation = json.loads(
              Path(
                  '.devflow/bark-all-status-http-retest-activation.json'
              ).read_text(encoding='utf-8')
          )
          expected = {
              'schema_version': 1,
              'activation_id': 'bark-all-status-http-retest-v1-20260724',
              'approved_by': 'tyxq428',
              'issue_number': 61,
              'active': True,
              'statuses': statuses,
              'expected_requests': 4,
              'automatic_retry': False,
              'allowed_protocols': ['http', 'https'],
          }
          if activation != expected:
              raise SystemExit('BARK_HTTP_RETEST_ACTIVATION_MISMATCH')

          repository = os.environ['REPOSITORY_VALUE']
          run_id = int(os.environ['RUN_ID_VALUE'])
          target_url = f'https://github.com/{repository}/actions/runs/{run_id}'
          output_dir = Path('/tmp/bark-all-status-http-retest/messages')
          output_dir.mkdir(parents=True, exist_ok=True)
          for status in statuses:
              validated = {
                  'task_id': 'bark-all-status-http-retest-v1',
                  'notification_type': status,
                  'reason_code': f'SIMULATED_{status}',
                  'reason': (
                      'Owner-authorized real Bark transport retest for '
                      f'terminal status {status} over the configured HTTP or HTTPS endpoint.'
                  ),
                  'minimum_action': 'No action is required; this is a live transport retest.',
                  'source_workflow': 'Bark All-Status HTTP Retest',
                  'source_run_id': run_id,
                  'target_url': target_url,
              }
              message = render_bark_message(
                  validated,
                  repository=repository,
                  group='ashare-f10-devflow-http-retest',
              )
              if f'[{status}]' not in message['title']:
                  raise SystemExit(f'BARK_TITLE_MISSING_STATUS:{status}')
              (output_dir / f'{status}.json').write_text(
                  json.dumps(message, ensure_ascii=False, indent=2) + '\n',
                  encoding='utf-8',
              )
          print('BARK_HTTP_RETEST_MESSAGES=4')
          PY

      - name: Send exactly one real Bark request for each supported status
        id: live_test
        if: steps.reserve.outputs.should_run == 'true'
        shell: bash
        env:
          BARK_PUSH_URL: ${{ secrets.BARK_PUSH_URL }}
        run: |
          set -uo pipefail
          set +x
          RESULTS_DIR=/tmp/bark-all-status-http-retest
          RESULTS_JSONL="${RESULTS_DIR}/results.jsonl"
          RESULT_JSON="${RESULTS_DIR}/result.json"
          mkdir -p "$RESULTS_DIR"
          : > "$RESULTS_JSONL"
          STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)

          VALID_PROTOCOL=false
          case "${BARK_PUSH_URL:-}" in
            http://*|https://*) VALID_PROTOCOL=true ;;
          esac
          if [[ "$VALID_PROTOCOL" == "true" ]]; then
            echo "::add-mask::${BARK_PUSH_URL}"
            for STATUS in "${STATUSES[@]}"; do
              MESSAGE="${RESULTS_DIR}/messages/${STATUS}.json"
              TITLE="$(jq -r '.title' "$MESSAGE")"
              set +e
              HTTP_STATUS_RAW="$(curl \
                --silent \
                --retry 0 \
                --proto '=http,https' \
                --connect-timeout 10 \
                --max-time 20 \
                --request POST \
                --header 'Content-Type: application/json; charset=utf-8' \
                --data-binary "@${MESSAGE}" \
                --output /dev/null \
                --write-out '%{http_code}' \
                "$BARK_PUSH_URL")"
              CURL_RC=$?
              set -e
              python - "$STATUS" "$TITLE" "$CURL_RC" "$HTTP_STATUS_RAW" \
                "$RESULTS_JSONL" <<'PY'
          import json
          import sys
          from pathlib import Path

          status, title, curl_raw, http_raw, output = sys.argv[1:]
          curl_exit = int(curl_raw)
          http_status = int(http_raw) if http_raw.isdigit() else None
          delivered = (
              curl_exit == 0
              and http_status is not None
              and 200 <= http_status <= 299
          )
          value = {
              'status': status,
              'title': title,
              'delivery_status': 'DELIVERED' if delivered else 'FAILED',
              'request_initiated': True,
              'request_attempts': 1,
              'curl_exit_code': curl_exit,
              'http_status': http_status,
              'automatic_retry': False,
              'response_body_stored': False,
              'response_headers_stored': False,
              'endpoint_stored': False,
              'raw_error_stored': False,
              'secret_value_stored': False,
          }
          with Path(output).open('a', encoding='utf-8') as handle:
              handle.write(json.dumps(value, ensure_ascii=False) + '\n')
          PY
            done
          else
            for STATUS in "${STATUSES[@]}"; do
              TITLE="$(jq -r '.title' \
                "${RESULTS_DIR}/messages/${STATUS}.json")"
              python - "$STATUS" "$TITLE" "$RESULTS_JSONL" <<'PY'
          import json
          import sys
          from pathlib import Path

          status, title, output = sys.argv[1:]
          value = {
              'status': status,
              'title': title,
              'delivery_status': 'SKIPPED_INVALID_OR_MISSING_PROTOCOL',
              'request_initiated': False,
              'request_attempts': 0,
              'curl_exit_code': None,
              'http_status': None,
              'automatic_retry': False,
              'response_body_stored': False,
              'response_headers_stored': False,
              'endpoint_stored': False,
              'raw_error_stored': False,
              'secret_value_stored': False,
          }
          with Path(output).open('a', encoding='utf-8') as handle:
              handle.write(json.dumps(value, ensure_ascii=False) + '\n')
          PY
            done
          fi

          python - "$RESULTS_JSONL" "$RESULT_JSON" <<'PY'
          import json
          import sys
          from pathlib import Path

          source, output = map(Path, sys.argv[1:])
          results = [
              json.loads(line)
              for line in source.read_text(encoding='utf-8').splitlines()
              if line.strip()
          ]
          expected = [
              'COMPLETED',
              'INTERRUPTED',
              'HUMAN_REQUIRED',
              'SECURITY_BLOCKED',
          ]
          value = {
              'schema_version': 1,
              'activation_id': 'bark-all-status-http-retest-v1-20260724',
              'issue_number': 61,
              'expected_statuses': expected,
              'expected_requests': 4,
              'actual_requests': sum(item['request_attempts'] for item in results),
              'all_delivered': (
                  len(results) == 4
                  and [item['status'] for item in results] == expected
                  and all(item['delivery_status'] == 'DELIVERED' for item in results)
              ),
              'results': results,
          }
          output.write_text(
              json.dumps(value, ensure_ascii=False, indent=2) + '\n',
              encoding='utf-8',
          )
          PY

          jq -r '.results[] | "BARK_HTTP_RETEST=\(.status) title=\(.title) delivery=\(.delivery_status) http=\(.http_status // "null")"' \
            "$RESULT_JSON" >> "$GITHUB_STEP_SUMMARY"
          echo "EXPECTED_REAL_BARK_REQUESTS=4" >> "$GITHUB_STEP_SUMMARY"
          echo "ACTUAL_REAL_BARK_REQUESTS=$(jq -r '.actual_requests' "$RESULT_JSON")" \
            >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_ALLOWED_PROTOCOLS=HTTP_HTTPS" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_AUTOMATIC_RETRIES=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_RESPONSE_BODY_STORED=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_RESPONSE_HEADERS_STORED=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_ENDPOINT_STORED=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_SECRET_VALUE_STORED=0" >> "$GITHUB_STEP_SUMMARY"

      - name: Upload the all-status HTTP retest result
        if: always() && steps.reserve.outputs.should_run == 'true'
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: bark-all-status-http-retest-${{ github.run_id }}
          path: /tmp/bark-all-status-http-retest/result.json
          if-no-files-found: error
          retention-days: 14
          compression-level: 0

      - name: Record the safe HTTP retest result in Issue 61
        if: always() && steps.reserve.outputs.should_run == 'true'
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          REPOSITORY_VALUE: ${{ github.repository }}
          RUN_ID_VALUE: ${{ github.run_id }}
        run: |
          set -euo pipefail
          RESULT=/tmp/bark-all-status-http-retest/result.json
          if [[ ! -f "$RESULT" ]]; then
            echo "BARK_HTTP_RETEST_RESULT=UNAVAILABLE" >> "$GITHUB_STEP_SUMMARY"
            exit 0
          fi
          python - <<'PY'
          import json
          import os
          from pathlib import Path

          value = json.loads(
              Path('/tmp/bark-all-status-http-retest/result.json').read_text(
                  encoding='utf-8'
              )
          )
          repository = os.environ['REPOSITORY_VALUE']
          run_id = os.environ['RUN_ID_VALUE']
          lines = [
              '[BARK][ALL_STATUS_HTTP_RETEST]',
              '',
              f'- Run: https://github.com/{repository}/actions/runs/{run_id}',
              f"- Expected requests: `{value['expected_requests']}`",
              f"- Actual requests: `{value['actual_requests']}`",
              f"- All delivered: `{str(value['all_delivered']).lower()}`",
              '- Allowed protocols: `http`, `https`',
              '',
              '| Status | Title | Delivery | curl | HTTP |',
              '|---|---|---|---:|---:|',
          ]
          for item in value['results']:
              lines.append(
                  f"| `{item['status']}` | {item['title']} | "
                  f"`{item['delivery_status']}` | "
                  f"`{item['curl_exit_code']}` | `{item['http_status']}` |"
              )
          lines.extend(
              (
                  '',
                  '- Automatic retries: `0`',
                  '- Response body/headers stored: `false`',
                  '- Endpoint/raw error/Secret stored: `false`',
              )
          )
          Path('/tmp/bark-all-status-http-retest-comment.md').write_text(
              '\n'.join(lines) + '\n',
              encoding='utf-8',
          )
          PY
          gh issue comment 61 --repo "${{ github.repository }}" \
            --body-file /tmp/bark-all-status-http-retest-comment.md

      - name: Require all four status requests to be accepted
        if: steps.reserve.outputs.should_run == 'true'
        shell: bash
        run: |
          set -euo pipefail
          python - <<'PY'
          import json
          from pathlib import Path

          value = json.loads(
              Path('/tmp/bark-all-status-http-retest/result.json').read_text(
                  encoding='utf-8'
              )
          )
          assert value['expected_requests'] == 4
          assert value['actual_requests'] == 4
          assert value['all_delivered'] is True
          for item in value['results']:
              assert f"[{item['status']}]" in item['title']
              assert item['request_attempts'] == 1
              assert item['automatic_retry'] is False
          PY
          echo "BARK_ALL_STATUS_HTTP_RETEST=DELIVERED" >> "$GITHUB_STEP_SUMMARY"

      - name: Record a safely deduplicated retest
        if: steps.reserve.outputs.should_run == 'false'
        shell: bash
        run: |
          set -euo pipefail
          echo "BARK_HTTP_RETEST_REQUESTS=0_ALREADY_RESERVED_OR_COMPLETED" \
            >> "$GITHUB_STEP_SUMMARY"
''', encoding='utf-8')

for temporary in (
    ROOT / 'scripts/devflow/prepare_bark_http_retest.py',
    ROOT / 'scripts/devflow/prepare_bark_http_retest_v2.py',
    ROOT / '.github/workflows/temporary-prepare-bark-http-retest.yml',
):
    if temporary.exists():
        temporary.unlink()
