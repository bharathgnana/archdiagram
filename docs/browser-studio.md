# Browser studio

The hosted MCP server also serves the browser studio at `/`. Its colors and
Firebase sign-in approach are inspired by the Knowledge Forge interface.
The studio uses email-link sign-in and never restricts sign-in to one domain.
Email login does **not** confer a paid entitlement. Browser rendering requires
both a valid, verified-email Identity Platform token (checked server-side) and
a buyer's API key. The same active-key checks and monthly quota apply to MCP
clients, which use `/mcp` directly with their API key.
The key is kept in the page's password field, not browser storage.

## Configuration before release

1. Configure Identity Platform / Firebase Authentication for the **same project
   as this service**, enable email/password and email-link sign-in, configure a
   suitable email sender, and add the final website domain to its authorized
   domains. Follow [Firebase's email-link setup](https://firebase.google.com/docs/auth/web/email-link-auth).
2. Set `ARCHDIAGRAM_FIREBASE_API_KEY` to that project's public Firebase web API
   key and `ARCHDIAGRAM_AUTH_DOMAIN` to its auth domain. Set
   `GOOGLE_CLOUD_PROJECT` to the same project. The first two values are public
   client configuration, not service-account credentials or API-key peppers.
   Without them the page explicitly says sign-in is not configured.
3. Make the service reachable only after reviewing Cloud Run ingress and invoker
   settings. `/mcp` must remain in API-key mode. An API key is independently
   sufficient to use MCP. There is not yet a verified association between a
   signed-in email and a buyer's key.
4. Issue buyer keys only after independently verifying their subscription;
   Agensi billing synchronization and self-service key provisioning are not
   yet connected. Do not grant access just because an email address signs in.

Render requests count against the key's existing monthly quota. SVG can be
previewed in a sandboxed frame; the other supported formats can be downloaded.
PDF is omitted because the current hosted container lacks its dependencies.
