# Security

OpsBench uses only fictional infrastructure, generated operational data, and
synthetic credentials. It does not contain employer systems, production
credentials, or private incident details.

## Reporting a Vulnerability

Open a GitHub issue or private security advisory on this repository. There is
no bug bounty; this is a personal open-source project.

## Existing Controls and Reference Configuration

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
limiting, or multi-tenant isolation. A reverse proxy is necessary for HTTPS but
is not sufficient to make this prototype safe for untrusted or multi-user access.
The bearer token also protects static frontend assets; the console has no token
UX. Do not treat the current deployment examples as a production-readiness claim.

Container runtime validation is pending, including the default database path
versus Compose's read-only root and writable volume. Kubernetes network-policy
enforcement depends on the deployed CNI and effective configuration.

## Planned IncidentOps Boundaries

These are release requirements, not controls already implemented:

- Read-only connectors collect allowlisted, size/time-bounded evidence with
  redaction before transfer/storage and explicit data-owner authorization.
- Separate production collection identities from isolated lab workers. No
  production credentials, privileged host access, or unrestricted worker egress.
- HTTPS/OIDC must be backed by server-side authorization for evidence and jobs,
  audit records, revocation, quotas, and tested permission-denial paths.
- Treat imported evidence as untrusted, including embedded instructions. Never
  convert it into shell execution, agent authority, or public training material.
- Define retention, deletion, encryption and secret-management requirements,
  and test backups and restoration before accepting private evidence.
- External model requests and publication of sanitized scenarios are separate
  opt-in decisions. Human/AI benchmark scoring is not a safety certification.
- Production canaries require separately approved write identities, recipient
  allowlists, bounded frequency, expiry, cancellation, and audit. Read-only
  collection consent does not authorize notification delivery or fault injection.
- Monitor the product independently. Failure of its own alert path must not
  silently remove the only signal that verification has stopped.

Initial verification runs target disposable labs only. Hosted tenant isolation
and any production execution require separate threat models and testing. See
the [roadmap](docs/roadmap.md) for implementation gates.
