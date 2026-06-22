"""Command-line interface for archdiagram.

    archdiagram validate <spec.json>
    archdiagram render   <spec.json> --format pdf|drawio|vsdx -o out.ext
                          [--drawio-mode native|portable] [--icons DIR]
    archdiagram catalog  search <query>
    archdiagram catalog  list [--vendor azure]
"""

from __future__ import annotations

import argparse
import sys

from .emit.drawio import NATIVE, PORTABLE, emit_drawio
from .emit.pdf import PdfDependencyError, emit_pdf
from .emit.vsdx import emit_vsdx
from .registry.catalog import get_catalog
from .spec.validate import SpecError, SpecValidationError, load_spec


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        diagram = load_spec(args.spec)
    except SpecValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: '{diagram.title}' - {len(diagram.nodes)} nodes, "
        f"{len(diagram.edges)} edges, {len(diagram.groups)} groups"
    )
    return 0


def _default_out(spec_path: str, fmt: str) -> str:
    base = spec_path.rsplit(".", 1)[0] if "." in spec_path else spec_path
    ext = {"pdf": "pdf", "drawio": "drawio", "vsdx": "vsdx"}[fmt]
    return f"{base}.{ext}"


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        diagram = load_spec(args.spec)
    except SpecError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out_path = args.output or _default_out(args.spec, args.format)
    warnings: list[str] = []
    try:
        if args.format == "pdf":
            warnings = emit_pdf(diagram, out_path, icon_cache=args.icons)
        elif args.format == "drawio":
            mode = PORTABLE if args.drawio_mode == "portable" else NATIVE
            xml = emit_drawio(diagram, mode=mode, icon_cache=args.icons)
            import os

            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(xml)
        elif args.format == "vsdx":
            warnings = emit_vsdx(diagram, out_path, icon_cache=args.icons)
        else:  # pragma: no cover - argparse restricts choices
            print(f"unknown format: {args.format}", file=sys.stderr)
            return 2
    except PdfDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"wrote {out_path}")
    return 0


def _cmd_catalog(args: argparse.Namespace) -> int:
    catalog = get_catalog()
    if args.catalog_cmd == "search":
        results = catalog.search(args.query)
        if not results:
            print("no matches")
            return 0
        for entry in results:
            print(f"  {entry.service:<34} {entry.label}")
        return 0
    # list
    entries = catalog.all_entries()
    if args.vendor:
        entries = [e for e in entries if e.vendor == args.vendor]
    for entry in sorted(entries, key=lambda e: e.service):
        print(f"  {entry.service:<34} {entry.label}")
    print(f"\n{len(entries)} services across vendors: {', '.join(catalog.vendors)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archdiagram", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="validate a spec file")
    p_val.add_argument("spec", help="path to spec JSON (or JSON string)")
    p_val.set_defaults(func=_cmd_validate)

    p_ren = sub.add_parser("render", help="render a spec to a diagram file")
    p_ren.add_argument("spec", help="path to spec JSON (or JSON string)")
    p_ren.add_argument(
        "--format", "-f", required=True, choices=["pdf", "drawio", "vsdx"], help="output format"
    )
    p_ren.add_argument("--output", "-o", help="output path (default: alongside spec)")
    p_ren.add_argument(
        "--drawio-mode",
        choices=["native", "portable"],
        default="portable",
        help="drawio icon strategy (default: portable, best for Lucid import)",
    )
    p_ren.add_argument("--icons", help="icon cache directory override")
    p_ren.set_defaults(func=_cmd_render)

    p_cat = sub.add_parser("catalog", help="inspect the vendor service catalog")
    cat_sub = p_cat.add_subparsers(dest="catalog_cmd", required=True)
    p_search = cat_sub.add_parser("search", help="search services")
    p_search.add_argument("query")
    p_search.set_defaults(func=_cmd_catalog)
    p_list = cat_sub.add_parser("list", help="list services")
    p_list.add_argument("--vendor", help="filter by vendor")
    p_list.set_defaults(func=_cmd_catalog)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
