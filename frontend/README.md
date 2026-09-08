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

Open <http://localhost:5173/app/>. Live API data is the default. Enable the
explicit Demo dataset checkbox to explore synthetic scenarios and results.
Empty or failed API responses never silently switch to demo data. Individual
source failures are shown without discarding successful sources.

## Validation and build

```bash
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
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

The console fetches health, scenarios, indexed runs, and portfolio results.
Search/select scenarios, inspect the benchmark workflow, open stored run
reports, and compare two results. Cross-scenario comparisons carry a warning.
Operations displays capability metadata without inventing executable commands.

The orthographic Three.js factory uses original procedural geometry: rounded
monitoring instruments, a collector, a segmented delivery conveyor, an
articulated orchestration arm, container platforms, and routed cables. Studio
environment lighting, shadows, bevels, and instrument textures provide depth.

The stretched U-shaped layout includes an Ansible joystick console and a
Terraform forklift. Raised machine emblems use the packaged Simple Icons paths
for Kubernetes, Terraform, Ansible, Grafana, Prometheus, Docker, and GitLab.
Simple Icons artwork is distributed under CC0; brand names and trademarks
remain their owners' property. This illustration implies no endorsement.

One active package follows a 36-second illustrated cycle: conveyor arrival,
grip, lift, transfer, placement on a pallet, forklift loading, delivery, unloading,
and return. The belt stops during the handoff. The next package starts only
after the full cycle completes. The arm targets the package with two-link
kinematics, and the package is parented to the actual gripper or forklift load
socket during transport. A cycle slider pauses and scrubs the sequence.

Select physical stations or use arrows/Home/End in the stage tabs to update the
inspector. Camera controls include orbit/pan, zoom/reset, a top view, selected
station focus, and an expanded scene. Playback supports pause and 0.5x/1x/2x
speed. Reduced motion starts paused; explicit playback is still available.
The machinery and its animation are illustrative, not live telemetry or actual
infrastructure actions. Native run dialogs contain focus and support Escape.

The API's optional bearer authentication also protects frontend assets, while
the browser currently has no token UX. Authentication is therefore an unresolved
integration requirement, not a completed team-login workflow. Proposed actions
are never executed by the browser.

## Current UI and Future Work

The interactive 2.5D benchmark workspace uses React, TypeScript, Vite, Three.js,
Lucide icons, and CSS. Node selection and the inspector are implemented; edge
inspection and a real incident timeline remain future work. Tailwind is not
required for depth or interactivity. WebStorm is an optional editor.

- Observe: bounded source evidence with timestamps, provenance, and missing data.
- Verify: stage-level assertions, coverage, failure evidence, and corrected reruns.
- Rehearse: modelled checkpoints, alternative decisions, and debrief comparisons.

Preserve visible mode boundaries. Never show simulations as live observations
or receiver acceptance as human acknowledgement. Prioritize a readable evidence
timeline over decorative topology; use animation only to represent known state.
Playwright checks desktop (1440px) and mobile (390px) layouts, pixel-based canvas
visibility/movement and station picking, keyboard selection, camera panning,
focus/expansion, playback/reduced motion, package continuity and actual carrier
attachment, logo presence, cycle scrubbing, scenario search, run comparison/dialogs,
and empty/partial API states. Screenshots are generated
under ignored `test-results/`; the frontend CI workflow retains them as artifacts.
These checks do not validate production connectors, authentication, or Docker.
