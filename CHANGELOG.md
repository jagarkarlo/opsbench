# Changelog

All notable changes to this project are documented here. Dates are release
tag dates; versions follow the milestones described in `docs/roadmap.md`.

## v0.6.1 — 2026-09-04 — Phase 5: Reliability Replay and ColdRoute scenario adapters

- Added `ReliabilityReplayAdapter`, `ReliabilityReplayTimeline`, and `ReplayStep`
  for deterministic simulation of multi-step incident timelines and root-cause
  playback.
- Added `ColdRouteAdapter` and `ColdRouteProfile` for evaluating cold-route failover,
  disaster recovery paths, and un-warmed infrastructure procedures.
- Added JSON persistence helpers (`load_replay_timeline`, `write_replay_timeline`,
  `load_cold_routes`, `write_cold_routes`).
- Added `opsbench run replay` CLI command supporting performance baselines,
  failure injection, and OTLP tracing.

## v0.6.0 — 2026-09-04 — Phase 5: Scenario authoring SDK and contribution checks

- Added `ScenarioBuilder` fluent SDK and `scaffold_scenario` factory for
  programmatic and automated creation of valid OpsBench scenario packs.
- Added strict contribution readiness checks via `check_contribution` and
  `check_gallery_contributions`, verifying lint status, naming conventions,
  evidence content depth, evaluator rule validity, reference response
  viability, and secret/credential hygiene.
- Added `opsbench scenario init` to scaffold turnkey scenario packs ready for
  contribution.
- Added `opsbench scenario check` to validate single scenario packs or full
  galleries against contribution standards.

## v0.5.9 — 2026-09-03 — Phase 4: Operations complete

- Added bounded local load and synthetic chaos matrices through
  `run_chaos_matrix` and `opsbench run chaos-matrix`.
- Added deterministic iteration/mode ordering, isolated case outputs, and
  explicit failure accounting with exit status `3`.
- Completed the Phase 4 operations follow-ups without external infrastructure
  actions or a resident scheduler daemon.

Phase 5 begins at `0.6.0`.

## v0.5.8 — 2026-09-03 — Phase 4: Scheduled recovery verification

- Added `run_recovery_schedule_tick` for one cron/systemd-friendly recovery
  invocation without a resident daemon.
- Added append-only JSONL history for verified and failed ticks.
- Added optional local alert artifacts and exit status `3` for failed ticks.
- Added `opsbench store schedule-tick` with explicit attempt and retention
  controls.

## v0.5.7 — 2026-09-03 — Phase 4: Partial-suite performance

- Added resilient performance profiling for suites with expected injected
  failures.
- Added explicit completed, failed, and total scenario counts to performance
  reports.
- Kept failed scenarios out of measured timing aggregates while preserving
  their structured failure records and exit status `3`.

## v0.5.6 — 2026-09-03 — Phase 4: Repeated recovery drills

- Added `run_recovery_drill_series` for repeated verified local backup and
  restore exercises with numbered attempt directories.
- Added bounded retention cleanup that keeps only the newest requested number
  of verified attempts and reports removed attempts.
- Added `opsbench store drill-series` with configurable `--attempts` and
  `--retention` controls.

## v0.5.5 — 2026-09-03 — Phase 4: Resilient suite failure reporting

- Added `execute_suite_resilient`, which preserves successful immutable result
  bundles while recording expected injected failures in deterministic gallery
  order.
- Added suite `--inject-failure` and repeatable `--inject-failure-scenario`
  options. Partial suites emit `completed_with_injected_failures`, include
  structured failure records, and exit with status `3`.
- Prevented combining injected suite failures with performance reporting until
  partial-suite performance semantics are defined.

## v0.5.4 — 2026-09-03 — Phase 4: Safe failure injection

- Added deterministic synthetic `timeout`, `malformed_response`,
  `missing_evidence`, and `adapter_exception` modes for local adapter tests.
- Added optional scenario targeting through `FailureInjection` and
  `FailureInjectingAdapter` without executing proposed actions or touching
  external infrastructure.
