"""Billing trust boundaries and lifecycle behaviour; no real payments or keys."""
import contextlib
import copy
import hashlib
import hmac
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from mcp_server.access import AccessError, FirestoreQuotaStore, InvalidApiKey, MonthlyQuotaExceeded, current_month
from mcp_server.billing import (BillingApp, BillingError, BillingService, BillingSettings,
                                BillingStore, Conflict, Razorpay, account_id, encode)


SETTINGS = BillingSettings("rzp_test_example", "test-api-secret", "test-webhook-secret", "plan_example")
NOW = 1800000000


class MemoryStore:
    def __init__(self):
        self.docs = {}
        self.version = 0

    def get(self, path):
        return copy.deepcopy(self.docs.get(path, ({}, None)))

    def commit(self, updates):
        for path, _, revision in updates:
            if self.docs.get(path, ({}, None))[1] != revision:
                raise Conflict("conflict", 409)
        for path, values, _ in updates:
            self.version += 1
            self.docs[path] = (copy.deepcopy(values), str(self.version))


class Provider(Razorpay):
    def __init__(self):
        super().__init__(SETTINGS)
        self.calls = []
        self.sub = {"id": "sub_example", "plan_id": "plan_example", "status": "active",
                    "short_url": "https://rzp.io/rzp/example", "current_end": NOW + 9000}
        self.plan = {"period": "monthly", "interval": 1, "item": {"amount": 500, "currency": "USD"}}
        self.invoice = {"id": "inv_example", "subscription_id": "sub_example", "status": "paid",
                        "billing_start": NOW - 100, "billing_end": NOW + 100,
                        "currency": "USD", "amount_paid": 500, "amount_due": 0, "payment_id": "pay_example"}
        self.payment = {"id": "pay_example", "status": "captured", "captured": True,
                        "invoice_id": "inv_example", "currency": "USD", "amount": 500, "amount_refunded": 0}

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.startswith("plans/"):
            return copy.deepcopy(self.plan)
        if path == "subscriptions" and method == "POST":
            return {**self.sub, "status": "created"}
        if path.startswith("subscriptions/"):
            if method == "POST":
                self.sub["status"] = "cancelled"
            return copy.deepcopy(self.sub)
        if path.startswith("invoices?"):
            return {"items": [copy.deepcopy(self.invoice)]}
        if path.startswith("invoices/"):
            return copy.deepcopy(self.invoice)
        if path.startswith("payments/"):
            return copy.deepcopy(self.payment)
        raise AssertionError(path)


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch("time.time", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.store, self.provider = MemoryStore(), Provider()
        self.service = BillingService(SETTINGS, self.store, "pepper", self.provider)
        self.owner = account_id("verified-firebase-uid")
        self.path = "billing_accounts/" + self.owner

    def associate(self):
        self.store.commit([(self.path, {"subscriptionId": "sub_example", "usageMonth": current_month(),
                            "usageCount": 17}, None),
                           ("billing_subscriptions/sub_example", {"accountId": self.owner}, None)])

    def event(self, name="subscription.charged", payload=None, event_id="evt_1"):
        body = json.dumps({"event": name, "payload": payload or {
            "subscription": {"entity": {"id": "sub_example"}}}}).encode()
        signature = hmac.new(SETTINGS.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return self.service.webhook(body, signature, event_id)

    def test_checkout_associates_server_identity_and_reuses_unpaid_checkout(self):
        first = self.service.checkout(self.owner)
        self.provider.sub["status"] = "created"
        self.assertEqual(self.service.checkout(self.owner), first)
        creates = [c for c in self.provider.calls if c[0] == "POST" and c[1] == "subscriptions"]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0][2]["notes"]["archdiagram_account"], self.owner)
        self.assertEqual(self.store.get("billing_subscriptions/sub_example")[0]["accountId"], self.owner)
        self.assertNotIn("paidThrough", self.store.get(self.path)[0])

    def test_plan_mismatch_blocks_checkout(self):
        self.provider.plan["item"]["amount"] = 100
        with self.assertRaises(BillingError):
            self.service.checkout(self.owner)
        self.assertFalse(self.store.docs)

    def test_ambiguous_checkout_cannot_create_second_subscription(self):
        with patch.object(self.provider, "create", side_effect=BillingError("timeout")):
            with self.assertRaises(BillingError):
                self.service.checkout(self.owner)
        with self.assertRaises(BillingError) as error:
            self.service.checkout(self.owner)
        self.assertEqual(error.exception.status, 409)

    def test_paid_invoice_required_not_auth_or_active_status(self):
        self.associate()
        self.provider.invoice["status"] = "issued"
        self.assertFalse(self.service.status(self.owner)["active"])
        with self.assertRaises(BillingError) as error:
            self.service.rotate_key(self.owner)
        self.assertEqual(error.exception.status, 403)

    def test_invalid_payment_evidence_does_not_grant_access(self):
        for changes in ({"status": "authorized"}, {"captured": False}, {"amount_refunded": 1},
                        {"invoice_id": "inv_other"}, {"currency": "INR"}, {"amount": 100}):
            with self.subTest(changes=changes):
                provider = Provider()
                provider.payment.update(changes)
                self.assertEqual(provider.paid_through("sub_example"), 0)

    def test_future_and_expired_and_wrong_subscription_invoices_are_not_access(self):
        for changes in ({"billing_start": NOW + 1}, {"billing_end": NOW}, {"subscription_id": "sub_other"},
                        {"amount_due": 1}, {"amount_paid": 5}, {"currency": "INR"}):
            with self.subTest(changes=changes):
                provider = Provider()
                provider.invoice.update(changes)
                self.assertEqual(provider.paid_through("sub_example"), 0)

    def test_signed_webhook_retries_are_idempotent_and_do_not_reset_usage(self):
        self.associate()
        self.event()
        calls = len(self.provider.calls)
        self.event()
        self.assertEqual(calls, len(self.provider.calls))
        self.assertEqual(self.store.get(self.path)[0]["usageCount"], 17)

    def test_forged_or_modified_webhook_has_no_effect(self):
        self.associate()
        before = copy.deepcopy(self.store.docs)
        with self.assertRaises(BillingError) as error:
            self.service.webhook(b'{"event":"subscription.charged"}', "bad", "evt_forged")
        self.assertEqual(error.exception.status, 401)
        self.assertEqual(before, self.store.docs)

    def test_out_of_order_cancel_uses_live_evidence_and_preserves_paid_period(self):
        self.associate()
        self.event()
        self.provider.sub["status"] = "cancelled"
        self.event("subscription.cancelled", event_id="evt_old")
        self.assertTrue(self.service.status(self.owner)["active"])
        self.assertEqual(self.store.get(self.path)[0]["paidThrough"], NOW + 100)
        with patch("time.time", return_value=NOW + 101):
            self.assertFalse(self.service.status(self.owner)["active"])

    def test_refund_revokes_paid_access(self):
        self.associate()
        self.event()
        self.provider.payment["amount_refunded"] = 500
        self.event("refund.processed", {"refund": {"entity": {"payment_id": "pay_example"}}}, "evt_refund")
        self.assertFalse(self.service.status(self.owner)["active"])

    def test_dispute_suspension_is_not_cleared_by_later_subscription_event(self):
        self.associate()
        self.event("payment.dispute.created", {"dispute": {"entity": {"payment_id": "pay_example"}}})
        self.event(event_id="evt_later")
        self.assertFalse(self.service.status(self.owner)["active"])

    def test_concurrent_refresh_retries_without_losing_quota_update(self):
        self.associate()
        original = self.provider.paid_through
        def concurrent(sub):
            account, revision = self.store.get(self.path)
            account["usageCount"] = 18
            self.store.commit([(self.path, account, revision)])
            self.provider.paid_through = original
            return original(sub)
        self.provider.paid_through = concurrent
        self.event()
        self.assertEqual(self.store.get(self.path)[0]["usageCount"], 18)

    def test_key_rotation_keeps_quota_and_only_stores_digest(self):
        self.associate()
        first, second = self.service.rotate_key(self.owner), self.service.rotate_key(self.owner)
        self.assertNotEqual(first, second)
        account = self.store.get(self.path)[0]
        self.assertEqual(account["usageCount"], 17)
        self.assertIn(account["keyId"], second["apiKey"])
        serialized = json.dumps(self.store.docs)
        self.assertNotIn(first["apiKey"], serialized)
        self.assertNotIn(second["apiKey"], serialized)

    def test_unknown_subscription_webhook_does_not_grant_access(self):
        self.event()
        self.assertEqual(self.store.docs, {})

    def test_provider_failure_does_not_delete_prior_entitlement(self):
        self.associate()
        self.event()
        before = self.store.get(self.path)
        with patch.object(self.provider, "paid_through", side_effect=BillingError("provider unavailable")):
            with self.assertRaises(BillingError):
                self.event(event_id="evt_failed")
        self.assertEqual(before, self.store.get(self.path))

    def test_expired_terminal_subscription_can_be_replaced_without_resetting_quota(self):
        self.associate()
        self.provider.sub["status"] = "cancelled"
        self.provider.invoice["billing_end"] = NOW - 1
        with patch.object(self.provider, "create", return_value={"id": "sub_new", "short_url": "https://rzp.io/rzp/new"}):
            self.service.checkout(self.owner)
        account = self.store.get(self.path)[0]
        self.assertEqual(account["subscriptionId"], "sub_new")
        self.assertEqual(account["usageCount"], 17)

    def test_cancellation_is_idempotent(self):
        self.associate()
        self.service.cancel(self.owner)
        self.service.cancel(self.owner)
        self.assertEqual(len([c for c in self.provider.calls if c[1].endswith('/cancel')]), 1)
        self.assertTrue(self.service.status(self.owner)["cancellationRequested"])

    def test_checkout_rejects_external_redirect(self):
        self.provider.sub['short_url'] = 'https://example.com/collect-card'
        with self.assertRaises(BillingError):
            self.service.checkout(self.owner)

    def test_cancel_is_at_end_of_cycle(self):
        self.associate()
        self.service.cancel(self.owner)
        self.assertIn(("POST", "subscriptions/sub_example/cancel", {"cancel_at_cycle_end": True}), self.provider.calls)
        self.assertTrue(self.service.status(self.owner)["active"])


