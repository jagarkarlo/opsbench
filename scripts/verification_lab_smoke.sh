#!/usr/bin/env bash
set -euo pipefail

modes="healthy|missing_collection|routing_mismatch|invalid_notification|unavailable"
mode="${1:-healthy}"
report_path="${2:-}"
case "$mode" in
    healthy|missing_collection|routing_mismatch|invalid_notification|unavailable) ;;
    *) echo "usage: $0 [$modes] [report-path]" >&2; exit 2 ;;
esac

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
lab="$root/deploy/verification"
project="opsbench-verification-smoke-$$"
compose=(docker compose -p "$project" -f "$lab/docker-compose.yml")
overlay="$lab/docker-compose.${mode//_/-}.yml"
if [[ -f "$overlay" ]]; then
    compose+=(-f "$overlay")
fi
if [[ -x "$root/.venv/bin/opsbench" ]]; then
    opsbench_command="$root/.venv/bin/opsbench"
else
    opsbench_command="opsbench"
fi
work_dir="$(mktemp -d)"
cleanup() {
    if ! "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1; then
        echo "cleanup failed; remove manually: docker compose -p $project down -v" >&2
    fi
    rm -rf "$work_dir"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
# Non-interactive: a background run must not stop on terminal reads (SIGTTIN) and skip cleanup.
exec </dev/null

"${compose[@]}" up -d --wait
if [[ "$mode" == "unavailable" ]]; then
    "${compose[@]}" stop test-service
fi

python3 "$root/scripts/verification_lab_observe.py" "$mode" "$work_dir/input.json" "${compose[@]}"

keep_report=1
if [[ -z "$report_path" ]]; then
    report_path="$work_dir/report.json"
    keep_report=0
fi
status=0
"$opsbench_command" verify monitoring-path "$work_dir/input.json" "$report_path" >/dev/null || status=$?
# Exit code 3 is a failed verification outcome, which the failure modes expect.
if [[ "$status" != 0 && "$status" != 3 ]]; then
    echo "opsbench verify exited with $status" >&2
    exit "$status"
fi

"${compose[@]}" down -v --remove-orphans >/dev/null
label="label=com.docker.compose.project=$project"
leftovers="$(docker ps -aq --filter "$label"; docker volume ls -q --filter "$label"; docker network ls -q --filter "$label")"
if [[ -n "$leftovers" ]]; then
    echo "cleanup left Docker resources for $project" >&2
    exit 1
fi
echo "verification lab $mode passed; cleanup verified"
if [[ "$keep_report" == 1 ]]; then
    echo "verification report written to $report_path"
fi
