from __future__ import annotations

import json
from pathlib import Path

INCIDENT = Path(".github/workflows/devflow-incident.yml")
MANIFEST = Path(".devflow/notification-channels.yaml")
RETEST = Path(".github/workflows/bark-all-status-live-retest-v2.yml")
RECEIPT = Path("scripts/devflow/bark_delivery_result.py")
CHANNEL_VALIDATOR = Path("scripts/devflow/validate_notification_channels.py")
WORKFLOW_VALIDATOR = Path("scripts/devflow/validate_workflows.py")
WORKFLOW_TEST = Path("tests/test_devflow_bark_workflow.py")
RECEIPT_TEST = Path("tests/test_devflow_bark_delivery_result.py")
POLICY = Path("docs/process/policies/notification-policy.md")
RUNBOOK = Path("docs/process/runbooks/handle-incident.md")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"REPLACE_COUNT_MISMATCH:{path}:{count}:{old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1. Production Incident: permit only explicit HTTP or HTTPS, condition TLS for HTTPS,
# normalize one trailing slash, keep one attempt and no endpoint diagnostics.
old_incident = r'''          set -uo pipefail
          set +x
          DELIVERY_STATUS="SKIPPED_MISSING_CONFIGURATION"
          REQUEST_INITIATED="false"
          REQUEST_ATTEMPTS="0"
          CURL_EXIT_CODE="null"
          HTTP_STATUS="null"

          if [[ -n "${BARK_PUSH_URL:-}" ]]; then
            echo "::add-mask::${BARK_PUSH_URL}"
            REQUEST_INITIATED="true"
            REQUEST_ATTEMPTS="1"
            HTTP_STATUS_RAW="$(curl \
              --silent \
              --fail \
              --retry 0 \
              --proto '=https' \
              --tlsv1.2 \
              --connect-timeout 10 \
              --max-time 20 \
              --request POST \
              --header 'Content-Type: application/json; charset=utf-8' \
              --data-binary @/tmp/bark-message.json \
              --output /dev/null \
              --write-out '%{http_code}' \
              "$BARK_PUSH_URL")"
            CURL_RC=$?
            CURL_EXIT_CODE="$CURL_RC"
            if [[ "$HTTP_STATUS_RAW" =~ ^[1-5][0-9][0-9]$ ]]; then
              HTTP_STATUS="$((10#$HTTP_STATUS_RAW))"
            fi
            if [[ "$CURL_RC" -eq 0 && "$HTTP_STATUS_RAW" =~ ^2[0-9][0-9]$ ]]; then
              DELIVERY_STATUS="DELIVERED"
            else
              DELIVERY_STATUS="FAILED"
            fi
          fi
'''
new_incident = r'''          set -uo pipefail
          set +x
          DELIVERY_STATUS="SKIPPED_MISSING_CONFIGURATION"
          REQUEST_INITIATED="false"
          REQUEST_ATTEMPTS="0"
          CURL_EXIT_CODE="null"
          HTTP_STATUS="null"

          BARK_ENDPOINT="${BARK_PUSH_URL:-}"
          BARK_ENDPOINT="${BARK_ENDPOINT%/}"
          CURL_PROTOCOL_ARGS=(--proto '=http,https')
          if [[ -n "${BARK_PUSH_URL:-}" ]]; then
            echo "::add-mask::${BARK_PUSH_URL}"
          fi
          if [[ -n "$BARK_ENDPOINT" ]]; then
            echo "::add-mask::${BARK_ENDPOINT}"
          fi

          if [[ -z "$BARK_ENDPOINT" ]]; then
            DELIVERY_STATUS="SKIPPED_MISSING_CONFIGURATION"
          elif [[ "$BARK_ENDPOINT" != http://* && "$BARK_ENDPOINT" != https://* ]]; then
            DELIVERY_STATUS="SKIPPED_INVALID_CONFIGURATION"
          else
            if [[ "$BARK_ENDPOINT" == https://* ]]; then
              CURL_PROTOCOL_ARGS+=(--tlsv1.2)
            fi
            REQUEST_INITIATED="true"
            REQUEST_ATTEMPTS="1"
            set +e
            HTTP_STATUS_RAW="$(curl \
              --silent \
              --fail \
              --retry 0 \
              "${CURL_PROTOCOL_ARGS[@]}" \
              --connect-timeout 10 \
              --max-time 20 \
              --request POST \
              --header 'Content-Type: application/json; charset=utf-8' \
              --data-binary @/tmp/bark-message.json \
              --output /dev/null \
              --write-out '%{http_code}' \
              --url "$BARK_ENDPOINT")"
            CURL_RC=$?
            set -e
            CURL_EXIT_CODE="$CURL_RC"
            if [[ "$HTTP_STATUS_RAW" =~ ^[1-5][0-9][0-9]$ ]]; then
              HTTP_STATUS="$((10#$HTTP_STATUS_RAW))"
            fi
            if [[ "$CURL_RC" -eq 0 && "$HTTP_STATUS_RAW" =~ ^2[0-9][0-9]$ ]]; then
              DELIVERY_STATUS="DELIVERED"
            else
              DELIVERY_STATUS="FAILED"
            fi
          fi
'''
replace_once(INCIDENT, old_incident, new_incident)

