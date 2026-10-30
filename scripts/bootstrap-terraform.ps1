[CmdletBinding()]
param(
    [string]$ProjectId = "agensi-mcp-188309590003",
    [string]$Region = "asia-south1",
    [string]$StateBucket = "agensi-mcp-188309590003-tfstate"
)

$ErrorActionPreference = "Stop"
$terraformDirectory = Join-Path $PSScriptRoot "..\infra\terraform"
Push-Location $terraformDirectory
try {
    # The bucket is created separately by infra/terraform-bootstrap. Never
    # switch an existing remote state to a fresh local state or apply with a
    # null container image: that would remove the deployed service.
    terraform init -reconfigure -input=false -backend-config "bucket=$StateBucket" -backend-config "prefix=archdiagram-mcp"
    if ($LASTEXITCODE -ne 0) { throw "Terraform backend initialization failed" }
    terraform output
    Write-Output "Configure these GitHub Actions variables:"
    Write-Output "GCP_PROJECT_ID=$ProjectId"
    Write-Output "GCP_REGION=$Region"
    Write-Output "GCP_ARTIFACT_REPOSITORY=archdiagram"
    Write-Output "GCP_CLOUD_RUN_SERVICE=archdiagram-mcp"
    Write-Output "GCP_RUNTIME_SERVICE_ACCOUNT=$(terraform output -raw runtime_service_account)"
    Write-Output "GCP_DEPLOY_SERVICE_ACCOUNT=$(terraform output -raw deployer_service_account)"
    Write-Output "GCP_WIF_PROVIDER=$(terraform output -raw workload_identity_provider)"
    Write-Output "TF_STATE_BUCKET=$StateBucket"
}
finally {
    Pop-Location
}
