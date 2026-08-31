# Architecture

## Design Goals

OpsBench is designed around five constraints:

1. **Reproducibility:** The same scenario, response, and evaluator version must
   produce the same score.
2. **Provider neutrality:** Scenario packs and scoring cannot depend on one AI
   vendor or model API.
3. **Safety:** Proposed actions are evaluated separately from diagnostic
   accuracy, with explicit penalties for destructive or unsupported actions.
4. **Scalability:** Local execution and distributed workers share the same job
   and result contracts.
5. **Auditability:** Every score traces back to scenario evidence, evaluator
   rules, and the exact submitted response.

## Bounded Components

| Component | Responsibility |
| --- | --- |
| Scenario SDK | Load, validate, and version scenario packs. |
| Runner | Build benchmark jobs and execute them through an adapter. |
| Adapter SDK | Normalize model and human responses into one contract. |
| Evaluator | Score diagnosis, evidence, actions, and safety deterministically. |
| Result store | Persist immutable runs and aggregate comparisons. |
| API | Schedule runs and expose scenarios, jobs, and results. |
| Console | Explore scenarios, evidence, timelines, and score breakdowns. |
| Worker | Execute jobs independently with bounded concurrency and retries. |

## Core Data Flow

1. A scenario pack declares evidence and expected findings.
2. The runner snapshots the scenario and evaluator versions into a benchmark job.
3. An adapter submits scenario evidence to a human or model.
4. The adapter returns a provider-neutral structured response.
5. The evaluator produces a deterministic score breakdown and safety findings.
6. The immutable result is stored with hashes for later reproduction.

## Scaling Path

The first implementation runs in one process and stores result artifacts on the
filesystem. The interfaces must also support PostgreSQL-backed metadata, object
storage for evidence, and queue-driven workers. Horizontal workers will claim
idempotent jobs by run ID; retries must never create duplicate result records.

## Security Boundary

Scenario packs are untrusted input. Loaders enforce path containment and size
limits. Runners will use isolated containers without host mounts, credentials,
or unrestricted networks. Provider secrets remain outside scenario packs and
are passed only to the selected adapter at runtime.

As of v0.5.0, the reference API server, Docker image, and Kubernetes/Helm
deployment already enforce: optional bearer-token API authentication, a
non-root/read-only container filesystem, dropped Linux capabilities, and a
default-deny `NetworkPolicy` scoped to the server's own port plus DNS/HTTPS
egress. See [SECURITY.md](../SECURITY.md) for the current, verifiable scope.