class PaidQuotaTests(unittest.TestCase):
    def store(self, paid_until=NOW + 100, count=0, key_id="new", suspended=False):
        class Store(FirestoreQuotaStore):
            def __init__(self):
                super().__init__("test")
                self.saved = None
            def _metadata_token(self):
                return "test"
            def _request(self, method, path, token, body=None):
                if path == ":beginTransaction":
                    return {"transaction": "transaction"}
                if method == "GET" and path.startswith("/api_keys/"):
                    fields = {"active": True, "secretHash": "digest", "billingAccountId": "owner"}
                    return {"name": "key", "updateTime": "key-rev", "fields": encode(fields)}
                if method == "GET":
                    fields = {"keyId": key_id, "paidThrough": paid_until, "suspended": suspended,
                              "usageCount": count, "usageMonth": "2027-01", "monthlyLimit": 2}
                    return {"name": "account", "updateTime": "account-rev", "fields": encode(fields)}
                self.saved = body["writes"][0]["update"]
                return {}
        return Store()

    @patch("time.time", return_value=NOW)
    def test_expired_rotated_and_suspended_keys_are_rejected(self, _):
        for settings in ({"paid_until": NOW}, {"key_id": "old"}, {"suspended": True}):
            with self.subTest(settings=settings), self.assertRaises(InvalidApiKey):
                self.store(**settings)._consume_sync("new", "digest", "2027-01")

    @patch("time.time", return_value=NOW)
    def test_quota_is_incremented_on_account_and_resets_in_new_month(self, _):
        store = self.store(count=1)
        store._consume_sync("new", "digest", "2027-01")
        self.assertEqual(store.saved["name"], "account")
        self.assertEqual(store.saved["fields"]["usageCount"]["integerValue"], "2")
        with self.assertRaises(MonthlyQuotaExceeded):
            self.store(count=2)._consume_sync("new", "digest", "2027-01")
        store = self.store(count=2)
        store._consume_sync("new", "digest", "2027-02")
        self.assertEqual(store.saved["fields"]["usageCount"]["integerValue"], "1")


