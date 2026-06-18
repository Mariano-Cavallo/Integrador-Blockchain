output "cluster_name" {
  description = "Nombre del cluster GKE"
  value       = google_container_cluster.primary.name
}

output "cluster_endpoint" {
  description = "URL del API server de Kubernetes (usado por kubectl y los pipelines)"
  value       = google_container_cluster.primary.endpoint
  sensitive   = true
}

output "cluster_location" {
  description = "Zona donde esta el cluster"
  value       = google_container_cluster.primary.location
}
