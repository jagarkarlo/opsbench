#!/usr/bin/env bash
set -euo pipefail

mode="${1:-healthy}"
report_path="${2:-}"
case "$mode" in
  healthy|missing_collection|invalid_notification) ;;
    *) echo "usage: $0 [healthy|missing_collection|invalid_notification] [report-path]" >&2; exit 2 ;;
esac

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
lab="$root/deploy/verification"
project="opsbench-verification-smoke-$$"
compose=(docker compose -p "$project" -f "$lab/docker-compose.yml")
if [[ -x "$root/.venv/bin/opsbench" ]]; then
    opsbench_command="$root/.venv/bin/opsbench"
else
    opsbench_command="opsbench"
fi
temporary_input="$(mktemp)"
cleanup() {
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
    rm -f "$temporary_input"
}
trap cleanup EXIT

OPSBENCH_SIGNAL_MODE="$mode" "${compose[@]}" up -d --wait

python - "$mode" "$temporary_input" <<'PY'
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

mode = sys.argv[1]
input_path = Path(sys.argv[2])

def fetch(url, method="GET", body=None):
    request = urllib.request.Request(url, method=method, data=body)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()

if mode == "invalid_notification":
    payload = json.dumps({"alerts": [{"annotations": {"summary": "invalid"}}]}).encode()
    status, _body = fetch("http://127.0.0.1:8090/alerts", "POST", payload)
    if status != 422:
        raise SystemExit(f"expected invalid notification status 422, got {status}")
    print("verification lab invalid_notification passed")
    raise SystemExit(0)

deadline = time.time() + 30
events = []
prometheus_result = []
prometheus_alerts = []
alertmanager_alerts = []
while time.time() < deadline:
    status, body = fetch("http://127.0.0.1:8090/events")
    if status == 200:
        events = json.loads(body).get("events", [])
    status, body = fetch("http://127.0.0.1:9090/api/v1/query?query=opsbench_verification_signal")
    if status == 200:
        prometheus_result = json.loads(body).get("data", {}).get("result", [])
    status, body = fetch("http://127.0.0.1:9090/api/v1/alerts")
    if status == 200:
        prometheus_alerts = json.loads(body).get("data", {}).get("alerts", [])
    status, body = fetch("http://127.0.0.1:9093/api/v2/alerts")
    if status == 200:
        alertmanager_alerts = json.loads(body)
    if mode == "healthy" and events:
        break
    if mode == "missing_collection" and not prometheus_result and not prometheus_alerts:
        break
    time.sleep(1)

healthy = mode == "healthy"
observations = [
    {
        "stage_id": "signal_emitted",
        "status": "passed",
        "observed_at": None,
        "evidence_refs": ["test-service/health"],
        "summary": "Synthetic test service was healthy.",
    },
    {
        "stage_id": "signal_collected",
        "status": "passed" if prometheus_result else "failed",
        "observed_at": None,
        "evidence_refs": ["prometheus/query/opsbench_verification_signal"],
        "summary": "Prometheus returned the synthetic signal." if prometheus_result else "Prometheus returned no synthetic signal.",
    },
    {
        "stage_id": "rule_fired",
        "status": "passed" if any(alert.get("state") == "firing" for alert in prometheus_alerts) else "failed",
        "observed_at": None,
        "evidence_refs": ["prometheus/alerts/opsbench-verification"],
        "summary": "Prometheus evaluated the verification rule." if prometheus_alerts else "Prometheus did not fire the verification rule.",
    },
    {
        "stage_id": "route_matched",
        "status": "passed" if alertmanager_alerts else "not_tested",
        "observed_at": None,
        "evidence_refs": ["alertmanager/api/v2/alerts"] if alertmanager_alerts else [],
        "summary": "Alertmanager exposed the routed alert." if alertmanager_alerts else "No alert reached Alertmanager.",
    },
    {
        "stage_id": "receiver_accepted",
        "status": "passed" if events else "not_tested",
        "observed_at": None,
        "evidence_refs": ["receiver/events"] if events else [],
        "summary": "The test receiver accepted the alert." if events else "The test receiver received no alert.",
    },
]
input_path.write_text(json.dumps({
    "schema_version": "1.0",
    "verification_id": f"verification-lab-{mode}",
    "scenario_id": "monitoring-path-lab",
    "started_at": "2026-09-09T00:00:00Z",
    "assertions": [
        {"assertion_id": f"assert-{observation['stage_id']}", "stage_id": observation["stage_id"], "description": f"{observation['stage_id']} is verified."}
        for observation in observations
    ],
    "observations": observations,
}, sort_keys=True), encoding="utf-8")
print(f"verification input written to {input_path}")
PY

if [[ -z "$report_path" ]]; then
  report_path="$(mktemp)"
  remove_report=1
else
  remove_report=0
fi
"$opsbench_command" verify monitoring-path "$temporary_input" "$report_path"
if [[ "$remove_report" == 1 ]]; then
  rm -f "$report_path"
else
  echo "verification report written to $report_path"
fi