- Added `--inject-failure` and repeatable `--inject-failure-scenario` controls
  for single fixture, human, and OpenAI-compatible runs. Expected injected
  exceptions return structured JSON and exit status `3` without writing a
  result bundle.

## v0.5.3 — 2026-09-03 — Phase 4: Recovery drills

- Added `opsbench store drill` to execute a local backup/recovery exercise
  from a result-store database into a fresh SQLite database.
- The drill verifies archive integrity, prevents target-database overwrites,
  restores all bundles, and validates source/restored bundle hashes match.

## v0.5.2 — 2026-09-03 — Phase 4: Performance baselines

- Added dependency-free execution metrics for individual benchmark runs and
  gallery suites, including duration and throughput measurements.
- Added opt-in JSON performance reports through `--performance-output`.
- Added portable JSON baseline creation and comparison through
  `--write-performance-baseline` and `--compare-performance-baseline`.
- Added threshold-based regression detection that exits with status `2` for
  CI-friendly failure signaling while preserving the result JSON output.

## v0.5.1 — 2026-09-02 — Phase 4: Operations follow-up

- Added opt-in OTLP/HTTP trace export for `opsbench run` and `opsbench run
  suite` through `--otlp-endpoint`.
- Completed recorded run and suite spans with precise timestamps, preserving
  parent-child trace relationships for suite execution.
- Added portable archive backup/restore validation, integrity checks, and
  conflict protection for local SQLite result stores.

## v0.5.0 — 2026-08-31 — Phase 4: Operations (core)

- Removed the experimental Three.js "DevOps factory" pipeline visualization
  (`/pipeline`) after it did not reach usable visual quality; the console
  dashboard remains the only bundled web UI.
- Redesigned the web console with a hand-picked "paper ledger" palette and
  layout (serif type, hairline rules, inline stat line, zebra-striped
  tables) instead of a templated dark-SaaS admin theme.
- Added `SECURITY.md` documenting the hardening already shipped in v0.5.0.
- Added a bearer-token API authentication option (`opsbench serve
  --api-token` / `$OPSBENCH_API_TOKEN`).
- Wired `TraceTracer` OpenTelemetry-style spans through `execute_run` and
  `execute_suite`.
- Added an `opsbench doctor` command to validate a scenario gallery and
  result database, and an `opsbench --version` flag.
- Hardened the Kubernetes Deployment, Helm chart, and Docker image/Compose
  service: non-root user, read-only root filesystem, dropped capabilities,
  a default-deny `NetworkPolicy`, and a `.dockerignore` that excludes local
  databases and secrets from the build context.
- Added a CI-enforced public safety scan (`scripts/public_safety_scan.sh`),
  a deployment-manifest YAML validation step, a tag-triggered release
  workflow that verifies the pushed tag matches the package version, and
  a Python 3.11/3.12 test matrix.

## v0.4.0 — Phase 3: Platform Services

- Zero-dependency HTTP REST API server (`opsbench serve`).
- SQLite result store index (`SQLiteResultStore`, `opsbench store`).
- Result store JSON package export and import.
- Web console HTML dashboard.
- Scenario static linter and validator (`opsbench scenario lint`).
- Prometheus exposition format `/metrics` endpoint.
- Reference Docker/Compose, Kubernetes, Helm, Argo CD, and Terraform
  deployment assets; structured JSON logging and an initial trace span
  collector.

## v0.3.0 — Phase 2: Execution (complete)

- OpenAI-compatible response adapter.
- Concurrent scenario suite runner with reproducible run metadata.
- Terraform resource-import-conflict scenario pack.

## v0.2.0

- PostgreSQL transaction deadlock scenario pack.
- Markdown output format for result comparisons.

## v0.1.0 — Phase 1: Benchmark Core

- Versioned scenario manifest and evidence contract with deterministic
  content hashing.
- Deterministic diagnosis, evidence, action, and safety scoring engine.
- CLI for scenario validation, listing, auditing, prompt rendering, and
  offline response evaluation.
- Fixture and human response adapters, immutable result bundles, and
  result comparison/trial summaries.
- Five fictional scenarios spanning Kubernetes, observability, GitOps,
  and PostgreSQL categories.
