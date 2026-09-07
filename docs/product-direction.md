# Product Direction: IncidentOps Powered by OpsBench

Decision date: 2026-09-07. Status: adopted planning direction, not shipped
functionality or a claim of thesis novelty. See the [roadmap](roadmap.md),
[architecture](architecture.md), and [security boundaries](../SECURITY.md).

## Purpose and Audience

Help small platform and on-call teams answer: **Which parts of our incident
response path have actually been verified, and where does our evidence stop?**
Start with operators of Prometheus/Alertmanager stacks who need repeatable
checks after configuration changes. Let teammates learn from the same bounded
failure in a later rehearsal workflow.

IncidentOps is the planned visual experience in this repository. OpsBench
remains its scenario and result foundation. Preserve existing commands, packs,
and results; extend versioned contracts without changing old score semantics.
Do not split into multiple products or require AI for the first useful workflow.

## Problem to Solve

A successful notification test does not prove that a real alert will reach its
destination. Collection, rule evaluation, routing, and payload handling can fail
independently. Teams need a clear view of what was tested and where evidence stops.

Build on existing monitoring and rule-testing tools. Connect verification,
visual explanation, and reusable rehearsal in one workflow, and validate its
usefulness with pilot users before expanding scope.

## Visual Direction

Build an interactive, futuristic 2.5D control room: a readable two-dimensional
workspace with orthographic depth, layered service nodes, and restrained motion.
Depth should explain relationships and state, not obstruct operational evidence.

Use the existing React, TypeScript, Vite, and Three.js stack. Keep navigation,
forms, tables, and accessible controls in React; use Three.js for the topology
scene. Keep the existing CSS initially. Tailwind is optional if a later styling
decision justifies migration; WebStorm is an optional editor, not a runtime
dependency or UI framework.

Support selecting a node or connection to inspect evidence, pan/zoom with a
reset view, and timeline selection synchronized with the scene. Animate only
observed events or explicitly labelled simulation activity. Keep text sharp and
legible with no perspective-dependent labels or decorative dashboard values.

Provide keyboard-accessible selection and a list equivalent to the scene,
reduced-motion support, stable layouts, and touch-friendly controls. On mobile,
switch between the scene and evidence view rather than squeezing both together.
Verify desktop/mobile screenshots, interactions, and nonblank canvas rendering
before considering the UI complete. This is the target design, not shipped UI.

## Planned Experience

### Observe

Read selected telemetry and configuration evidence through scoped connectors.
Link back to source tools. Display provenance, collection time, freshness, and
missing data. Partial observations must not look like a complete live topology.

### Verify

Run a bounded check and display its measured path:

```text
Test signal -> Collected -> Rule fired -> Route matched -> Receiver accepted
```

Each stage needs passed, failed, unknown, or not-tested status. Store assertions,
observations, timestamps, configuration versions, and coverage boundaries.
Missing evidence is not automatically a root cause. HTTP acceptance by a
receiver does not prove human receipt or response.

### Rehearse

Use an explicit synthetic model with visible evidence, decisions, checkpoints,
and alternative branches. Keep hidden state out of initial investigations and
reveal model-defined causes during debrief. Separate blind attempts from
informed replays when comparing results.

Match the exogenous workload and fault schedule across branches. Record model
version and seed without claiming arbitrary external systems are deterministic.
Logs cannot reconstruct all production state or prove counterfactual outcomes.
Validate selected model behaviours against disposable real services.

## First Vertical Slice

Use one disposable test service, Prometheus, Alertmanager, and a test receiver.
Begin at the emitted signal to cover collection and evaluation. Posting directly
to Alertmanager covers only downstream stages and must be labelled accordingly.

1. Declare the expected path, configuration versions, time budget, and receiver.
2. Run a healthy baseline and retain per-stage evidence.
3. Introduce missing collection, mismatched routing, and invalid notification
   content independently in the disposable environment.
4. Show failed or unobserved stages without guessing unsupported causes.
5. Correct the configuration, rerun, and compare retained evidence.
6. Export a sanitized report for change review or regression testing.

Acceptance requires automated integration tests for all three failures and
corrected reruns. The UI must match stored observations, including timeout,
unavailable, and partial-result cases. No fabricated green states, production
credentials, or unapproved notifications are allowed.

During the pilot, measure setup effort, time to locate the broken stage, useful
failures caught, and false or ambiguous conclusions. Expand only if operators
can repeat the workflow and find it useful compared with existing scripts.

## Deployment Direction

Localhost is development mode, not the product boundary. Start with a self-hosted
team instance on a VM or Kubernetes behind HTTPS and OIDC. Keep secrets
server-side. An outbound connector inside the team's network can send
allowlisted, redacted observations without publicly exposing internal APIs.

Separate read-only collection from worker execution. Workers receive lab-scoped
capabilities, never production credentials. Start with one team; queue and
storage choices and hosted tenant isolation need explicit decisions and tests.

## Non-Goals and Future Options

- No autonomous production remediation or production fault injection initially.
- No replacement for Grafana, Prometheus, Loki, or established incident tooling.
- No full Kubernetes emulator, automatic digital twin, or guaranteed root cause.
- No claim that keyword scoring proves semantic grounding or remediation safety.
- No automatic publication of private evidence to scenarios or leaderboards.
- No requirement to merge unrelated portfolio repositories into this project.

After the pilot, consider separately approved production canaries with
allowlisted receivers, rate limits, cancellation, expiry, and audit logs. Results
only apply to the path and configuration exercised. Monitor OpsBench through an
independent health signal so its own failure is detectable.

Branching rehearsal, reviewed change proposals, and optional agent comparison
can follow reliable evidence contracts. Hosted multi-tenancy and production
execution require separate threat models and release gates.