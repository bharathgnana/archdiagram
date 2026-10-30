output "artifact_registry_repository" {
  value = google_artifact_registry_repository.images.name
}

output "deployer_service_account" {
  value = google_service_account.deployer.email
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github_actions.name
}

output "mcp_endpoint" {
  value = var.container_image == null ? null : "${google_cloud_run_v2_service.mcp[0].uri}/mcp"
}

output "api_key_pepper_secret" {
  value = google_secret_manager_secret.api_key_pepper.name
}
