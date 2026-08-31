# Changelog

All notable changes to this project are documented here. Dates are release
tag dates; versions follow the milestones described in `docs/roadmap.md`.

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
