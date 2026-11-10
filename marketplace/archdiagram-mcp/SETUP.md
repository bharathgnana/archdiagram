# Connect Architecture Diagram MCP

The Agensi connector is free. Hosted access is a separate paid service operated
by Bharath Adapa and billed directly through Razorpay. Agensi does not host the
server or manage hosted subscriptions.

1. Open https://archdiagram-mcp-moryq375tq-el.a.run.app/ and check payment
   availability, monthly price, currency, and quota before subscribing.
2. Sign in using the email link. If payments are unavailable, check back later;
   the free connector alone does not grant access.
3. Choose Subscribe with Razorpay and complete the provider's checkout.
4. Return to the studio and choose Refresh payment status. A mandate or card
   authorization alone does not activate access; a captured paid invoice does.
5. Create API key and save the key in your agent's secret settings. It is shown
   once. Replacing a key invalidates its predecessor and preserves quota usage.
6. Adapt `mcp-config.example.json` to your MCP client. The example uses an
   environment variable placeholder; your client must support its expansion or
   provide its own secret mechanism. Never share a configuration containing a
   real key. Restart or reconnect the client after configuration changes.

Endpoint: `https://archdiagram-mcp-moryq375tq-el.a.run.app/mcp`.
Transport: Streamable HTTP. Header: `Authorization: Bearer <personal API key>`.

The standard plan allows 1,000 MCP HTTP requests or browser renders per UTC
calendar month. Initialization and discovery requests also count. This is not
a quota of 1,000 diagrams. Quota resets on the first request of the next UTC
month. Paid access expires independently at the end of the paid billing period.

Cancel renewal from the studio; existing paid access continues until expiry.
Refunds and payment disputes can suspend access. Contact the service owner
through the listing's support channel for billing or account problems.

- HTTP 401: check the personal key, paid-through date, and whether the key was
  replaced or access suspended. Signing in by email alone does not grant access.
- HTTP 429: the monthly request quota is exhausted. Do not retry repeatedly.
- HTTP 503: the service or payment provider is temporarily unavailable. Do not
  create another subscription to work around an uncertain payment result.

Hosted exports: SVG, HTML, editable draw.io, PowerPoint, and Visio. PDF is not
currently supported by the hosted container. This connector does not include
server hosting or the server implementation.
