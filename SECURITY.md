# Security

OpsBench uses only fictional infrastructure, generated operational data, and
synthetic credentials. It does not contain employer systems, production
credentials, or private incident details.

## Reporting a Vulnerability

Open a GitHub issue or private security advisory on this repository. There is
no bug bounty; this is a personal open-source project.

## What Is Already Hardened

- **API authentication:** `opsbench serve --api-token` (or `$OPSBENCH_API_TOKEN`)
  requires a bearer token on every endpoint except `/api/v1/health`, which
  stays open so Kubernetes liveness/readiness probes work without credentials.
- **Kubernetes / Helm:** the server Pod runs as a non-root user with a
  read-only root filesystem, dropped Linux capabilities, and a default-deny
  `NetworkPolicy` scoped to its own port plus DNS/HTTPS egress.
- **Containers:** the Docker image and Compose service run as a dedicated
  non-root UID; `.dockerignore` excludes local databases, `.env` files, and
  other secrets from the build context.
- **CI:** every push and pull request runs `scripts/public_safety_scan.sh`,
  which fails the build on credential-shaped strings or employer-specific
  identifiers in tracked text, plus a YAML validation pass over `deploy/`.

## What Is Explicitly Out of Scope (local prototype)

OpsBench's local HTTP server (`opsbench serve`) is a zero-dependency
`http.server` implementation meant for local/dev use and the reference
Kubernetes deployment. It does not implement TLS termination, request rate
limiting, or multi-tenant isolation; put it behind a real ingress/reverse
proxy (as the bundled Ingress and Helm chart already assume) before exposing
it beyond a trusted network.
