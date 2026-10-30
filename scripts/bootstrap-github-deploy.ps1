[CmdletBinding()]
param(
    [string]$ProjectId = "agensi-mcp-188309590003",
    [string]$Region = "asia-south1",
    [string]$Repository = "archdiagram",
    [string]$GitHubRepository = "bharathgnana/archdiagram"
)

$ErrorActionPreference = "Stop"

$projectNumber = (gcloud.cmd projects describe $ProjectId --format="value(projectNumber)").Trim()
$deployServiceAccount = "github-archdiagram-deployer@$ProjectId.iam.gserviceaccount.com"
$runtimeServiceAccount = "archdiagram-runtime@$ProjectId.iam.gserviceaccount.com"
$poolId = "github-actions"
$providerId = "archdiagram"

gcloud.cmd services enable run.googleapis.com artifactregistry.googleapis.com iamcredentials.googleapis.com sts.googleapis.com --project $ProjectId

$repositoryExists = gcloud.cmd artifacts repositories list --project $ProjectId --location $Region --filter "repositoryId=$Repository" --format="value(name)"
if (-not $repositoryExists) {
    gcloud.cmd artifacts repositories create $Repository --project $ProjectId --location $Region --repository-format docker --description "ArchDiagram MCP images"
}

foreach ($serviceAccount in @("github-archdiagram-deployer", "archdiagram-runtime")) {
    $email = "$serviceAccount@$ProjectId.iam.gserviceaccount.com"
    $serviceAccountExists = gcloud.cmd iam service-accounts list --project $ProjectId --filter "email=$email" --format="value(email)"
    if (-not $serviceAccountExists) {
        gcloud.cmd iam service-accounts create $serviceAccount --project $ProjectId --display-name $serviceAccount
    }
}

gcloud.cmd projects add-iam-policy-binding $ProjectId --member "serviceAccount:$deployServiceAccount" --role roles/run.admin --condition=None
gcloud.cmd artifacts repositories add-iam-policy-binding $Repository --project $ProjectId --location $Region --member "serviceAccount:$deployServiceAccount" --role roles/artifactregistry.writer
gcloud.cmd iam service-accounts add-iam-policy-binding $runtimeServiceAccount --project $ProjectId --member "serviceAccount:$deployServiceAccount" --role roles/iam.serviceAccountUser

$poolExists = gcloud.cmd iam workload-identity-pools list --project $ProjectId --location global --filter "workloadIdentityPoolId=$poolId" --format="value(name)"
if (-not $poolExists) {
    gcloud.cmd iam workload-identity-pools create $poolId --project $ProjectId --location global --display-name "GitHub Actions"
}

$providerExists = gcloud.cmd iam workload-identity-pools providers list --project $ProjectId --location global --workload-identity-pool $poolId --filter "workloadIdentityPoolProviderId=$providerId" --format="value(name)"
if (-not $providerExists) {
    gcloud.cmd iam workload-identity-pools providers create-oidc $providerId --project $ProjectId --location global --workload-identity-pool $poolId --display-name "ArchDiagram GitHub Actions" --issuer-uri "https://token.actions.githubusercontent.com" --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" --attribute-condition "assertion.repository=='$GitHubRepository'"
}

$principal = "principalSet://iam.googleapis.com/projects/$projectNumber/locations/global/workloadIdentityPools/$poolId/attribute.repository/$GitHubRepository"
gcloud.cmd iam service-accounts add-iam-policy-binding $deployServiceAccount --project $ProjectId --member $principal --role roles/iam.workloadIdentityUser

$provider = "projects/$projectNumber/locations/global/workloadIdentityPools/$poolId/providers/$providerId"
Write-Output "Configure these GitHub Actions variables for ${GitHubRepository}:"
Write-Output "GCP_PROJECT_ID=$ProjectId"
Write-Output "GCP_REGION=$Region"
Write-Output "GCP_ARTIFACT_REPOSITORY=$Repository"
Write-Output "GCP_CLOUD_RUN_SERVICE=archdiagram-mcp"
Write-Output "GCP_RUNTIME_SERVICE_ACCOUNT=$runtimeServiceAccount"
Write-Output "GCP_DEPLOY_SERVICE_ACCOUNT=$deployServiceAccount"
Write-Output "GCP_WIF_PROVIDER=$provider"