# 2. Receipt schema: add a secret-safe zero-request invalid-configuration state.
replace_once(
    RECEIPT,
    '''ALLOWED_DELIVERY_STATUSES = {
    "DELIVERED",
    "FAILED",
    "SKIPPED_MISSING_CONFIGURATION",
}
''',
    '''ALLOWED_DELIVERY_STATUSES = {
    "DELIVERED",
    "FAILED",
    "SKIPPED_MISSING_CONFIGURATION",
    "SKIPPED_INVALID_CONFIGURATION",
}
''',
)
replace_once(
    RECEIPT,
    '''    else:
        if request_initiated or request_attempts != 0:
            raise BarkDeliveryResultError(
                "SKIPPED_MISSING_CONFIGURATION requires zero requests"
            )
        if curl_exit_code is not None or http_status is not None:
            raise BarkDeliveryResultError(
                "SKIPPED_MISSING_CONFIGURATION cannot contain transport status"
            )
''',
    '''    elif delivery_status in {
        "SKIPPED_MISSING_CONFIGURATION",
        "SKIPPED_INVALID_CONFIGURATION",
    }:
        if request_initiated or request_attempts != 0:
            raise BarkDeliveryResultError(
                f"{delivery_status} requires zero requests"
            )
        if curl_exit_code is not None or http_status is not None:
            raise BarkDeliveryResultError(
                f"{delivery_status} cannot contain transport status"
            )
''',
)

# 3. Machine-readable policy, including one reviewed live retest generation.
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
bark = manifest["channels"]["bark"]
bark["allowed_schemes"] = ["http", "https"]
bark["https_minimum_tls"] = "1.2"
bark["http_transport_is_unencrypted"] = True
manifest["one_time_live_retest"] = {
    "test_id": "bark-all-status-live-retest-v3-http-20260724",
    "workflow": ".github/workflows/bark-all-status-live-retest-v2.yml",
    "issue_number": 61,
    "reservation_marker": (
        "bark-all-status-live-retest-v3-http-reservation:20260724"
    ),
    "result_marker": "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]",
    "statuses": [
        "COMPLETED",
        "INTERRUPTED",
        "HUMAN_REQUIRED",
        "SECURITY_BLOCKED",
    ],
    "expected_requests": 4,
    "allowed_schemes": ["http", "https"],
    "run_attempt_must_equal": 1,
    "automatic_retry": False,
    "response_body_stored": False,
    "response_headers_stored": False,
    "endpoint_stored": False,
    "raw_error_stored": False,
    "secret_value_stored": False,
}
MANIFEST.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

