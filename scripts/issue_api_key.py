"""Issue a buyer-specific key for the hosted ArchDiagram MCP.

Run this only from an administrator workstation authenticated with gcloud. The
plaintext key is printed once; Firestore stores only a keyed digest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mcp_server.access import DEFAULT_MONTHLY_LIMIT, issue_api_key, key_digest


def access_token() -> str:
    return subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue an ArchDiagram MCP buyer API key")
    parser.add_argument("--buyer", required=True, help="Buyer reference, such as their Agensi purchase ID")
    parser.add_argument("--monthly-limit", type=int, default=DEFAULT_MONTHLY_LIMIT)
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--database", default=os.environ.get("ARCHDIAGRAM_FIRESTORE_DATABASE", "(default)"))
    args = parser.parse_args()
    if not args.project:
        parser.error("--project or GOOGLE_CLOUD_PROJECT is required")
    if args.monthly_limit < 1:
        parser.error("--monthly-limit must be positive")
    pepper = os.environ.get("ARCHDIAGRAM_API_KEY_PEPPER", "")
    if not pepper:
        parser.error("ARCHDIAGRAM_API_KEY_PEPPER must be set")

    key = issue_api_key()
    now = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    fields = {
        "active": {"booleanValue": True},
        "buyerReference": {"stringValue": args.buyer},
        "createdAt": {"timestampValue": now},
        "monthlyLimit": {"integerValue": str(args.monthly_limit)},
        "secretHash": {"stringValue": key_digest(key.secret, pepper)},
        "usageCount": {"integerValue": "0"},
        "usageMonth": {"stringValue": ""},
    }
    document_id = urllib.parse.quote(key.key_id, safe="")
    url = (
        f"https://firestore.googleapis.com/v1/projects/{urllib.parse.quote(args.project, safe='')}"
        f"/databases/{urllib.parse.quote(args.database, safe='()')}/documents/api_keys/{document_id}"
    )
    request = urllib.request.Request(
        url,
        data=json.dumps({"fields": fields}, separators=(",", ":")).encode("utf-8"),
        method="PATCH",
        headers={"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15):  # nosec B310 - fixed Google API origin
        pass
    print("Give this key to the buyer exactly once. It cannot be recovered later:")
    print(key.value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
