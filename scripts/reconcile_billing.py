"""Audit direct Razorpay access; dry-run unless --apply is explicitly passed.

Use administrator gcloud credentials on a trusted workstation. API secrets are
read from environment, never command arguments. No keys or emails are printed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mcp_server.billing import BillingService, BillingSettings, BillingStore, decode


class AdminStore(BillingStore):
    def _metadata_token(self):
        executable = shutil.which("gcloud.cmd") or shutil.which("gcloud")
        if not executable:
            raise RuntimeError("gcloud is required for administrator reconciliation")
        return subprocess.check_output([executable, "auth", "print-access-token"], text=True).strip()

    def accounts(self):
        page = ""
        while True:
            query = urllib.parse.urlencode({"pageSize": 100, "pageToken": page})
            result = self._request("GET", "/billing_accounts?" + query, self._metadata_token())
            for document in result.get("documents", []):
                yield document["name"].rsplit("/", 1)[1], decode(document)
            page = result.get("nextPageToken", "")
            if not page:
                return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"), required=not os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--apply", action="store_true", help="Apply current provider evidence with revision checks; default is dry-run")
    args = parser.parse_args()
    settings = BillingSettings.from_env()
    if not settings:
        parser.error("Set ARCHDIAGRAM_BILLING_ENABLED=true and the Razorpay environment settings")
    store = AdminStore(args.project, os.environ.get("ARCHDIAGRAM_FIRESTORE_DATABASE", "(default)"))
    service = BillingService(settings, store, "")  # Reconciliation never issues keys.
    failed = 0
    for owner, account in store.accounts():
        try:
            if not account.get("subscriptionId"):
                print(json.dumps({"accountReference": owner, "result": "manual-checkout-recovery-required"}))
                failed += 1
                continue
            if args.apply:
                current = service.refresh(owner)
                paid, state = current.get("paidThrough", 0), current.get("status", "unknown")
            else:
                sub = service.provider.subscription(account["subscriptionId"])
                if sub.get("plan_id") != settings.plan_id:
                    raise RuntimeError("plan mismatch")
                paid, state = service.provider.paid_through(account["subscriptionId"]), sub.get("status", "unknown")
            print(json.dumps({"accountReference": owner, "mode": "applied" if args.apply else "dry-run",
                              "previousPaidThrough": account.get("paidThrough", 0), "verifiedPaidThrough": paid,
                              "providerStatus": state, "suspended": account.get("suspended", False)}))
        except Exception:
            # Exception messages can include third-party details. Preserve state on error.
            print(json.dumps({"accountReference": owner, "result": "verification-failed-no-access-change"}))
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
