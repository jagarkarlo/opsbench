# Changelog

All notable changes to this project are documented here. Dates are release
tag dates; versions follow the milestones described in `docs/roadmap.md`.

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
