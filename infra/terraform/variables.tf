variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-south1"
}

variable "github_repository" {
  type    = string
  default = "bharathgnana/archdiagram"
}

variable "artifact_repository" {
  type    = string
  default = "archdiagram"
}

variable "service_name" {
  type    = string
  default = "archdiagram-mcp"
}

variable "state_bucket_name" {
  type    = string
  default = "agensi-mcp-188309590003-tfstate"
}

variable "container_image" {
  type        = string
  default     = null
  nullable    = true
  description = "Artifact Registry image to release. Omit during infrastructure bootstrap."
}

variable "firestore_database" {
  type        = string
  default     = "(default)"
  description = "Firestore Native database used for buyer API keys and quotas."
}

variable "api_key_pepper_secret_id" {
  type        = string
  default     = "archdiagram-api-key-pepper"
  description = "Secret Manager secret containing the HMAC pepper for buyer API keys."
}
