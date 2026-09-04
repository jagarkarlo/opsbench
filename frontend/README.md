# OpsBench Control Room

The `frontend` directory contains the React and TypeScript control room for
OpsBench. It is an observation and comparison surface for scenario packs,
indexed runs, portfolio rankings, and the capability matrix.

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

Open <http://localhost:5173/app/>. When the API is unavailable, the console
uses clearly labelled demo data so the layout remains inspectable.

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

The container build performs this frontend build automatically. Run
`docker compose up --build` from the repository root and open
<http://127.0.0.1:8080/app/>.

## UI boundaries

The console supports live health, scenario, run, result, and portfolio
inspection. The Operations view lists the complete OpsBench surface and marks
workflows that remain CLI-only, including benchmark execution, response
evaluation, store mutation, dataset packaging, attestation, MCP inspection,
and diagnostics. Proposed actions are never executed by the browser.
