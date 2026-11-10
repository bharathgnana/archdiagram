"""FastMCP registration for the SDK-free diagram tool functions."""

from __future__ import annotations

import os

from .access import ApiKeyGate, hosted_access_settings
from .web import BrowserApp
from .billing import BillingApp, BillingService, BillingSettings, BillingStore

from .tools import (
    catalog_resource,
    choose_template,
    describe_architecture,
    describe_diagram,
    generate_diagram,
    get_catalog_info,
    get_diagram_template,
    list_catalog,
    list_icons,
    list_templates,
    render_diagram,
    resolve_service,
    schema_resource,
    search_catalog,
    validate_spec,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "A compatible MCP SDK (1.x) is required. Install it with:\n"
        "    pip install \"archdiagram[mcp]\""
    ) from exc

# A non-loopback host prevents FastMCP 1.x from enabling its localhost-only
# DNS-rebinding allowlist. Cloud Run supplies the external listener.
mcp = FastMCP("archdiagram", host="0.0.0.0", stateless_http=bool(os.environ.get("PORT")))

for tool in (
    validate_spec,
    render_diagram,
    search_catalog,
    list_catalog,
    choose_template,
    get_diagram_template,
    list_templates,
    list_icons,
    resolve_service,
    get_catalog_info,
    generate_diagram,
):
    mcp.tool()(tool)

mcp.resource("archdiag://schema")(schema_resource)
mcp.resource("archdiag://catalog")(catalog_resource)
mcp.prompt()(describe_diagram)
mcp.prompt()(describe_architecture)


def hosted_app():
    """Return the Cloud Run ASGI app protected by buyer-specific API keys."""
    if os.environ.get("ARCHDIAGRAM_ACCESS_MODE", "api-key") == "disabled":
        if os.environ.get("ARCHDIAGRAM_BILLING_ENABLED", "false") == "true":
            raise RuntimeError("Billing requires API-key access mode")
        return BillingApp(BrowserApp(mcp.streamable_http_app()), None)
    if os.environ.get("ARCHDIAGRAM_ACCESS_MODE", "api-key") != "api-key":
        raise RuntimeError("ARCHDIAGRAM_ACCESS_MODE must be 'disabled' or 'api-key'")
    store, pepper = hosted_access_settings()
    if not pepper:
        raise RuntimeError("ARCHDIAGRAM_API_KEY_PEPPER must be configured for hosted access")
    settings = BillingSettings.from_env()
    billing = None
    if settings:
        billing_store = BillingStore(os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
                                     os.environ.get("ARCHDIAGRAM_FIRESTORE_DATABASE", "(default)"))
        billing = BillingService(settings, billing_store, pepper)
    return BillingApp(BrowserApp(ApiKeyGate(mcp.streamable_http_app(), store, pepper), store, pepper), billing)


def main() -> None:
    # Stdio remains the right default for a locally configured MCP server.
    # Cloud Run provides PORT when this module is deployed as a service.
    port = os.environ.get("PORT")
    if port:
        import uvicorn

        uvicorn.run(hosted_app(), host="0.0.0.0", port=int(port))
    else:
        mcp.run()


if __name__ == "__main__":
    main()
