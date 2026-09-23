"""Collect live evidence from the disposable verification lab and classify each stage."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request


STAGES = ("signal_emitted", "signal_collected", "rule_fired", "route_matched", "receiver_accepted")
DESCRIPTIONS = {
    "signal_emitted": "The synthetic service exposes the verification signal.",
    "signal_collected": "Prometheus scrapes and stores the verification signal.",
    "rule_fired": "The verification alert rule is firing.",
    "route_matched": "Alertmanager routes the alert to the test receiver.",
    "receiver_accepted": "The test receiver accepts the notification content.",
}
EXPECTED = {
    "healthy": ("passed", "passed", "passed", "passed", "passed"),
    "missing_collection": ("passed", "failed", "not_tested", "not_tested", "not_tested"),
    "routing_mismatch": ("passed", "passed", "passed", "failed", "not_tested"),
    "invalid_notification": ("passed", "passed", "passed", "passed", "failed"),
    "unavailable": ("unknown", "not_tested", "not_tested", "not_tested", "not_tested"),
}
ALERT_NAME = "OpsBenchVerificationSignal"
SCRAPE_JOB = "verification-test-service"
EXPECTED_RECEIVER = "opsbench-test-receiver"
PROMETHEUS = "http://127.0.0.1:9090"
ALERTMANAGER = "http://127.0.0.1:9093"
RECEIVER = "http://127.0.0.1:8090"
FETCH_METRICS = (
    "import urllib.request;"
    "print(urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=2).read().decode())"
)

Evaluation = tuple[str, str, str]


def _emitted(snapshot: dict[str, Any]) -> Evaluation:
    reference = "test-service:/metrics"
    body = snapshot.get("metrics_body")
    if body is None:
        return "unknown", reference, "The signal source could not be reached."
    if any(line.strip() == "opsbench_verification_signal 1" for line in body.splitlines()):
        return "passed", reference, "The signal source exposed opsbench_verification_signal 1."
    return "failed", reference, "The signal source did not expose the verification signal."


def _collected(snapshot: dict[str, Any]) -> Evaluation:
    reference = "prometheus:/api/v1/targets"
    target = snapshot.get("target")
    if target is None:
        return "pending", reference, "Prometheus has not reported the scrape target."
    if target.get("health") == "down":
        detail = target.get("lastError") or "no error detail"
        return "failed", reference, f"Prometheus reports the scrape target down: {detail}."
    if target.get("health") == "up" and "1" in snapshot.get("signal_values", []):
        return "passed", "prometheus:/api/v1/query", "Prometheus stored the verification signal."
    return "pending", reference, "Prometheus has not stored the verification signal."


def _rule(snapshot: dict[str, Any]) -> Evaluation:
    reference = "prometheus:/api/v1/rules"
    state = snapshot.get("rule_state")
    if state == "firing":
        return "passed", reference, f"{ALERT_NAME} is firing."
    if state is None:
        return "pending", reference, f"Prometheus has not loaded {ALERT_NAME}."
    return "pending", reference, f"{ALERT_NAME} is {state}."


def _route(snapshot: dict[str, Any]) -> Evaluation:
    reference = "alertmanager:/api/v2/alerts"
    receivers = snapshot.get("alert_receivers")
    if receivers is None:
        return "pending", reference, "Alertmanager has not received the alert."
    if EXPECTED_RECEIVER in receivers:
        return "passed", reference, f"Alertmanager routed the alert to {EXPECTED_RECEIVER}."
    actual = ", ".join(sorted(receivers)) or "no receiver"
    return "failed", reference, f"Alertmanager routed the alert to {actual}, not {EXPECTED_RECEIVER}."


def _receiver(snapshot: dict[str, Any]) -> Evaluation:
    reference = "receiver:/events"
    if snapshot.get("accepted", 0) > 0:
        return "passed", reference, "The test receiver accepted the notification."
    rejected = snapshot.get("rejected", 0)
    if rejected > 0:
        return "failed", reference, f"The test receiver rejected {rejected} notification(s) with invalid content."
    return "pending", reference, "The test receiver has not received a notification."


EVALUATORS: tuple[Callable[[dict[str, Any]], Evaluation], ...] = (_emitted, _collected, _rule, _route, _receiver)


def classify(snapshot: dict[str, Any], *, final: bool, observed_at: str) -> list[dict[str, Any]] | None:
    """Return stage observations, or None while a stage is still pending before the deadline."""
    observations: list[dict[str, Any]] = []
    blocked = False
    for stage_id, evaluate in zip(STAGES, EVALUATORS):
        if blocked:
            observations.append(_observation(stage_id, "not_tested", None, [], "Not tested because an earlier stage did not pass."))
            continue
        status, reference, summary = evaluate(snapshot)
        if status == "pending":
            if not final:
                return None
            status, summary = "unknown", f"{summary} No conclusive evidence before the deadline."
        timestamp = None if status == "unknown" else observed_at
        observations.append(_observation(stage_id, status, timestamp, [reference], summary))
        blocked = status != "passed"
    return observations


def _observation(stage_id: str, status: str, observed_at: str | None, refs: list[str], summary: str) -> dict[str, Any]:
    return {
        "evidence_refs": refs,
        "observed_at": observed_at,
        "stage_id": stage_id,
        "status": status,
        "summary": summary,
    }


def build_input(mode: str, started_at: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    compact = started_at.replace("-", "").replace(":", "")
    return {
        "assertions": [
            {"assertion_id": f"assert-{stage_id}", "description": DESCRIPTIONS[stage_id], "stage_id": stage_id}
            for stage_id in STAGES
        ],
        "observations": observations,
        "scenario_id": "monitoring-path-lab",
        "schema_version": "1.0",
        "started_at": started_at,
        "verification_id": f"verification-lab-{mode}-{compact}",
    }


def _get_json(url: str) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read())
    except (OSError, ValueError):
        return None


def collect(compose: list[str]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        result = subprocess.run(
            [*compose, "exec", "-T", "test-service", "python", "-c", FETCH_METRICS],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        snapshot["metrics_body"] = result.stdout if result.returncode == 0 else None
    except subprocess.TimeoutExpired:
        snapshot["metrics_body"] = None

    targets = _get_json(f"{PROMETHEUS}/api/v1/targets?state=active") or {}
    for target in targets.get("data", {}).get("activeTargets", []):
        if target.get("labels", {}).get("job") == SCRAPE_JOB and target.get("health") in {"up", "down"}:
            snapshot["target"] = target

    query = urllib.parse.quote("opsbench_verification_signal")
    series = _get_json(f"{PROMETHEUS}/api/v1/query?query={query}") or {}
    snapshot["signal_values"] = [item["value"][1] for item in series.get("data", {}).get("result", [])]

    rules = _get_json(f"{PROMETHEUS}/api/v1/rules?type=alert") or {}
    for group in rules.get("data", {}).get("groups", []):
        for rule in group.get("rules", []):
            if rule.get("name") == ALERT_NAME:
                snapshot["rule_state"] = rule.get("state")

    alert_filter = urllib.parse.quote(f'alertname="{ALERT_NAME}"')
    alerts = _get_json(f"{ALERTMANAGER}/api/v2/alerts?filter={alert_filter}")
    if alerts:
        snapshot["alert_receivers"] = sorted({receiver["name"] for alert in alerts for receiver in alert.get("receivers", [])})

    events = _get_json(f"{RECEIVER}/events") or {}
    snapshot["accepted"] = events.get("count", 0)
    snapshot["rejected"] = events.get("rejected", 0)
    return snapshot


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[1] not in EXPECTED:
        print(f"usage: {argv[0]} MODE INPUT_PATH COMPOSE_COMMAND...", file=sys.stderr)
        return 2
    mode, input_path, compose = argv[1], Path(argv[2]), argv[3:]
    deadline = time.monotonic() + float(os.environ.get("OPSBENCH_LAB_DEADLINE_SECONDS", "60"))
    started_at = _now()
    while True:
        final = time.monotonic() >= deadline
        observations = classify(collect(compose), final=final, observed_at=_now())
        if observations is not None:
            break
        time.sleep(1)
    input_path.write_text(json.dumps(build_input(mode, started_at, observations), sort_keys=True), encoding="utf-8")
    for observation in observations:
        print(f"{observation['stage_id']}: {observation['status']} - {observation['summary']}")
    actual = tuple(observation["status"] for observation in observations)
    if actual != EXPECTED[mode]:
        print(f"unexpected stage statuses for {mode}: expected {EXPECTED[mode]}, got {actual}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
