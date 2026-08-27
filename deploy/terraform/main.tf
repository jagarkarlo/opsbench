terraform {
  required_version = ">= 1.0.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.20.0"
    }
  }
}

resource "kubernetes_namespace_v1" "opsbench" {
  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/name"       = "opsbench"
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}

resource "kubernetes_deployment_v1" "opsbench_server" {
  metadata {
    name      = "opsbench-server"
    namespace = kubernetes_namespace_v1.opsbench.metadata[0].name
    labels = {
      "app.kubernetes.io/name" = "opsbench-server"
    }
  }

  spec {
    replicas = var.replica_count

    selector {
      match_labels = {
        "app.kubernetes.io/name" = "opsbench-server"
      }
    }

    template {
      metadata {
        labels = {
          "app.kubernetes.io/name" = "opsbench-server"
        }
      }

      spec {
        container {
          name  = "opsbench-server"
          image = var.container_image

          args = [
            "serve",
            "--host", "0.0.0.0",
            "--port", tostring(var.server_port),
            "--gallery-path", "scenarios",
            "--db", "/app/data/benchmarks.db"
          ]

          port {
            name           = "http"
            container_port = var.server_port
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/api/v1/health"
              port = var.server_port
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/api/v1/health"
              port = var.server_port
            }
            initial_delay_seconds = 3
            period_seconds        = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "opsbench_server" {
  metadata {
    name      = "opsbench-server"
    namespace = kubernetes_namespace_v1.opsbench.metadata[0].name
  }

  spec {
    selector = {
      "app.kubernetes.io/name" = "opsbench-server"
    }

    port {
      name        = "http"
      port        = var.server_port
      target_port = "http"
    }

    type = "ClusterIP"
  }
}