class BillingRouteTests(unittest.IsolatedAsyncioTestCase):
    async def call(self, app, path, method="GET", headers=(), body=b""):
        messages = []
        async def receive():
            return {"type": "http.request", "body": body}
        async def send(message):
            messages.append(message)
        await app({"type": "http", "path": path, "method": method, "headers": list(headers)}, receive, send)
        return messages[0]["status"], json.loads(messages[-1]["body"])

    async def test_disabled_billing_and_private_configuration(self):
        app = BillingApp(None, None)
        self.assertEqual(await self.call(app, "/api/billing/config"), (200, {"enabled": False}))
        self.assertEqual((await self.call(app, "/api/billing/checkout", "POST"))[0], 503)
        service = BillingService(SETTINGS, MemoryStore(), "pepper", Provider())
        _, config = await self.call(BillingApp(None, service), "/api/billing/config")
        self.assertNotIn(SETTINGS.key_secret, json.dumps(config))
        self.assertNotIn(SETTINGS.webhook_secret, json.dumps(config))

    async def test_verified_identity_is_required_and_client_cannot_select_another_account(self):
        service = BillingService(SETTINGS, MemoryStore(), "pepper", Provider())
        app = BillingApp(None, service)
        with patch("mcp_server.billing.browser_identity", return_value=None):
            self.assertEqual((await self.call(app, "/api/billing/key", "POST"))[0], 401)
        with patch("mcp_server.billing.browser_identity", return_value={"uid": "verified", "email": "verified@example.com"}), patch.object(service, "rotate_key", return_value={"apiKey": "test"}) as rotate:
            self.assertEqual((await self.call(app, "/api/billing/key", "POST", body=b'{"uid":"victim"}'))[0], 200)
            rotate.assert_called_once_with(account_id("verified"))