# 4. Fresh all-status retest. Existing v2 markers cannot suppress this v3 generation.
retest_text = r'''name: Bark All-Status Live Retest v3 HTTP or HTTPS

on:
  issues:
    types:
      - assigned

permissions:
  contents: read
  issues: write

concurrency:
  group: bark-all-status-live-retest-v3-http
  cancel-in-progress: false

jobs:
  live-retest:
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

      - name: Reserve the HTTP-or-HTTPS retest exactly once
        id: reserve
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          RESERVATION_MARKER='bark-all-status-live-retest-v3-http-reservation:20260724'
          RESULT_MARKER='[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]'
          gh api --paginate \
            "repos/${{ github.repository }}/issues/61/comments?per_page=100" \
            --jq '.[].body' > /tmp/bark-retest-existing-comments.txt
          if grep -Fq -- "$RESERVATION_MARKER" /tmp/bark-retest-existing-comments.txt || \
             grep -Fq -- "$RESULT_MARKER" /tmp/bark-retest-existing-comments.txt; then
            echo "should_run=false" >> "$GITHUB_OUTPUT"
            echo "BARK_ALL_STATUS_RETEST_V3_HTTP=ALREADY_RESERVED_OR_COMPLETED" \
              >> "$GITHUB_STEP_SUMMARY"
            exit 0
          fi
          cat > /tmp/bark-retest-reservation.md <<EOF
          [BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP_RESERVED]

          - Run: https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}
          - Expected real requests: 4
          - Allowed schemes: http, https
          - Automatic retries: 0
          - JSON POST target: normalized base device-key URL

          <!-- ${RESERVATION_MARKER} -->
          EOF
          gh issue comment 61 --repo "${{ github.repository }}" \
            --body-file /tmp/bark-retest-reservation.md
          echo "should_run=true" >> "$GITHUB_OUTPUT"

      - name: Build four status-labelled Bark messages
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
          repository = os.environ['REPOSITORY_VALUE']
          run_id = int(os.environ['RUN_ID_VALUE'])
          target_url = f'https://github.com/{repository}/actions/runs/{run_id}'
          output_dir = Path('/tmp/bark-all-status-live-retest-v3/messages')
          output_dir.mkdir(parents=True, exist_ok=True)
          for status in statuses:
              validated = {
                  'task_id': 'bark-all-status-live-retest-v3-http',
                  'notification_type': status,
                  'reason_code': f'SIMULATED_{status}',
                  'reason': (
                      'Owner-authorized real Bark transport retest over the '
                      f'configured HTTP-or-HTTPS endpoint for terminal status {status}.'
                  ),
                  'minimum_action': 'No action is required; this is a live retest.',
                  'source_workflow': 'Bark All-Status Live Retest v3 HTTP or HTTPS',
                  'source_run_id': run_id,
                  'target_url': target_url,
              }
              message = render_bark_message(
                  validated,
                  repository=repository,
                  group='ashare-f10-devflow-live-retest-v3',
              )
              if f'[{status}]' not in message['title']:
                  raise SystemExit(f'BARK_TITLE_MISSING_STATUS:{status}')
              (output_dir / f'{status}.json').write_text(
                  json.dumps(message, ensure_ascii=False, indent=2) + '\n',
                  encoding='utf-8',
              )
          print('BARK_ALL_STATUS_RETEST_V3_MESSAGES=4')
          PY

      - name: Send one real JSON POST for each supported status
        id: live_retest
        if: steps.reserve.outputs.should_run == 'true'
        shell: bash
        env:
          BARK_PUSH_URL: ${{ secrets.BARK_PUSH_URL }}
        run: |
          set -uo pipefail
          set +x
          ROOT=/tmp/bark-all-status-live-retest-v3
          RESULTS_JSONL="${ROOT}/results.jsonl"
          RESULT_JSON="${ROOT}/result.json"
          mkdir -p "$ROOT"
          : > "$RESULTS_JSONL"
          STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)

          CONFIG_STATUS="MISSING"
          BARK_ENDPOINT="${BARK_PUSH_URL:-}"
          BARK_ENDPOINT="${BARK_ENDPOINT%/}"
          CURL_PROTOCOL_ARGS=(--proto '=http,https')
          if [[ -n "${BARK_PUSH_URL:-}" ]]; then
            echo "::add-mask::${BARK_PUSH_URL}"
          fi
          if [[ -n "$BARK_ENDPOINT" ]]; then
            echo "::add-mask::${BARK_ENDPOINT}"
          fi
          if [[ "$BARK_ENDPOINT" == http://* ]]; then
            CONFIG_STATUS="VALID_HTTP"
          elif [[ "$BARK_ENDPOINT" == https://* ]]; then
            CONFIG_STATUS="VALID_HTTPS"
            CURL_PROTOCOL_ARGS+=(--tlsv1.2)
          elif [[ -n "$BARK_ENDPOINT" ]]; then
            CONFIG_STATUS="INVALID_SCHEME"
          fi

          for STATUS in "${STATUSES[@]}"; do
            MESSAGE="${ROOT}/messages/${STATUS}.json"
            TITLE="$(jq -r '.title' "$MESSAGE")"
            if [[ "$CONFIG_STATUS" == VALID_* ]]; then
              set +e
              HTTP_STATUS_RAW="$(curl \
                --silent \
                --retry 0 \
                "${CURL_PROTOCOL_ARGS[@]}" \
                --connect-timeout 10 \
                --max-time 20 \
                --request POST \
                --header 'Content-Type: application/json; charset=utf-8' \
                --data-binary "@${MESSAGE}" \
                --output /dev/null \
                --write-out '%{http_code}' \
                --url "$BARK_ENDPOINT")"
              CURL_RC=$?
              set -e
              REQUEST_INITIATED=true
              REQUEST_ATTEMPTS=1
            else
              CURL_RC=0
              HTTP_STATUS_RAW=0
              REQUEST_INITIATED=false
              REQUEST_ATTEMPTS=0
            fi
            python - \
              "$STATUS" "$TITLE" "$CONFIG_STATUS" "$REQUEST_INITIATED" \
              "$REQUEST_ATTEMPTS" "$CURL_RC" "$HTTP_STATUS_RAW" \
              "$RESULTS_JSONL" <<'PY'
          import json
          import sys
          from pathlib import Path

          (
              status,
              title,
              config_status,
              initiated_raw,
              attempts_raw,
              curl_raw,
              http_raw,
              output,
          ) = sys.argv[1:]
          initiated = initiated_raw == 'true'
          attempts = int(attempts_raw)
          curl_exit = int(curl_raw)
          http_status = int(http_raw) if http_raw.isdigit() else None
          delivered = (
              initiated
              and curl_exit == 0
              and http_status is not None
              and 200 <= http_status <= 299
          )
          if delivered:
              delivery_status = 'DELIVERED'
          elif not initiated:
              delivery_status = (
                  'SKIPPED_MISSING_CONFIGURATION'
                  if config_status == 'MISSING'
                  else 'SKIPPED_INVALID_CONFIGURATION'
              )
          else:
              delivery_status = 'FAILED'
          value = {
              'status': status,
              'title': title,
              'configuration_status': config_status,
              'delivery_status': delivery_status,
              'request_initiated': initiated,
              'request_attempts': attempts,
              'curl_exit_code': curl_exit if initiated else None,
              'http_status': http_status if initiated else None,
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
              'test_id': 'bark-all-status-live-retest-v3-http-20260724',
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

          jq -r '.results[] | "BARK_RETEST_V3=\(.status) title=\(.title) config=\(.configuration_status) delivery=\(.delivery_status) curl=\(.curl_exit_code // \"null\") http=\(.http_status // \"null\")"' \
            "$RESULT_JSON" >> "$GITHUB_STEP_SUMMARY"
          echo "EXPECTED_REAL_BARK_REQUESTS=4" >> "$GITHUB_STEP_SUMMARY"
          echo "ACTUAL_REAL_BARK_REQUESTS=$(jq -r '.actual_requests' "$RESULT_JSON")" \
            >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_ALLOWED_SCHEMES=http,https" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_AUTOMATIC_RETRIES=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_RESPONSE_BODY_STORED=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_RESPONSE_HEADERS_STORED=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_ENDPOINT_STORED=0" >> "$GITHUB_STEP_SUMMARY"
          echo "BARK_SECRET_VALUE_STORED=0" >> "$GITHUB_STEP_SUMMARY"

      - name: Upload the safe aggregate retest result
        if: steps.reserve.outputs.should_run == 'true' && always()
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: bark-all-status-live-retest-v3-${{ github.run_id }}
          path: /tmp/bark-all-status-live-retest-v3/result.json
          if-no-files-found: error
          retention-days: 14
          compression-level: 0

      - name: Record the safe retest matrix in Issue 61
        if: steps.reserve.outputs.should_run == 'true' && always()
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          REPOSITORY_VALUE: ${{ github.repository }}
          RUN_ID_VALUE: ${{ github.run_id }}
        run: |
          set -euo pipefail
          RESULT=/tmp/bark-all-status-live-retest-v3/result.json
          if [[ ! -f "$RESULT" ]]; then
            echo "BARK_ALL_STATUS_RETEST_V3_RESULT=UNAVAILABLE" >> "$GITHUB_STEP_SUMMARY"
            exit 0
          fi
          python - <<'PY'
          import json
          import os
          from pathlib import Path

          value = json.loads(
              Path('/tmp/bark-all-status-live-retest-v3/result.json').read_text(
                  encoding='utf-8'
              )
          )
          repository = os.environ['REPOSITORY_VALUE']
          run_id = os.environ['RUN_ID_VALUE']
          lines = [
              '[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]',
              '',
              f'- Run: https://github.com/{repository}/actions/runs/{run_id}',
              f"- Expected requests: `{value['expected_requests']}`",
              f"- Actual requests: `{value['actual_requests']}`",
              f"- All delivered: `{str(value['all_delivered']).lower()}`",
              '',
              '| Status | Title | Config | Delivery | curl | HTTP |',
              '|---|---|---|---|---:|---:|',
          ]
          for item in value['results']:
              lines.append(
                  f"| `{item['status']}` | {item['title']} | "
                  f"`{item['configuration_status']}` | "
                  f"`{item['delivery_status']}` | "
                  f"`{item['curl_exit_code']}` | `{item['http_status']}` |"
              )
          lines.extend(
              (
                  '',
                  '- Allowed schemes: `http`, `https`',
                  '- Automatic retries: `0`',
                  '- Response body/headers stored: `false`',
                  '- Endpoint/raw error/Secret stored: `false`',
              )
          )
          Path('/tmp/bark-all-status-live-retest-v3-comment.md').write_text(
              '\n'.join(lines) + '\n',
              encoding='utf-8',
          )
          PY
          gh issue comment 61 --repo "${{ github.repository }}" \
            --body-file /tmp/bark-all-status-live-retest-v3-comment.md

      - name: Require all four HTTP-or-HTTPS requests to be accepted
        if: steps.reserve.outputs.should_run == 'true'
        shell: bash
        run: |
          set -euo pipefail
          python - <<'PY'
          import json
          from pathlib import Path

          value = json.loads(
              Path('/tmp/bark-all-status-live-retest-v3/result.json').read_text(
                  encoding='utf-8'
              )
          )
          assert value['expected_requests'] == 4
          assert value['actual_requests'] == 4
          assert value['all_delivered'] is True
          for item in value['results']:
              assert f"[{item['status']}]" in item['title']
              assert item['configuration_status'] in {'VALID_HTTP', 'VALID_HTTPS'}
              assert item['request_attempts'] == 1
              assert item['automatic_retry'] is False
          PY
          echo "BARK_ALL_STATUS_LIVE_RETEST_V3_HTTP=DELIVERED" \
            >> "$GITHUB_STEP_SUMMARY"
'''
RETEST.write_text(retest_text, encoding="utf-8")

