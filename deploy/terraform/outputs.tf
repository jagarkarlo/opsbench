output "namespace" {
  value       = kubernetes_namespace_v1.opsbench.metadata[0].name
  description = "Created Kubernetes namespace for OpsBench"
}

output "service_name" {
  value       = kubernetes_service_v1.opsbench_server.metadata[0].name
  description = "Kubernetes Service name for OpsBench server"
}

output "service_port" {
  value       = kubernetes_service_v1.opsbench_server.spec[0].port[0].port
  description = "Kubernetes Service port for OpsBench server"
}