class BillingPersistenceTests(unittest.TestCase):
    def test_commit_uses_atomic_revision_preconditions(self):
        store = BillingStore('project')
        with patch.object(store, '_metadata_token', return_value='token'), patch.object(store, '_request', return_value={}) as request:
            store.commit([('billing_accounts/account', {'usageCount': 9}, 'revision'),
                          ('billing_events/event', {'processedAt': NOW}, None)])
        writes = request.call_args.args[3]['writes']
        self.assertEqual(writes[0]['currentDocument'], {'updateTime': 'revision'})
        self.assertEqual(writes[1]['currentDocument'], {'exists': False})
        self.assertEqual(writes[0]['update']['name'], 'projects/project/databases/(default)/documents/billing_accounts/account')

    def test_missing_document_is_distinct_from_storage_outage(self):
        store = BillingStore('project')
        with patch.object(store, '_metadata_token', return_value='token'):
            for status in (404, 503):
                error = urllib.error.HTTPError('https://firestore.googleapis.com', status, 'error', {}, io.BytesIO(b''))
                with patch('urllib.request.urlopen', side_effect=error):
                    if status == 404:
                        self.assertEqual(store.get('billing_accounts/account'), ({}, None))
                    else:
                        with self.assertRaises(AccessError):
                            store.get('billing_accounts/account')


class ReconciliationTests(unittest.TestCase):
    def test_default_audit_is_read_only(self):
        from scripts import reconcile_billing
        store = MemoryStore()
        owner = account_id('owner')
        account = {'subscriptionId': 'sub_example', 'paidThrough': 0, 'usageCount': 31}
        store.commit([('billing_accounts/' + owner, account, None)])
        store.accounts = lambda: iter([(owner, account.copy())])
        service = BillingService(SETTINGS, store, '', Provider())
        before = copy.deepcopy(store.docs)
        output = io.StringIO()
        with patch('sys.argv', ['reconcile_billing.py', '--project', 'project']), patch.object(reconcile_billing.BillingSettings, 'from_env', return_value=SETTINGS), patch.object(reconcile_billing, 'AdminStore', return_value=store), patch.object(reconcile_billing, 'BillingService', return_value=service), patch('time.time', return_value=NOW), contextlib.redirect_stdout(output):
            self.assertEqual(reconcile_billing.main(), 0)
        self.assertEqual(store.docs, before)
        self.assertEqual(json.loads(output.getvalue())['mode'], 'dry-run')


if __name__ == "__main__":
    unittest.main()
