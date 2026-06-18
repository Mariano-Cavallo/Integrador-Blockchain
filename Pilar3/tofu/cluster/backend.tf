terraform {
  backend "gcs" {
    bucket = "blockchain-tp-tofu-state"
    prefix = "pilar3/cluster"
  }
}
