"""Check first-use prerequisites and optionally fetch icons or install Node helpers."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .download_icons import main as download_icons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icons", action="store_true", help="download vendor icons")
    parser.add_argument("--pdf", action="store_true", help="install optional Node PDF helpers")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or newer is required")
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}: ready")
    if args.icons and download_icons([]) != 0:
        return 1
    if args.pdf:
        node = Path(__file__).resolve().parent.parent / "node"
        try:
            subprocess.run(["npm", "ci"], cwd=node, check=True)
        except (OSError, subprocess.CalledProcessError):
            print("Node helpers unavailable; install Node.js 20+, then run cd node && npm ci",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
