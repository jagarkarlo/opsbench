variable "namespace" {
  type        = string
  description = "Kubernetes namespace for OpsBench server deployment"
  default     = "opsbench"
}

variable "server_port" {
  type        = number
  description = "Port for the OpsBench server container"
  default     = 8080
}

variable "replica_count" {
  type        = number
  description = "Number of OpsBench server pod replicas"
  default     = 1
}

variable "container_image" {
  type        = string
  description = "Container image tag for OpsBench server"
  default     = "ghcr.io/jagarkarlo/opsbench:latest"
}
