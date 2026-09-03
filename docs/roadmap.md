# Roadmap

Each milestone must remain runnable and independently verifiable.

## Phase 1: Benchmark Core

- Versioned scenario manifest and evidence contract.
- Deterministic schema validation and content hashing.
- Structured benchmark response contract.
- Scoring engine for diagnosis, evidence, actions, and safety.
- CLI for scenario validation and offline response evaluation.
- Initial Kubernetes, observability, GitOps, and database scenarios.

## Phase 2: Execution

- Provider-neutral adapter SDK.
- Human, fixture, and OpenAI-compatible adapters.
- Run manifests with seeds, model parameters, and immutable inputs.
- Concurrent local runner with timeouts and bounded retries.
- Reproducible result bundles and comparison reports.

## Phase 3: Platform Services (Completed in v0.4.0)

- Zero-dependency HTTP REST API server (`opsbench serve`).
- SQLite result store index (`SQLiteResultStore` & `opsbench store`).
- Result store JSON package export and import (`opsbench store export/import`).
- Web Console HTML dashboard (`render_dashboard_html`).
- Scenario static linter and validator (`opsbench scenario lint`).
- Prometheus exposition format metrics collector (`/metrics`).

## Phase 4: Operations (Core completed in v0.5.0)

- Prometheus metrics, structured logs, and OpenTelemetry-style traces.
- Docker Compose development environment, hardened to run as non-root.
- Kubernetes and Helm deployment, hardened with a non-root/read-only
  security context and a default-deny `NetworkPolicy`.
- Argo CD GitOps examples and a Terraform Kubernetes module.
- Bearer-token API authentication and a CI-enforced public safety scan.
- `opsbench doctor` environment/config validation command.

The following portable archive foundation is available as a bounded follow-up:

- Canonical JSON backup archives with SHA-256 integrity verification.
- Explicit backup, restore, and archive validation commands.
- Restore conflict checks that prevent duplicate or overwritten result run IDs.

The following performance foundation is available as a bounded follow-up:

- Dependency-free per-run and suite wall-time/throughput measurements.
- Portable JSON performance baselines and threshold-based regression detection
  for local and CI workflows.

The following recovery exercise is available as a bounded follow-up:

- `opsbench store drill` exports, verifies, restores, and hash-compares an
  indexed local result store against a fresh SQLite recovery target.

The first safe failure-injection slice is available as a bounded follow-up:

- Deterministic synthetic `timeout`, `malformed_response`,
  `missing_evidence`, and `adapter_exception` modes.
- Adapter wrapper support with optional scenario targeting.
- Resilient suite execution that preserves successful bundles and reports
  expected injected failures in deterministic gallery order.
- No destructive infrastructure actions and no execution of proposed actions.

Deferred to a later milestone:

- Partial-suite performance aggregation and reporting for injected failures.
- Load, chaos, and disaster-recovery exercises, including scheduled backup and
  recovery drills beyond the local archive foundation.

## Phase 5: Ecosystem

- Scenario authoring SDK and contribution checks.
- Reliability Replay and ColdRoute scenario adapters.
- GitHub, GitLab, Jira, Grafana, and Kubernetes MCP context adapters.
- Public benchmark datasets and signed result attestations.
- Model leaderboards with uncertainty and repeated-trial analysis.