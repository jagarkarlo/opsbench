# Roadmap

Each milestone must remain runnable and independently verifiable.

## Active Direction (2026-09-07)

Build IncidentOps powered by OpsBench: Observe, Verify, Rehearse. The first
production-value slice is monitoring-path verification, not a general AI SRE
or production simulator. See [product direction](product-direction.md).

Unchecked items below are **planned**; checked items are implemented on
`develop`, not a tagged release. No delivery dates are promised. Preserve existing
benchmark contracts and tests. Historical phases follow these active gates.

### Gate A: Trustworthy Prototype

- [x] Separate explicit demo/live/empty/error states; remove fabricated live values.
- [x] Add indexed run reports and two-run comparison; remove invented CLI commands.
- [x] Build an orthographic 2.5D benchmark workflow with node selection,
  pan/zoom/reset, and synchronized stage inspection.
- [x] Keep React/TypeScript/Vite/Three.js with keyboard stage controls, native
  dialogs, reduced motion, and responsive layouts; label model animation.
- [ ] Add incident-specific edge evidence and synchronized timeline inspection.
- [ ] Implement and test browser authentication, including static asset access.
- [ ] Validate binary assets, missing-asset responses, and path containment.
- [ ] Correct Docker database/volume ownership and read-only filesystem wiring.
- [ ] Run Docker build/start/restart/persistence and backup/restore smoke tests.
- [x] Add desktop/mobile browser tests, screenshots, canvas-pixel and picking checks.

Exit: a clean documented startup works; data states match API results, auth does
not break navigation, persisted results survive restart, and no display value
is presented as live without a source. Existing CLI behaviour remains intact.

### Gate B: Monitoring-Path Verification

- [ ] Define versioned assertions, stage evidence, coverage, and run outcomes.
- [ ] Build one disposable service/Prometheus/Alertmanager/test-receiver lab.
- [ ] Use existing rule/routing tooling and real components, not a second evaluator.
- [ ] Verify a healthy signal from emission through receiver acceptance.
- [ ] Test missing collection, mismatched routing, and invalid notification content.
- [ ] Handle timeouts, unavailable stages, and partial evidence without guessed causes.
- [ ] Retain corrected reruns and provide visual evidence comparison and export.
- [ ] Guarantee cancellation and cleanup; prevent credentials or real paging access.

Exit: automated integration tests cover the healthy path, all three failures,
and corrected reruns. UI and exported results agree on failed, unknown, and
untested stages. A downstream-only probe is never labelled a full-path test.

### Gate C: Self-Hosted Team Pilot

- [ ] Deploy behind HTTPS/OIDC with server-side authorization and audit records.
- [ ] Add bounded, read-only, allowlisted connectors and redaction before storage.
- [ ] Isolate workers from production identities; enforce quotas and deadlines.
- [ ] Define retention/deletion and validate restore and upgrade procedures.
- [ ] Test credential revocation, permission denial, and failure recovery.
- [ ] Monitor OpsBench health through an independent signal.
- [ ] Run a pilot measuring setup effort, diagnosis time, and false/ambiguous results.

Exit: a team can install and repeat the workflow without developer intervention,
review retained data, revoke access, and restore results. Pilot feedback must
justify further scope. This is not permission to execute against production.

### Gate D: Branching Rehearsal

- [ ] Select a maintained simulation library and define a bounded incident model.
- [ ] Record checkpoint lineage, model version, seed, and external schedules.
- [ ] Support alternative decisions and evidence/outcome comparison.
- [ ] Keep hidden state out of play; separate blind attempts from informed replays.
- [ ] Validate selected model behaviours against disposable real services.

Exit: repeatable model tests support branch comparisons without claiming
production prediction. Existing replay adapters alone do not satisfy this gate.

### Later Options: Separate Approval Required

- Production canaries: scoped write identity, approved recipients/time windows,
  notification budgets, cancellation, expiry, audit, and precise coverage labels.
- Hosted multi-tenancy: tested tenant boundaries, quotas, secure secret lifecycle,
  retention, cost controls, incident response, and operational recovery.
- Reviewed change proposals and optional agent comparisons after evidence
  contracts are trustworthy; no autonomous production remediation by default.

## Historical Benchmark Milestones

The phases below describe the benchmark foundation through v0.6.4, not completion
of the IncidentOps gates. The React console on `develop` is a prototype added
after that release, not an already released production interface.

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
- Public benchmark datasets and signed result attestations (completed in v0.6.3):
  - Deterministic dataset manifests with local gallery checksum verification.
  - HMAC-signed result attestations and `opsbench attest` verification commands.
- Model leaderboards with uncertainty and repeated-trial analysis (completed):
  - Repeated-trial sample variance and standard deviation.
  - Normal-approximation 95% confidence intervals for runner means.
  - Conservative lower-bound ranking with deterministic tie-breakers.
  - JSON and Markdown output through `opsbench leaderboard results`.
- Cross-scenario portfolio leaderboards (completed in v0.6.4):
  - Normalized score aggregation across scenario IDs with explicit coverage.
  - Repeated-trial uncertainty and conservative lower-bound ranking.
  - JSON and Markdown output through `opsbench leaderboard portfolio`.