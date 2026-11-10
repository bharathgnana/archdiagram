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

variable "firebase_web_api_key" {
  type        = string
  default     = ""
  description = "Public Firebase web API key for browser email sign-in."
}

variable "firebase_auth_domain" {
  type        = string
  default     = ""
  description = "Identity Platform/Firebase auth domain for browser email sign-in."
}

variable "billing_enabled" {
  type        = bool
  default     = false
  description = "Enable direct Razorpay subscriptions only after test-mode checkout and webhooks pass."
}

variable "razorpay_key_id" {
  type    = string
  default = ""
}

variable "razorpay_plan_id" {
  type    = string
  default = ""
}

variable "razorpay_key_secret_name" {
  type        = string
  default     = "archdiagram-razorpay-key-secret"
  description = "Existing Secret Manager secret name. Never pass its value to Terraform."
}

variable "razorpay_webhook_secret_name" {
  type        = string
  default     = "archdiagram-razorpay-webhook-secret"
  description = "Existing Secret Manager secret name for the dedicated webhook secret."
}

variable "plan_amount" {
  type        = number
  default     = 500
  description = "Monthly price in minor currency units; must match the Razorpay plan."
  validation {
    condition     = var.plan_amount > 0 && floor(var.plan_amount) == var.plan_amount
    error_message = "Price must be a positive integer in minor currency units."
  }
}

variable "plan_currency" {
  type    = string
  default = "USD"
  validation {
    condition     = can(regex("^[A-Z]{3}$", var.plan_currency))
    error_message = "Use an uppercase three-letter currency code."
  }
}
