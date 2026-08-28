# OpsBench Observability Configs

Reference configuration snippets for wiring OpsBench into an existing
Prometheus + Grafana Alloy + Loki stack. These are examples to merge into
your own observability deployment, not standalone deployable manifests.

- `prometheus-scrape-config.yaml` — scrape job for the OpsBench `/metrics`
  Prometheus endpoint (see `opsbench.metrics.generate_prometheus_metrics`).
- `alloy-config.river` — Grafana Alloy pipeline that discovers OpsBench pods
  in the `opsbench` namespace and forwards their structured JSON logs
  (see `opsbench.logging.JSONLogger`) to a Loki write endpoint.

No Loki-side configuration is required beyond an existing Loki gateway
reachable at the `loki.write` endpoint above; OpsBench only produces logs,
it does not run or configure Loki itself.
