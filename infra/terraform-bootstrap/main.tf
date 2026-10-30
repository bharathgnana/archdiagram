variable "project_id" { type = string }
variable "region" { type = string }
variable "state_bucket_name" { type = string }

resource "google_storage_bucket" "terraform_state" {
  name                        = var.state_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}
