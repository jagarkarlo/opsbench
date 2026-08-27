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

## Phase 4: Operations

- Prometheus metrics, structured logs, and OpenTelemetry traces.
- Docker Compose development environment.
- Kubernetes and Helm deployment.
- Argo CD GitOps examples and Terraform infrastructure.
- Backup, restore, load, chaos, and disaster-recovery exercises.

## Phase 5: Ecosystem

- Scenario authoring SDK and contribution checks.
- Reliability Replay and ColdRoute scenario adapters.
- GitHub, GitLab, Jira, Grafana, and Kubernetes MCP context adapters.
- Public benchmark datasets and signed result attestations.
- Model leaderboards with uncertainty and repeated-trial analysis.