# OpsBench Control Room

The `frontend` directory contains the React and TypeScript control room for
OpsBench. The current prototype shows scenario packs, indexed-run summaries,
portfolio rankings, and a capability matrix. The planned IncidentOps experience
is described in [product direction](../docs/product-direction.md); Observe,
Verify, and Rehearse are not implemented views yet.

## Development

From this directory, install dependencies and start Vite:

```bash
npm ci
npm run dev
```

The Vite development server proxies `/api` requests to
`http://127.0.0.1:8080`. Start the Python API in another terminal:

```bash
cd ..
opsbench serve --host 127.0.0.1 --port 8080 --db bench.db
```

Open <http://localhost:5173/app/>. The console uses demo fallback data when the
API is unavailable. Currently, demo rows may also remain after a connected API
returns an empty list; do not interpret them as indexed results.

## Validation and build

```bash
npm run lint
npm run build
```

The production bundle is written to `frontend/dist`. The Python server serves
that directory at `/app` when started with `--frontend-path`:

```bash
opsbench serve --frontend-path frontend/dist --db bench.db
```

The container build is configured to build these assets automatically. Docker
startup/persistence still needs validation, including the database path versus
the read-only Compose root. See [roadmap Gate A](../docs/roadmap.md).

## UI boundaries

The console fetches health, scenarios, run summaries, and portfolio results.
The topology is illustrative, not live infrastructure telemetry; several
operational values are hard-coded. Full run detail/comparison controls and
reliable partial-error states are pending. Capability IDs copied by Operations
are not necessarily valid CLI commands; use the [root README](../README.md).

The API's optional bearer authentication also protects frontend assets, while
the browser currently has no token UX. Authentication is therefore an unresolved
integration requirement, not a completed team-login workflow. Proposed actions
are never executed by the browser.

## Planned IncidentOps UI

The target is an interactive 2.5D control room using the existing React,
TypeScript, Vite, and Three.js stack. Use orthographic depth for relationships,
with node/edge selection, pan/zoom/reset, and evidence synchronized to timeline
selection. Keep accessible controls in React and retain CSS initially; Tailwind
is optional, not required for depth or interactivity. WebStorm is an editor.

- Observe: bounded source evidence with timestamps, provenance, and missing data.
- Verify: stage-level assertions, coverage, failure evidence, and corrected reruns.
- Rehearse: modelled checkpoints, alternative decisions, and debrief comparisons.

Preserve visible mode boundaries. Never show simulations as live observations
or receiver acceptance as human acknowledgement. Prioritize a readable evidence
timeline over decorative topology; use animation only to represent known state.
Desktop/mobile browser checks and canvas validation are pending release gates,
not verification established by a successful TypeScript build.