# 5. Channel validator: permanent HTTP/HTTPS contract plus one reviewed test workflow.
replace_once(
    CHANNEL_VALIDATOR,
    'AUTO_RECOVERY = WORKFLOW_ROOT / "devflow-auto-recovery.yml"\n',
    'AUTO_RECOVERY = WORKFLOW_ROOT / "devflow-auto-recovery.yml"\n'
    'LIVE_RETEST = WORKFLOW_ROOT / "bark-all-status-live-retest-v2.yml"\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '''        "maximum_requests_per_notification": 1,
        "failure_changes_task_state": False,
''',
    '''        "maximum_requests_per_notification": 1,
        "failure_changes_task_state": False,
        "allowed_schemes": ["http", "https"],
        "https_minimum_tls": "1.2",
        "http_transport_is_unencrypted": True,
''',
)
live_manifest_validation = r'''
    live_retest = manifest.get("one_time_live_retest")
    expected_live_retest = {
        "test_id": "bark-all-status-live-retest-v3-http-20260724",
        "workflow": LIVE_RETEST.as_posix(),
        "issue_number": 61,
        "reservation_marker": (
            "bark-all-status-live-retest-v3-http-reservation:20260724"
        ),
        "result_marker": "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]",
        "statuses": expected_types,
        "expected_requests": 4,
        "allowed_schemes": ["http", "https"],
        "run_attempt_must_equal": 1,
        "automatic_retry": False,
        "response_body_stored": False,
        "response_headers_stored": False,
        "endpoint_stored": False,
        "raw_error_stored": False,
        "secret_value_stored": False,
    }
    if live_retest != expected_live_retest:
        errors.append("one-time Bark HTTP/HTTPS live-retest policy mismatch")

'''
replace_once(
    CHANNEL_VALIDATOR,
    '    workflow_text: dict[Path, str] = {}\n',
    live_manifest_validation + '    workflow_text: dict[Path, str] = {}\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '''    if environment_users != [INCIDENT.as_posix()]:
        errors.append(
            "notification-runtime must be referenced only by Devflow Incident: "
            f"{environment_users}"
        )
''',
    '''    expected_environment_users = [
        LIVE_RETEST.as_posix(),
        INCIDENT.as_posix(),
    ]
    if environment_users != expected_environment_users:
        errors.append(
            "notification-runtime may be referenced only by Incident and the "
            "owner-approved HTTP/HTTPS live retest: "
            f"{environment_users}"
        )
''',
)
replace_once(
    CHANNEL_VALIDATOR,
    '''    if secret_users != [INCIDENT.as_posix()]:
        errors.append(
            "BARK_PUSH_URL must be referenced only by Devflow Incident: "
            f"{secret_users}"
        )
''',
    '''    expected_secret_users = [
        LIVE_RETEST.as_posix(),
        INCIDENT.as_posix(),
    ]
    if secret_users != expected_secret_users:
        errors.append(
            "BARK_PUSH_URL may be referenced only by Incident and the "
            "owner-approved HTTP/HTTPS live retest: "
            f"{secret_users}"
        )
''',
)
replace_once(
    CHANNEL_VALIDATOR,
    '''    for path in (INCIDENT, STATE_CONSISTENCY, TERMINAL_PRODUCER):
''',
    '''    for path in (INCIDENT, STATE_CONSISTENCY, TERMINAL_PRODUCER, LIVE_RETEST):
''',
)
replace_once(
    CHANNEL_VALIDATOR,
    '''        "--retry 0",
        "--proto '=https'",
        "--tlsv1.2",
        "--output /dev/null",
''',
    '''        "--retry 0",
        "--proto '=http,https'",
        "BARK_ENDPOINT=\"${BARK_ENDPOINT%/}\"",
        "BARK_ENDPOINT\" != http://*",
        "BARK_ENDPOINT\" != https://*",
        "CURL_PROTOCOL_ARGS+=(--tlsv1.2)",
        "SKIPPED_INVALID_CONFIGURATION",
        "--output /dev/null",
''',
)
live_workflow_validation = r'''
    live_retest_text = workflow_text.get(LIVE_RETEST, "")
    required_live_retest = (
        "issues:",
        "      - assigned",
        "github.event.issue.number == 61",
        "github.event.assignee.login == 'tyxq428'",
        "github.run_attempt == 1",
        "name: notification-runtime",
        "${{ secrets.BARK_PUSH_URL }}",
        "bark-all-status-live-retest-v3-http-reservation:20260724",
        "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]",
        "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)",
        "render_bark_message",
        "BARK_TITLE_MISSING_STATUS",
        "--retry 0",
        "--proto '=http,https'",
        "VALID_HTTP",
        "VALID_HTTPS",
        "CURL_PROTOCOL_ARGS+=(--tlsv1.2)",
        "--output /dev/null",
        "EXPECTED_REAL_BARK_REQUESTS=4",
        "BARK_ALL_STATUS_LIVE_RETEST_V3_HTTP=DELIVERED",
        "gh issue comment 61",
        UPLOAD_ARTIFACT_REF,
        "bark-all-status-live-retest-v3-${{ github.run_id }}",
        "retention-days: 14",
        "compression-level: 0",
    )
    for fragment in required_live_retest:
        if fragment not in live_retest_text:
            errors.append(f"Bark HTTP/HTTPS live retest missing guard: {fragment}")
    if live_retest_text.count("--request POST") != 1:
        errors.append("Bark HTTP/HTTPS live retest must contain exactly one POST loop")
    if live_retest_text.count("actions/upload-artifact@") != 1:
        errors.append("Bark HTTP/HTTPS live retest must upload exactly one result Artifact")
    for forbidden in (
        "repository_dispatch:",
        "workflow_run:",
        "agent-runtime",
        "secrets.AGENT_",
        "openai/codex-action@",
        "private_responses_forwarder.py",
        "relay_health.py",
        "--show-error",
        "--proto '=https'",
    ):
        if forbidden in live_retest_text:
            errors.append(
                f"Bark HTTP/HTTPS live retest contains forbidden path: {forbidden}"
            )

'''
replace_once(
    CHANNEL_VALIDATOR,
    '    comment_text = (\n',
    live_workflow_validation + '    comment_text = (\n',
)
replace_once(
    CHANNEL_VALIDATOR,
    '''        "automatic_bark_retries": 0 if not errors else None,
        "errors": errors,
''',
    '''        "automatic_bark_retries": 0 if not errors else None,
        "allowed_bark_schemes": bark.get("allowed_schemes"),
        "one_time_live_retest": live_retest,
        "errors": errors,
''',
)

# 6. General workflow validator.
replace_once(
    WORKFLOW_VALIDATOR,
    '''WORKFLOW_TARGETS = (
    "codex-task.yml",
''',
    '''WORKFLOW_TARGETS = (
    "bark-all-status-live-retest-v2.yml",
    "codex-task.yml",
''',
)
replace_once(
    WORKFLOW_VALIDATOR,
    '''            "--retry 0",
            "--output /dev/null",
''',
    '''            "--retry 0",
            "--proto '=http,https'",
            "CURL_PROTOCOL_ARGS+=(--tlsv1.2)",
            "SKIPPED_INVALID_CONFIGURATION",
            "--output /dev/null",
''',
)
live_validator_func = r'''


def _validate_bark_http_live_retest(
    path: Path,
    text: str,
    errors: list[str],
) -> None:
    _require_fragments(
        path,
        text,
        (
            "issues:",
            "      - assigned",
            "github.event.issue.number == 61",
            "github.event.assignee.login == 'tyxq428'",
            "github.run_attempt == 1",
            "name: notification-runtime",
            "${{ secrets.BARK_PUSH_URL }}",
            "bark-all-status-live-retest-v3-http-reservation:20260724",
            "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]",
            "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)",
            "--proto '=http,https'",
            "VALID_HTTP",
            "VALID_HTTPS",
            "CURL_PROTOCOL_ARGS+=(--tlsv1.2)",
            "--retry 0",
            "--output /dev/null",
            "EXPECTED_REAL_BARK_REQUESTS=4",
            "BARK_ALL_STATUS_LIVE_RETEST_V3_HTTP=DELIVERED",
        ),
        errors,
    )
    _forbid(
        path,
        text,
        (
            "workflow_run:",
            "repository_dispatch:",
            "agent-runtime",
            "secrets.AGENT_",
            "openai/codex-action@",
            "private_responses_forwarder.py",
            "relay_health.py",
            "--show-error",
            "--proto '=https'",
        ),
        errors,
        message="Bark HTTP/HTTPS live retest contains a forbidden path",
    )
    if text.count("--request POST") != 1:
        errors.append(f"{path}: exactly one bounded POST loop is allowed")

'''
replace_once(
    WORKFLOW_VALIDATOR,
    '\ndef _validate_post_merge(path: Path, text: str, errors: list[str]) -> None:\n',
    live_validator_func
    + '\ndef _validate_post_merge(path: Path, text: str, errors: list[str]) -> None:\n',
)
replace_once(
    WORKFLOW_VALIDATOR,
    '''    validators = {
        "codex-task.yml": _validate_codex_task,
''',
    '''    validators = {
        "bark-all-status-live-retest-v2.yml": _validate_bark_http_live_retest,
        "codex-task.yml": _validate_codex_task,
''',
)

# 7. Regression tests.
replace_once(
    WORKFLOW_TEST,
    '''TERMINAL_PRODUCER = ROOT / ".github/workflows/devflow-terminal-state-notify.yml"
RECEIPT_COMMENT = DEVFLOW / "bark_delivery_receipt_comment.py"
''',
    '''TERMINAL_PRODUCER = ROOT / ".github/workflows/devflow-terminal-state-notify.yml"
LIVE_RETEST = ROOT / ".github/workflows/bark-all-status-live-retest-v2.yml"
RECEIPT_COMMENT = DEVFLOW / "bark_delivery_receipt_comment.py"
''',
)
replace_once(
    WORKFLOW_TEST,
    '''    assert "--proto '=https'" in text
    assert "--tlsv1.2" in text
''',
    '''    assert "--proto '=http,https'" in text
    assert "CURL_PROTOCOL_ARGS+=(--tlsv1.2)" in text
    assert "BARK_ENDPOINT=\"${BARK_ENDPOINT%/}\"" in text
    assert "SKIPPED_INVALID_CONFIGURATION" in text
''',
)
live_test_case = r'''


def test_owner_approved_http_or_https_all_status_retest_is_bounded() -> None:
    text = LIVE_RETEST.read_text(encoding="utf-8")
    assert "bark-all-status-live-retest-v3-http-reservation:20260724" in text
    assert "[BARK][ALL_STATUS_LIVE_RETEST_V3_HTTP]" in text
    assert "STATUSES=(COMPLETED INTERRUPTED HUMAN_REQUIRED SECURITY_BLOCKED)" in text
    assert "github.run_attempt == 1" in text
    assert "--proto '=http,https'" in text
    assert "VALID_HTTP" in text
    assert "VALID_HTTPS" in text
    assert "CURL_PROTOCOL_ARGS+=(--tlsv1.2)" in text
    assert "--retry 0" in text
    assert text.count("--request POST") == 1
    assert "EXPECTED_REAL_BARK_REQUESTS=4" in text
    assert "BARK_ALL_STATUS_LIVE_RETEST_V3_HTTP=DELIVERED" in text
    assert "--show-error" not in text
    assert "agent-runtime" not in text
    assert "openai/codex-action@" not in text

'''
replace_once(
    WORKFLOW_TEST,
    '\ndef test_auto_recovery_binds_terminal_events_without_retrying_bark() -> None:\n',
    live_test_case
    + '\ndef test_auto_recovery_binds_terminal_events_without_retrying_bark() -> None:\n',
)
replace_once(
    WORKFLOW_TEST,
    '''    assert summary["automatic_bark_retries"] == 0
''',
    '''    assert summary["automatic_bark_retries"] == 0
    assert summary["allowed_bark_schemes"] == ["http", "https"]
    assert summary["one_time_live_retest"]["expected_requests"] == 4
''',
)

receipt_test_addition = r'''


def test_invalid_configuration_receipt_records_zero_requests() -> None:
    value = _build(
        delivery_status="SKIPPED_INVALID_CONFIGURATION",
        request_initiated=False,
        request_attempts=0,
        curl_exit_code=None,
        http_status=None,
    )
    assert value["delivery_status"] == "SKIPPED_INVALID_CONFIGURATION"
    assert value["request_initiated"] is False
    assert value["request_attempts"] == 0

'''
replace_once(
    RECEIPT_TEST,
    '\n@pytest.mark.parametrize(\n',
    receipt_test_addition + '\n@pytest.mark.parametrize(\n',
)

# 8. Policies and runbook.
replace_once(
    POLICY,
    '''- Bark完整推送URL只存放在Environment Secret，不得出现在仓库、Issue、PR、日志或Artifact；
- 只有 `Devflow Incident` 可以引用该Environment和Secret；
- Bark Job从可信 `main` 重新验证payload并生成裁剪后的JSON；
''',
    '''- Bark完整推送URL只存放在Environment Secret，不得出现在仓库、Issue、PR、日志或Artifact；
- 生产Bark Transport只允许显式 `http` 或 `https` scheme，其他scheme在请求前以 `SKIPPED_INVALID_CONFIGURATION` 拒绝；
- HTTPS至少使用TLS 1.2；HTTP不提供传输加密，仅适用于用户明确接受该风险的自托管链路；
- 基础URL可以有或没有末尾 `/`；Workflow会去除一个末尾 `/`，并直接向device-key基础URL发送JSON POST，不拼接消息路径；
- 只有 `Devflow Incident` 可以引用该Environment和Secret；受审的一次性真实Transport测试可在独立Workflow中临时引用，测试后必须删除；
- Bark Job从可信 `main` 重新验证payload并生成裁剪后的JSON；
''',
)
replace_once(
    POLICY,
    '''- `DELIVERED / FAILED / SKIPPED_MISSING_CONFIGURATION`；
''',
    '''- `DELIVERED / FAILED / SKIPPED_MISSING_CONFIGURATION / SKIPPED_INVALID_CONFIGURATION`；
''',
)
replace_once(
    POLICY,
    '''SKIPPED_MISSING_CONFIGURATION:
  request_initiated: false
  request_attempts: 0
```
''',
    '''SKIPPED_MISSING_CONFIGURATION:
  request_initiated: false
  request_attempts: 0

SKIPPED_INVALID_CONFIGURATION:
  request_initiated: false
  request_attempts: 0
```
''',
)
replace_once(
    RUNBOOK,
    '''   - `SKIPPED_MISSING_CONFIGURATION`：未发起请求，检查 `notification-runtime` 配置；
''',
    '''   - `SKIPPED_MISSING_CONFIGURATION`：未发起请求，检查 `notification-runtime` 配置；
   - `SKIPPED_INVALID_CONFIGURATION`：未发起请求，scheme不是允许的 `http` 或 `https`；
''',
)
replace_once(
    RUNBOOK,
    '''- 不要把 `BARK_PUSH_URL` 粘贴到聊天、Issue或日志；
''',
    '''- 不要把 `BARK_PUSH_URL` 粘贴到聊天、Issue或日志；
- 自托管Bark可以使用完整 `http://IP:port/device-key` 或 `https://.../device-key` 基础URL；Workflow直接JSON POST到该基础URL并去除一个末尾 `/`；
- HTTP链路未加密；经公网发送时优先使用HTTPS或先建立加密隧道；
''',
)

# Ensure all edited text files end with exactly one newline.
for path in (
    INCIDENT,
    RETEST,
    RECEIPT,
    CHANNEL_VALIDATOR,
    WORKFLOW_VALIDATOR,
    WORKFLOW_TEST,
    RECEIPT_TEST,
    POLICY,
    RUNBOOK,
):
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")

print("BARK_HTTP_TRANSPORT_PATCH=PREPARED")
