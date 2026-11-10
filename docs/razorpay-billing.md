# Direct hosted billing with Razorpay

Agensi distributes a **free connector**. Hosted access is bought directly from
the service owner through Razorpay, independently of Agensi. There is no Agensi
buyer-ID or subscription-status dependency.

Billing is disabled by default. The studio reports payments unavailable until
the settings below are connected. Do not enable live payments before a full
test-mode purchase, webhook delivery, key issuance, quota check, cancellation,
and refund have been verified on a staging deployment.

## Account and plan setup

1. Enable Razorpay Subscriptions on the merchant account. Create a monthly plan
   with interval **1** and the approved price. The existing product price is
   **USD 5.00/month**, represented as `500` minor units. International currency
   subscriptions require an eligible card flow; **UPI requires INR**. If choosing
   INR, agree the price explicitly rather than silently converting dollars.
2. Use a dedicated staging Cloud Run service/project with test-mode credentials
   first. Keep test and live plans, API secrets, webhook secrets, databases, and
   buyer keys separate. This implementation creates at most 120 monthly cycles
   and discloses that limit before checkout.
3. Store the Razorpay API key secret and a separate, randomly generated webhook
   secret in Google Secret Manager. Recommended names:
   `archdiagram-razorpay-key-secret` and
   `archdiagram-razorpay-webhook-secret`. Add secret **versions** securely; do not
   put their values in Git, chat, GitHub variables, Terraform variables/state,
   command-line arguments, or a shared skill ZIP.
4. As a Google Cloud administrator, grant the runtime service account secret
   accessor on just these two secrets. Terraform declares those scoped grants,
   but initial provisioning requires an administrator able to set secret IAM;
   the existing deployment identity is intentionally not a secret administrator.
   Run the administrative Terraform bootstrap with the **current container image
   supplied**; omitting it after service creation can remove the service.
5. Configure a Razorpay webhook at
   `https://<service-origin>/api/billing/webhook`, using the dedicated secret.
   Subscribe to `subscription.authenticated`, `subscription.activated`,
   `subscription.charged`, `subscription.pending`, `subscription.halted`,
   `subscription.paused`, `subscription.resumed`, `subscription.cancelled`,
   `subscription.completed`, `subscription.expired`, `refund.processed`, and
   `payment.dispute.created`. Verify which events your account exposes. Disputes
   suspend access for administrator review; a later subscription event does not
   clear a dispute suspension.

## Deployment settings

Set these **GitHub repository variables**, which the deploy workflow maps to
Terraform. These values are identifiers and public configuration, not secrets.

| GitHub variable | Value |
| --- | --- |
| `BILLING_ENABLED` | `true` only after staging validation |
| `RAZORPAY_KEY_ID` | Merchant key ID for the intended mode |
| `RAZORPAY_PLAN_ID` | Monthly plan ID, `plan_…` |
| `RAZORPAY_KEY_SECRET_NAME` | Secret Manager API-secret name |
| `RAZORPAY_WEBHOOK_SECRET_NAME` | Secret Manager webhook-secret name |
| `PLAN_AMOUNT` | Minor units, default `500` |
| `PLAN_CURRENCY` | Default `USD`; use `INR` for an approved INR plan |

Existing `FIREBASE_WEB_API_KEY` and `FIREBASE_AUTH_DOMAIN` must identify the same
Identity Platform project as `GCP_PROJECT_ID`. Enable verified email-link login
and authorize the deployment domain as described in [browser-studio.md](browser-studio.md).

The corresponding runtime settings are `ARCHDIAGRAM_BILLING_ENABLED`,
`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`,
`RAZORPAY_PLAN_ID`, `ARCHDIAGRAM_PLAN_AMOUNT`, `ARCHDIAGRAM_PLAN_CURRENCY`, and
`ARCHDIAGRAM_MONTHLY_LIMIT`. The standard quota remains 1,000 requests per UTC
calendar month. Terraform injects secret values from Secret Manager at runtime.

## Customer flow

1. Load the free Agensi connector and open the hosted studio.
2. Verify the displayed price and quota, sign in with a verified email, and
   choose Subscribe with Razorpay. Checkout is hosted on Razorpay's domain.
