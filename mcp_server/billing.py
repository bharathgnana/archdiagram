"""Direct Razorpay subscriptions. No card details or plaintext keys are stored.

Agensi distributes the free connector; it is never an entitlement source.
Firestore compare-and-swap writes prevent billing from overwriting quota usage.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .access import AccessError, FirestoreQuotaStore, current_month, issue_api_key, key_digest
from .web import browser_identity


class BillingError(RuntimeError):
    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


class Conflict(BillingError):
    pass


def identifier(value: str, prefix: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9]+", value):
        raise BillingError("Invalid payment identifier", 400)
    return value


def account_id(uid: str) -> str:
    return hashlib.sha256(uid.encode()).hexdigest()


def checkout_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != "rzp.io" or parsed.username or parsed.password:
        raise BillingError("Payment provider returned an invalid checkout URL")
    return value


@dataclass(frozen=True)
class BillingSettings:
    key_id: str
    key_secret: str
    webhook_secret: str
    plan_id: str
    amount: int = 500  # minor currency units
    currency: str = "USD"
    monthly_limit: int = 1000
    total_count: int = 120

    @classmethod
    def from_env(cls):
        if os.environ.get("ARCHDIAGRAM_BILLING_ENABLED", "false") != "true":
            return None
        names = ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "RAZORPAY_PLAN_ID")
        if not all(os.environ.get(name) for name in names):
            raise RuntimeError("Razorpay billing is enabled but its credentials or plan are missing")
        result = cls(*(os.environ[name] for name in names),
                     amount=int(os.environ.get("ARCHDIAGRAM_PLAN_AMOUNT", "500")),
                     currency=os.environ.get("ARCHDIAGRAM_PLAN_CURRENCY", "USD"),
                     monthly_limit=int(os.environ.get("ARCHDIAGRAM_MONTHLY_LIMIT", "1000")))
        identifier(result.plan_id, "plan_")
        if result.amount < 1 or result.monthly_limit < 1 or not re.fullmatch(r"[A-Z]{3}", result.currency):
            raise RuntimeError("Invalid Razorpay plan settings")
        return result

    def public(self):
        return {"enabled": True, "provider": "Razorpay", "amount": self.amount,
                "currency": self.currency, "monthlyLimit": self.monthly_limit,
                "totalCycles": self.total_count, "testMode": self.key_id.startswith("rzp_test_")}


class Razorpay:
    def __init__(self, settings: BillingSettings):
        self.settings = settings

    def request(self, method: str, path: str, body=None):
        auth = base64.b64encode(f"{self.settings.key_id}:{self.settings.key_secret}".encode()).decode()
        request = urllib.request.Request("https://api.razorpay.com/v1/" + path,
                                         data=None if body is None else json.dumps(body).encode(),
                                         headers={"Authorization": "Basic " + auth,
                                                  "Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
                if not isinstance(result, dict):
                    raise ValueError("Invalid response")
                return result
        except (OSError, ValueError) as exc:
            # Provider error bodies can contain customer details; never relay them.
            raise BillingError("Razorpay is unavailable. Please try again later.") from exc

    def validate_plan(self):
        plan = self.request("GET", "plans/" + identifier(self.settings.plan_id, "plan_"))
        item = plan.get("item", {})
        if (plan.get("period") != "monthly" or plan.get("interval") != 1
                or item.get("amount") != self.settings.amount or item.get("currency") != self.settings.currency):
            raise BillingError("The payment plan does not match the advertised monthly price")

    def subscription(self, sub_id):
        return self.request("GET", "subscriptions/" + identifier(sub_id, "sub_"))

    def create(self, owner: str, intent: str):
        return self.request("POST", "subscriptions", {"plan_id": self.settings.plan_id,
                            "total_count": self.settings.total_count, "quantity": 1,
                            "customer_notify": True, "expire_by": int(time.time()) + 86400,
                            "notes": {"archdiagram_account": owner, "archdiagram_intent": intent}})

    def cancel(self, sub_id):
        return self.request("POST", "subscriptions/" + identifier(sub_id, "sub_") + "/cancel",
                            {"cancel_at_cycle_end": True})

    def paid_through(self, sub_id: str) -> int:
        """Only a paid monthly invoice backed by a captured, unrefunded payment.

        Authorization payments and a subscription's current_end are insufficient.
        Pagination is bounded by the subscription's finite 120 monthly cycles.
        """
        now, paid_until = int(time.time()), 0
        for skip in (0, 100):
            query = urllib.parse.urlencode({"subscription_id": identifier(sub_id, "sub_"),
                                           "count": 100, "skip": skip})
            items = self.request("GET", "invoices?" + query).get("items")
            if not isinstance(items, list):
                raise BillingError("Razorpay returned incomplete invoice records")
            for invoice in items:
                start, end = invoice.get("billing_start"), invoice.get("billing_end")
                if (invoice.get("subscription_id") != sub_id or invoice.get("status") != "paid"
                        or not isinstance(start, int) or not isinstance(end, int)
                        or not start <= now < end or invoice.get("currency") != self.settings.currency
                        or invoice.get("amount_paid", 0) < self.settings.amount or invoice.get("amount_due") != 0):
                    continue
                payment = self.request("GET", "payments/" + identifier(invoice.get("payment_id"), "pay_"))
                if (payment.get("status") == "captured" and payment.get("captured") is True
                        and payment.get("invoice_id") == invoice.get("id")
                        and payment.get("currency") == self.settings.currency
                        and payment.get("amount", 0) >= self.settings.amount
                        and payment.get("amount_refunded", 0) == 0):
                    paid_until = max(paid_until, end)
            if len(items) < 100:
                return paid_until
        raise BillingError("Invoice history requires manual reconciliation")


def encode(fields):
    result = {}
    for name, value in fields.items():
        if isinstance(value, bool):
            result[name] = {"booleanValue": value}
        elif isinstance(value, int):
            result[name] = {"integerValue": str(value)}
        elif isinstance(value, str):
            result[name] = {"stringValue": value}
        else:
            raise TypeError(f"Unsupported billing field: {name}")
    return result


def decode(document):
    result = {}
    for name, value in document.get("fields", {}).items():
        if "stringValue" in value:
            result[name] = value["stringValue"]
        elif "integerValue" in value:
            result[name] = int(value["integerValue"])
        elif "booleanValue" in value:
            result[name] = value["booleanValue"]
    return result


class BillingStore(FirestoreQuotaStore):
    """REST persistence with atomic preconditions on every modified document."""
    def get(self, path):
        try:
            doc = self._request("GET", "/" + path, self._metadata_token())
            return decode(doc), doc["updateTime"]
        except AccessError as exc:
            if isinstance(exc.__cause__, urllib.error.HTTPError) and exc.__cause__.code == 404:
                return {}, None
            raise

    def commit(self, updates):
        writes = []
        for path, values, revision in updates:
            writes.append({"update": {"name": self._base_url.split("/v1/", 1)[1] + "/" + path,
                                      "fields": encode(values)},
                           "currentDocument": {"updateTime": revision} if revision else {"exists": False}})
        try:
            self._request("POST", ":commit", self._metadata_token(), {"writes": writes})
        except AccessError as exc:
            cause = exc.__cause__
            if isinstance(cause, urllib.error.HTTPError) and cause.code in (409, 412, 400):
                raise Conflict("Account changed. Refresh and try again.", 409) from exc
            raise


class BillingService:
    def __init__(self, settings, store, pepper, provider=None):
        self.settings, self.store, self.pepper = settings, store, pepper
        self.provider = provider or Razorpay(settings)

    def refresh(self, owner: str, event_id: str = "", dispute: bool = False, event_name: str = ""):
        event_path = "billing_events/" + hashlib.sha256(event_id.encode()).hexdigest()
        for _ in range(4):
            if event_id and self.store.get(event_path)[1]:
                return self.store.get("billing_accounts/" + owner)[0]
            account, revision = self.store.get("billing_accounts/" + owner)
            sub_id = account.get("subscriptionId")
            if not sub_id:
                return account
            subscription = self.provider.subscription(sub_id)
            if subscription.get("id") != sub_id or subscription.get("plan_id") != self.settings.plan_id:
                raise BillingError("Subscription plan mismatch. Contact support.")
            # Re-fetch authoritative state on every event, including old/retried events.
            # Read revision BEFORE remote calls so stale work cannot overwrite a newer refresh.
            paid_until = self.provider.paid_through(sub_id)
            account.update({"paidThrough": paid_until, "status": subscription.get("status", "unknown"),
                            "monthlyLimit": self.settings.monthly_limit, "billingCheckedAt": int(time.time()),
                            "suspended": bool(account.get("suspended")) or dispute})
            updates = [("billing_accounts/" + owner, account, revision)]
            if event_id:
                updates.append((event_path, {"accountId": owner, "subscriptionId": sub_id,
                                            "event": event_name, "paidThrough": paid_until,
                                            "processedAt": int(time.time())}, None))
            try:
                self.store.commit(updates)
                return account
            except Conflict:
                continue
        raise BillingError("Account is busy. Please refresh and try again.", 409)

    def status(self, owner):
        account = self.refresh(owner)
        now = int(time.time())
        return {"status": account.get("status", "none"), "paidThrough": account.get("paidThrough", 0),
                "active": account.get("paidThrough", 0) > now and not account.get("suspended", False),
                "hasKey": bool(account.get("keyId")),
                "cancellationRequested": bool(account.get("cancellationRequested")),
                "usageCount": account.get("usageCount", 0) if account.get("usageMonth") == current_month() else 0,
                "monthlyLimit": self.settings.monthly_limit}

    def checkout(self, owner):
        self.provider.validate_plan()
        path = "billing_accounts/" + owner
        account, revision = self.store.get(path)
        if account.get("subscriptionId"):
            existing_sub_id = account["subscriptionId"]
            subscription = self.provider.subscription(existing_sub_id)
            if subscription.get("status") in ("created", "authenticated"):
                return {"checkoutUrl": checkout_url(subscription.get("short_url", ""))}
            if subscription.get("status") not in ("cancelled", "completed", "expired"):
                raise BillingError("A subscription already exists. Refresh its status or contact support.", 409)
            account = self.refresh(owner)
            if account.get("paidThrough", 0) > int(time.time()) or account.get("suspended"):
                raise BillingError("The previous subscription still has paid access or requires support.", 409)
            account, revision = self.store.get(path)
            if account.get("subscriptionId") != existing_sub_id:
                raise BillingError("Checkout changed. Refresh before retrying.", 409)
            account.update({"previousSubscriptionId": account["subscriptionId"],
                            "subscriptionId": "", "checkoutIntent": ""})
        if account.get("checkoutIntent"):
            raise BillingError("Checkout creation is awaiting reconciliation. Contact support before retrying.", 409)
        intent = secrets.token_hex(16)
        account.update({"checkoutIntent": intent, "checkoutCreatedAt": int(time.time())})
        account["cancellationRequested"] = False
        self.store.commit([(path, account, revision)])
        # Do not retry an ambiguous POST: Razorpay may already have created it.
        subscription = self.provider.create(owner, intent)
        sub_id = identifier(subscription.get("id"), "sub_")
        url = checkout_url(subscription.get("short_url", ""))
        account, revision = self.store.get(path)
        if account.get("checkoutIntent") != intent or account.get("subscriptionId"):
            raise BillingError("Checkout association requires support")
        account.update({"subscriptionId": sub_id, "status": "created"})
        self.store.commit([(path, account, revision),
                           ("billing_subscriptions/" + sub_id, {"accountId": owner}, None)])
        return {"checkoutUrl": url}

    def cancel(self, owner):
        account, _ = self.store.get("billing_accounts/" + owner)
        if not account.get("subscriptionId"):
            raise BillingError("No subscription to cancel", 409)
        sub_id = account["subscriptionId"]
        if not account.get("cancellationRequested"):
            self.provider.cancel(sub_id)
        for _ in range(4):
            account, revision = self.store.get("billing_accounts/" + owner)
            if account.get("subscriptionId") != sub_id:
                raise BillingError("Subscription changed. Refresh its status.", 409)
            account["cancellationRequested"] = True
            try:
                self.store.commit([("billing_accounts/" + owner, account, revision)])
                break
            except Conflict:
                continue
        else:
            raise BillingError("Cancellation sent. Refresh status before retrying.", 409)
        self.refresh(owner)
        return {"message": "Cancellation requested for the end of the billing cycle. Paid access continues until its expiry."}

    def rotate_key(self, owner):
        self.refresh(owner)
        account, revision = self.store.get("billing_accounts/" + owner)
        if account.get("paidThrough", 0) <= int(time.time()) or account.get("suspended"):
            raise BillingError("A confirmed subscription payment is required before issuing a key", 403)
        key = issue_api_key()
        account["keyId"] = key.key_id
        self.store.commit([("billing_accounts/" + owner, account, revision),
                           ("api_keys/" + key.key_id, {"active": True, "billingAccountId": owner,
                            "secretHash": key_digest(key.secret, self.pepper),
                            "createdAtEpoch": int(time.time())}, None)])
        # All old keys become invalid via account.keyId. Usage stays on the account.
        return {"apiKey": key.value}

    def webhook(self, body: bytes, signature: str, event_id: str):
        expected = hmac.new(self.settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise BillingError("Invalid webhook signature", 401)
        if not event_id or len(event_id) > 256:
            raise BillingError("Webhook event ID required", 400)
        event = json.loads(body)
        name, payload = event.get("event", ""), event.get("payload", {})
        sub_id = payload.get("subscription", {}).get("entity", {}).get("id")
        if not sub_id and (name == "refund.processed" or name.startswith("payment.dispute.")):
            entity = payload.get("refund", {}).get("entity", {}) or payload.get("dispute", {}).get("entity", {})
            payment = self.provider.request("GET", "payments/" + identifier(entity.get("payment_id"), "pay_"))
            if not payment.get("invoice_id"):
                return {"received": True}  # Unrelated to a subscription.
            invoice = self.provider.request("GET", "invoices/" + identifier(payment["invoice_id"], "inv_"))
            sub_id = invoice.get("subscription_id")
        if sub_id:
            identifier(sub_id, "sub_")
            mapping, _ = self.store.get("billing_subscriptions/" + sub_id)
            if mapping.get("accountId"):
                owner = mapping["accountId"]
                account, _ = self.store.get("billing_accounts/" + owner)
                if account.get("subscriptionId") == sub_id or name.startswith("payment.dispute."):
                    self.refresh(owner, event_id, dispute=name.startswith("payment.dispute."), event_name=name)
        return {"received": True}


class BillingApp:
    """ASGI endpoints outside the MCP quota gate, with verified account identity."""
    def __init__(self, app, service):
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        path, method = scope.get("path", ""), scope.get("method", "")
        if scope["type"] != "http" or not path.startswith("/api/billing/"):
            return await self.app(scope, receive, send)
        from .web import BrowserApp
        respond = BrowserApp.respond_json
        if path == "/api/billing/config" and method == "GET":
            return await respond(send, 200, self.service.settings.public() if self.service else {"enabled": False})
        if not self.service:
            return await respond(send, 503, {"error": "Payments are not configured yet"})
        headers = {k.lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        try:
            if path == "/api/billing/webhook" and method == "POST":
                body = bytearray()
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    body.extend(event.get("body", b""))
                    if len(body) > 256 * 1024:
                        raise BillingError("Webhook too large", 413)
                    if not event.get("more_body", False):
                        break
                result = await asyncio.to_thread(self.service.webhook, bytes(body),
                              headers.get(b"x-razorpay-signature", ""), headers.get(b"x-razorpay-event-id", ""))
            else:
                routes = {("GET", "/api/billing/status"): self.service.status,
                          ("POST", "/api/billing/checkout"): self.service.checkout,
                          ("POST", "/api/billing/cancel"): self.service.cancel,
                          ("POST", "/api/billing/key"): self.service.rotate_key}
                action = routes.get((method, path))
                if not action:
                    raise BillingError("Unknown billing endpoint or method", 404)
                # A custom header prevents form-based CSRF; CORS is not enabled.
                identity = await asyncio.to_thread(browser_identity, headers.get(b"x-firebase-token", ""),
                                                   os.environ.get("ARCHDIAGRAM_FIREBASE_API_KEY", ""))
                if not identity:
                    raise BillingError("Verified email sign-in required", 401)
                result = await asyncio.to_thread(action, account_id(identity["uid"]))
            return await respond(send, 200, result)
        except BillingError as exc:
            return await respond(send, exc.status, {"error": str(exc)})
        except (ValueError, TypeError, AttributeError, KeyError):
            return await respond(send, 400, {"error": "Invalid billing request"})
        except AccessError:
            return await respond(send, 503, {"error": "Billing storage is temporarily unavailable"})
