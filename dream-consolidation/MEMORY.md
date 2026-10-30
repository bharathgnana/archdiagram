# Project Memory

## Current state

- `archdiagram` renders architecture, process, decision, and data-flow specs into editable Draw.io, PowerPoint, Visio, SVG, HTML, and PDF outputs. Vendor-icon catalogs and swim lanes are supported. — `README.md`, `archdiagram/`, `archdiagram/formats.py`
- Core engine remains stdlib-only; the optional MCP SDK is isolated to `mcp_server/`, and optional Node helpers remain confined to `node/` plus `archdiagram/rasterize/`. — `AGENTS.md`, `pyproject.toml`
- The local working tree contains an uncommitted Cloud Run deployment implementation: a Docker image, Streamable HTTP MCP mode when `PORT` is set, CI smoke testing, a GitHub Actions deploy workflow, and Terraform infrastructure. — `Dockerfile`, `mcp_server/server.py`, `.github/workflows/`, `infra/terraform/`
- Terraform is intended to manage Artifact Registry, deployment/runtime service accounts, GitHub Actions OIDC federation restricted to `bharathgnana/archdiagram`, Cloud Run, and public invocation. The Cloud Run resource is only created when `container_image` is supplied. — `infra/terraform/main.tf`
- An Agensi marketplace package exists for an `architecture-diagram-mcp` skill. Agensi listings distribute skills, not MCP servers; the listing directs buyers to a separately hosted MCP endpoint. — `marketplace/archdiagram-mcp/SKILL.md`

## Decisions and constraints

- Preserve legacy rendering behavior and byte goldens unless a documented compatibility change is intentional. — `docs/maintainer_guide.md`, `tests/golden/`, `CHANGELOG.md`
- Do not commit downloaded icons, generated outputs, archives, or dependency directories. — `.gitignore`, `AGENTS.md`
- Deploy with GitHub OIDC and short-lived credentials; do not use a JSON service-account key or Cloud Build source deployment. — `.github/workflows/deploy-mcp.yml`, `docs/mcp_deployment.md`
- Keep agent-sync text identical across `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `.github/copilot-instructions.md`; store skills only under `C:\Users\Bharath\globalskills`. — Agent sync sections

## Open items

- Complete the first Terraform reconciliation and confirm the GCS backend state includes the workload-identity provider; then configure the GitHub Actions variables documented in `docs/mcp_deployment.md`. — maintainer
- Push the uncommitted deployment and marketplace changes, then run the Deploy MCP workflow to create the first Cloud Run revision and record its `/mcp` endpoint. — maintainer
- Replace the marketplace package placeholder access instructions with the deployed endpoint and complete the authenticated Agensi creator/listing workflow. — maintainer
- Open representative VSDX files in Visio and record visual verification. — maintainer with Visio access; `docs/maintainer_guide.md`

## Next actions

- Run `terraform -chdir=infra/terraform plan` using the GCS backend, resolve any remaining imports/drift, and commit `.terraform.lock.hcl` files. — maintainer
- Configure GitHub Actions repository variables, push the deployment code, and verify image build, Terraform apply, and the public MCP endpoint. — maintainer
- Before submitting the Agensi listing, decide whether it is free, one-time paid, or subscription, and complete the public creator profile. — product owner