3. Return to the studio and refresh payment status. The server fetches current
   subscription and invoice records plus the invoice's captured payment.
4. Create an API key after a captured, unrefunded payment has been confirmed.
   Save it immediately in the MCP client's secret settings. The plaintext is
   returned only to the authenticated account over HTTPS and is never persisted.
5. Configure the `/mcp` endpoint with the Bearer key. Replace a lost key from the
   same account; the old key stops working and the account quota is preserved.
6. Cancel renewal from the studio. The request uses `cancel_at_cycle_end: true`.
   Paid access continues until its invoice's billing end. Expiry is enforced on
   each request even if an expiry webhook never arrives.

## Trust boundaries and recovery

- Identity Platform verifies the ID token server-side; its stable `localId`
  selects the account. Client-supplied emails, UIDs, subscription IDs, receipts,
  and payment callbacks cannot select an account or grant access.
- Accounts, subscription-to-account associations, webhook audit records, and
  key hashes are server-only Firestore collections: `billing_accounts`,
  `billing_subscriptions`, `billing_events`, and `api_keys`. Do not allow client
  SDK writes to these collections. Browser code uses authenticated server routes.
- Webhooks require a valid HMAC-SHA256 over the exact raw request bytes and an
  event ID. Duplicate IDs are acknowledged without mutations. New events trigger
  an authoritative re-fetch; Firestore revision preconditions prevent a stale
  response from overwriting a newer billing or quota update.
- A subscription's `active` state, `current_end`, or mandate authorization is
  insufficient. Access requires a paid monthly invoice in the current time
  window and its captured payment, with correct currency, sufficient amount,
  matching invoice, and no refund. Partial refunds also suspend the affected
  invoice's access. A payment dispute holds the account for review.
- Billing outages return an error and preserve prior records. They neither
  extend nor delete previously confirmed paid-through dates. Monitor failed
  webhook deliveries in Razorpay and replay them after recovery. Refund and
  dispute changes depend on webhook delivery or a status refresh; monitor this
  rather than claiming instantaneous enforcement during an outage.
- Run `python scripts/reconcile_billing.py --project <project>` from a trusted
  administrator workstation for a dry-run audit, with the Razorpay environment
  settings loaded securely. Review its report, then add `--apply` to reconcile
  verified paid-through dates. It preserves quota and dispute holds, reports
  failed verification, and never issues keys. Run this regularly alongside
  webhook monitoring; this command does not install a scheduler.
- Checkout creation is reserved before the provider POST. A timeout or storage
  failure can leave a pending `checkoutIntent`; this blocks automatic retries
  rather than risking a duplicate recurring charge. Inspect the provider's
  subscription notes (`archdiagram_account`, `archdiagram_intent`) against the
  persisted intent. Associate the verified subscription atomically or cancel
  the orphan before clearing the reservation. Never clear an uncertain
  reservation without checking Razorpay first.
- Terminal subscriptions can be replaced only after paid access has expired;
  usage counters remain on the account. Old subscription events cannot restore
  an old subscription's access.
- Administrator-issued legacy keys retain the existing manual access policy;
  they are not automatically associated with or billed to a signed-in account.
  Audit them separately before claiming all hosted keys require direct payment.

## Validation

Run `python -m unittest tests.test_billing tests.test_hosted_access tests.test_browser_ui`
and the repository suite. On staging, use Razorpay test mode to exercise an
actual checkout, webhook signature, paid invoice, personal key, replacement,
refund, cancellation, and expired-access response. Automated unit tests mock
the provider; they do not establish merchant activation or a successful live
payment. No real customer is charged by the test suite.

API references:
[create subscription](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/),
[fetch subscription](https://razorpay.com/docs/api/payments/subscriptions/fetch-subscription-id),
[subscription invoices](https://razorpay.com/docs/api/payments/subscriptions/fetch-invoices),
[webhook validation and retries](https://razorpay.com/docs/webhooks/validate-test/),
[cancel at cycle end](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/),
[supported currency flows](https://razorpay.com/docs/payments/subscriptions/faqs/).
