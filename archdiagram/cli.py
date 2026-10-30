"""Command-line interface for archdiagram.

    archdiagram validate <spec.json>
    archdiagram render   <spec.json> --format pdf|drawio|vsdx|svg|html|pptx -o out.ext
                          [--drawio-mode native|portable] [--icons DIR]
    archdiagram catalog  search <query>
    archdiagram catalog  list [--vendor azure]
"""

from __future__ import annotations

import argparse
import json
import sys

from .emit.pdf import PdfDependencyError
from .engine import render_to_file, resolve_services
from .formats import FORMATS, get_format
from .registry.catalog import get_catalog
from .spec.validate import SpecError, SpecValidationError, load_spec
from .templates import get_template, list_templates, suggest_template


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        diagram = load_spec(args.spec)
        if args.strict:
            resolve_services(diagram, strict=True)
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
    return f"{base}{get_format(fmt).extension}"


def _cmd_render(args: argparse.Namespace) -> int:
    out_path = args.output or _default_out(args.spec, args.format)
    try:
        result = render_to_file(args.spec, args.format, out_path,
                                icon_cache=args.icons, drawio_mode=args.drawio_mode,
                                strict=args.strict)
    except SpecError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except PdfDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    for warning in result.warnings:
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


def _cmd_templates(args: argparse.Namespace) -> int:
    if args.template_cmd == "list":
        for item in list_templates():
            print(f"{item['name']}: {item['description']}")
    elif args.template_cmd == "suggest":
        print(suggest_template(args.description))
    else:
        print(json.dumps(get_template(args.name), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archdiagram", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_val = sub.add_parser("validate", help="validate a spec file")
    p_val.add_argument("spec", help="path to spec JSON (or JSON string)")
    p_val.add_argument("--strict", action="store_true", help="reject unresolved services")
    p_val.set_defaults(func=_cmd_validate)

    p_ren = sub.add_parser("render", help="render a spec to a diagram file")
    p_ren.add_argument("spec", help="path to spec JSON (or JSON string)")
    p_ren.add_argument(
        "--format", "-f", required=True, choices=list(FORMATS), help="output format"
    )
    p_ren.add_argument("--output", "-o", help="output path (default: alongside spec)")
    p_ren.add_argument(
        "--drawio-mode",
        choices=["native", "portable", "compressed"],
        default="portable",
        help="drawio icon strategy (default: portable, best for Lucid import)",
    )
    p_ren.add_argument("--icons", help="icon cache directory override")
    p_ren.add_argument("--strict", action="store_true", help="reject unresolved services")
    p_ren.set_defaults(func=_cmd_render)

    p_cat = sub.add_parser("catalog", help="inspect the vendor service catalog")
    cat_sub = p_cat.add_subparsers(dest="catalog_cmd", required=True)
    p_search = cat_sub.add_parser("search", help="search services")
    p_search.add_argument("query")
    p_search.set_defaults(func=_cmd_catalog)
    p_list = cat_sub.add_parser("list", help="list services")
    p_list.add_argument("--vendor", help="filter by vendor")
    p_list.set_defaults(func=_cmd_catalog)

    p_tpl = sub.add_parser("templates", help="list, suggest, or show starter specs")
    tpl_sub = p_tpl.add_subparsers(dest="template_cmd", required=True)
    tpl_list = tpl_sub.add_parser("list")
    tpl_list.set_defaults(func=_cmd_templates)
    tpl_show = tpl_sub.add_parser("show")
    tpl_show.add_argument("name", choices=[t["name"] for t in list_templates()])
    tpl_show.set_defaults(func=_cmd_templates)
    tpl_suggest = tpl_sub.add_parser("suggest")
    tpl_suggest.add_argument("description")
    tpl_suggest.set_defaults(func=_cmd_templates)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
