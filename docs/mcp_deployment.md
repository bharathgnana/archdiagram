# MCP deployment

The MCP runs on Cloud Run as a public Streamable HTTP service. Its endpoint is
`https://<cloud-run-url>/mcp`. Hosted requests require a buyer-specific API key
in the `Authorization: Bearer <key>` header. Local stdio use remains
unauthenticated. The Cloud Run runtime identity has only Firestore access for
quota records and Secret Manager access for the API-key HMAC pepper.

Each buyer key has a configurable monthly request limit; the default is 1,000
MCP HTTP requests per calendar month. The counter is reset atomically on the
first request of the next UTC month.

## One-time Google Cloud setup

Run this from an authenticated terminal after reviewing the Terraform
configuration in [`infra/terraform/`](../infra/terraform/):

```powershell
.\scripts\bootstrap-terraform.ps1
```

The script connects to the existing remote Terraform state and prints the
GitHub configuration values. The state bucket is managed separately by
`infra/terraform-bootstrap`. Create the Firestore Native default database and
the secret version separately; never put the pepper in Terraform state or Git.
The GitHub workflow uses the existing repository-restricted workload identity.
Do not apply this configuration with `container_image` unset after the service
exists: that would remove the Cloud Run service.

Add the variables printed by the script under GitHub repository **Settings >
Secrets and variables > Actions > Variables**. Do not create a JSON service
account key: the workflow exchanges GitHub's short-lived OIDC token directly
for Google credentials.

Also set `TF_STATE_BUCKET` to `agensi-mcp-188309590003-tfstate`. The pipeline
uses the same Terraform state and changes the Cloud Run revision by applying
the image generated for each commit.

## Delivery flow

1. Pull requests run the regular CI suite in `ci.yml`.
2. A push to `main` runs `deploy-mcp.yml`.
3. GitHub Actions builds the Docker image, pushes it to Artifact Registry, and
   deploys the image to Cloud Run.
4. The workflow prints the client endpoint with `/mcp` appended.

To release manually, run **Deploy MCP** from the repository's Actions tab.

## Issue, revoke, and rotate buyer keys

The Agensi connector is free. Hosted subscriptions are paid directly through
Razorpay. Configure the gateway and self-service key issuance using
[razorpay-billing.md](razorpay-billing.md). Do not use an Agensi install or
claimed purchase as evidence of paid hosted access.

For an administrator-approved legacy/manual entitlement, issue a key from an
administrator workstation after independently verifying access:

```powershell
$env:GOOGLE_CLOUD_PROJECT = "agensi-mcp-188309590003"
$env:ARCHDIAGRAM_API_KEY_PEPPER = gcloud secrets versions access latest --secret archdiagram-api-key-pepper --project $env:GOOGLE_CLOUD_PROJECT
python scripts/issue_api_key.py --buyer "verified-manual-entitlement-reference" --monthly-limit 1000
```

The command prints the plaintext key once. Send it through a secure support
channel, then direct the buyer to configure it as a Bearer token in their MCP
client. Firestore stores only an HMAC digest, not the secret. To revoke a key,
set its `active` field to `false` in the `api_keys` Firestore collection. To
rotate a key, revoke the old record and issue a new one.

Do not place buyer keys in an Agensi skill, an MCP prompt, a repository, or a
chat transcript.
