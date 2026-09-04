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

The following repeated recovery exercise is available as a bounded follow-up:

- Numbered local drill series with configurable attempt count.
- Retention cleanup that keeps the newest verified attempt artifacts.
- JSON reporting for verified, retained, and removed attempts.

Scheduled recovery verification is now available as a bounded local
invocation primitive:

- One `store schedule-tick` execution can be called by cron or systemd.
- Verified and failed outcomes append to JSONL history.
- Failed verification can write a local alert artifact and returns exit code 3.

The first safe failure-injection slice is available as a bounded follow-up:

- Deterministic synthetic `timeout`, `malformed_response`,
  `missing_evidence`, and `adapter_exception` modes.
- Adapter wrapper support with optional scenario targeting.
- Resilient suite execution that preserves successful bundles and reports
  expected injected failures in deterministic gallery order.
- No destructive infrastructure actions and no execution of proposed actions.

Phase 4 is complete through v0.5.9. Its bounded operational exercises remain
local and synthetic: no benchmark command executes proposed infrastructure
actions or requires a resident daemon.

## Phase 5: Ecosystem

Phase 5 starts at v0.6.0.

- Scenario authoring SDK and contribution checks (completed in v0.6.0):
  - `ScenarioBuilder` fluent programmatic authoring SDK.
  - Turnkey scaffolding with `opsbench scenario init`.
  - Strict contribution verification with `opsbench scenario check`, validating
    linting, naming conventions, evidence depth, evaluator rules, reference
    response viability, and secret/credential hygiene.
- Reliability Replay and ColdRoute scenario adapters (completed in v0.6.1):
  - `ReliabilityReplayAdapter` and `ReliabilityReplayTimeline` for reproducible incident trace simulation.
  - `ColdRouteAdapter` and `ColdRouteProfile` for cold-path disaster recovery procedures.
  - CLI `opsbench run replay` command.
- GitHub, GitLab, Jira, Grafana, and Kubernetes MCP context adapters (completed in v0.6.2):
  - Standardized `MCPContextAdapter` protocol, `MCPResource`, `MCPToolDefinition`, and `MCPRegistry`.
  - Built-in platform adapters for GitHub, GitLab, Jira, Grafana, and Kubernetes.
  - Prompt enrichment with `--mcp <provider>` and CLI `opsbench mcp list|inspect`.
- Public benchmark datasets and signed result attestations.
- Model leaderboards with uncertainty and repeated-trial analysis.