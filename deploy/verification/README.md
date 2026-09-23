# Disposable Monitoring Verification Lab

This directory contains a local-only Prometheus, Alertmanager, synthetic metric
source, and test receiver. It is a verification fixture, not a production
monitoring deployment and does not require credentials or external paging.

## Prerequisites

- Docker Engine with Compose v2 (Docker Desktop with WSL integration works)
- Free local ports `8090`, `9090`, and `9093`; runs cannot execute concurrently

Start the healthy path manually:

```bash
cd deploy/verification
docker compose up -d
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:9090/-/ready
curl http://127.0.0.1:8090/events
```

Run the bounded smoke test instead. It starts an isolated Compose project,
observes each stage through the real component APIs, writes a verification
report, and removes the project, then verifies no containers, volumes, or
networks remain. Cleanup also runs on SIGINT or SIGTERM:

```bash
scripts/verification_lab_smoke.sh [mode] [report-path]
```

Each failure mode swaps one real component config through a Compose overlay
(`docker-compose.<mode>.yml`) instead of faking a result:

| Mode | Broken component | Expected stages |
|---|---|---|
| `healthy` | none | all `passed` |
| `missing_collection` | Prometheus scrapes the wrong port | `signal_collected` failed |
| `routing_mismatch` | Alertmanager matcher routes to a null receiver | `route_matched` failed |
| `invalid_notification` | rule summary the receiver rejects (HTTP 422) | `receiver_accepted` failed |
| `unavailable` | test service stopped after startup | `signal_emitted` unknown |

A stage that does not pass marks later stages `not_tested`. A stage without
conclusive evidence by the deadline (`OPSBENCH_LAB_DEADLINE_SECONDS`, default
60) is `unknown`, never a guessed failure. The harness fails if a mode's stage
statuses differ from the table. No mode sends external notifications.

The receiver stores only bounded synthetic JSON events in the Compose volume.
Compare a failed run with a corrected rerun:

```bash
opsbench verify compare BASELINE.json RERUN.json OUTPUT.json
```

The comparison contains only scenario and verification IDs, outcomes,
coverage, and per-stage status transitions; no evidence references,
credentials, or host paths.

Runtime status: all five modes and SIGINT/SIGTERM cancellation cleanup were
validated live on Docker 28.3.2.
