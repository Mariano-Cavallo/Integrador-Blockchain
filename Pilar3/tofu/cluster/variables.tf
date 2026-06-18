variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "blockchain-tp"
}

variable "region" {
  description = "Region de GCP"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zona de GCP donde se crea el cluster"
  type        = string
  default     = "us-central1-a"
}

variable "cluster_name" {
  description = "Nombre del cluster GKE"
  type        = string
  default     = "blockchain-cluster"
}

variable "infra_machine_type" {
  description = "Tipo de maquina para el nodo de infra (Redis + RabbitMQ)"
  type        = string
  default     = "e2-standard-2"
}

variable "apps_machine_type" {
  description = "Tipo de maquina para los nodos de apps"
  type        = string
  default     = "e2-standard-2"
}

variable "infra_node_count" {
  description = "Cantidad fija de nodos en el pool de infra (minimo 2 para tolerancia a fallos)"
  type        = number
  default     = 2
}

variable "apps_min_nodes" {
  description = "Minimo de nodos en el pool de apps"
  type        = number
  default     = 2
}

variable "apps_max_nodes" {
  description = "Maximo de nodos en el pool de apps (autoscaling)"
  type        = number
  default     = 4
}
