"""Python wrapper around the optional Node rasterise / pdf bridge.

This module shells out to ``node`` running the scripts under ``node/``. Node and
its dependencies (``@resvg/resvg-js``, ``pdfkit``, ``svg-to-pdfkit``) are an
*optional* part of the system. If they are missing, the functions here raise
:class:`NodeBridgeError` with an actionable install hint and callers fall back
(``.vsdx`` -> labelled boxes) or surface the error (``.pdf``).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess

INSTALL_HINT = (
    "Node rasterise/PDF bridge unavailable. Install Node 18+ and the bridge deps:\n"
    "    cd node && npm install\n"
    "(provides @resvg/resvg-js, pdfkit, svg-to-pdfkit)."
)

_NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "node"))


class NodeBridgeError(RuntimeError):
    """Raised when the optional Node bridge cannot be used."""


def _node_exe() -> str | None:
    return shutil.which("node")


def _has_module(module_subpath: str) -> bool:
    return os.path.isdir(os.path.join(_NODE_DIR, "node_modules", *module_subpath.split("/")))


def rasterizer_available() -> bool:
    return bool(_node_exe()) and _has_module("@resvg/resvg-js")


def pdf_bridge_available() -> bool:
    return bool(_node_exe()) and _has_module("pdfkit") and _has_module("svg-to-pdfkit")


def _run(script: str, payload: dict, *, timeout: float = 120.0) -> tuple[int, bytes, bytes]:
    node = _node_exe()
    if not node:
        raise NodeBridgeError(INSTALL_HINT)
    script_path = os.path.join(_NODE_DIR, script)
    if not os.path.isfile(script_path):
        raise NodeBridgeError(f"bridge script not found: {script_path}")
    proc = subprocess.run(
        [node, script_path],
        input=json.dumps(payload).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def rasterize_icons(items: list[dict]) -> dict[str, bytes]:
    """Rasterise a batch of SVGs to PNG bytes.

    ``items`` is a list of ``{"id": str, "svg": str, "width": int}``.
    Returns ``{id: png_bytes}`` for every item that rendered. Items that fail
    individually are simply omitted (caller can detect missing ids).
    """

    if not items:
        return {}
    if not rasterizer_available():
        raise NodeBridgeError(INSTALL_HINT)

    code, out, err = _run("rasterize.mjs", {"items": items})
    if code == 2:
        raise NodeBridgeError(INSTALL_HINT)
    if code != 0:
        raise NodeBridgeError(f"rasterize bridge failed (exit {code}): {err.decode('utf-8', 'replace')}")

    try:
        data = json.loads(out.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise NodeBridgeError(f"rasterize bridge returned invalid JSON: {exc}") from exc

    results: dict[str, bytes] = {}
    for key, b64 in data.get("results", {}).items():
        results[key] = base64.b64decode(b64)
    return results


def svg_to_pdf(svg: str, out_path: str, width: float, height: float, title: str = "") -> None:
    """Convert a page SVG to a PDF file via the Node bridge."""

    if not pdf_bridge_available():
        raise NodeBridgeError(INSTALL_HINT)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    payload = {
        "svg": svg,
        "out": os.path.abspath(out_path),
        "width": width,
        "height": height,
        "title": title,
    }
    code, out, err = _run("svg2pdf.mjs", payload)
    if code == 2:
        raise NodeBridgeError(INSTALL_HINT)
    if code != 0:
        raise NodeBridgeError(f"pdf bridge failed (exit {code}): {err.decode('utf-8', 'replace')}")
