terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.zone

  # Borramos el node pool por defecto para usar los nuestros con configuracion especifica
  remove_default_node_pool = true
  initial_node_count       = 1

  # VPC-native: necesario para que los pods tengan IPs de la red de GCP
  networking_mode = "VPC_NATIVE"
  ip_allocation_policy {}
}

# Pool de infra: corre Redis y RabbitMQ
# Fijo en 2 nodos para que si cae uno, los pods se reprogramen en el otro
resource "google_container_node_pool" "infra" {
  name       = "infra-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  node_count = var.infra_node_count

  node_config {
    machine_type = var.infra_machine_type
    disk_size_gb = 50
    disk_type    = "pd-standard"

    labels = {
      role = "infra"
    }

    # Taint: repele pods que no tengan la toleracion role=infra
    # Evita que pods de apps ocupen nodos de infra por error
    taint {
      key    = "role"
      value  = "infra"
      effect = "NO_SCHEDULE"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}

# Pool de apps: corre nct-api, nct-consumer y worker-cpu
# Con autoscaling: GKE agrega o quita nodos segun la demanda
resource "google_container_node_pool" "apps" {
  name     = "apps-pool"
  location = var.zone
  cluster  = google_container_cluster.primary.name

  autoscaling {
    min_node_count = var.apps_min_nodes
    max_node_count = var.apps_max_nodes
  }

  node_config {
    machine_type = var.apps_machine_type
    disk_size_gb = 50
    disk_type    = "pd-standard"

    labels = {
      role = "apps"
    }

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
  }
}
