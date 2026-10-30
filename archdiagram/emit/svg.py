"""Self-contained SVG and HTML exports using the shared page renderer."""

from __future__ import annotations

import html

from ..layout.engine import LayoutResult, layout_diagram
from ..registry.catalog import Catalog, catalog_for
from ..registry.icons import IconResolver
from ..spec.model import Diagram
from .svgcanvas import build_page_svg


def render_svg(diagram: Diagram, *, icon_cache: str | None = None,
               layout: LayoutResult | None = None,
               catalog: Catalog | None = None) -> tuple[str, list[str]]:
    catalog = catalog if catalog is not None else catalog_for(diagram)
    resolver = IconResolver(icon_cache)
    uris: dict[str, str] = {}
    warnings: list[str] = []
    for node in diagram.nodes:
        if node.kind != "service":
            continue
        entry = catalog.lookup(node.service)
        if entry is None:
            warnings.append(f"unknown service '{node.service}' (node '{node.id}') -> fallback box")
            continue
        uri = resolver.data_uri(entry.icon)
        if uri is None:
            warnings.append(f"missing icon '{entry.icon}' (node '{node.id}') -> fallback box")
        else:
            uris[node.id] = uri
    return build_page_svg(diagram, layout if layout is not None else layout_diagram(diagram),
                          catalog, icon_uris=uris), warnings


def render_html(diagram: Diagram, *, icon_cache: str | None = None,
                layout: LayoutResult | None = None,
                catalog: Catalog | None = None) -> tuple[str, list[str]]:
    svg, warnings = render_svg(diagram, icon_cache=icon_cache, layout=layout, catalog=catalog)
    title = html.escape(diagram.title)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
        '<style>body{margin:0;padding:24px;background:#edf2f7;font-family:system-ui}'
        'main{max-width:100%;overflow:auto;background:white;box-shadow:0 2px 12px #0002}'
        'svg{display:block;max-width:none}</style></head><body><main>'
        f'{svg}</main></body></html>'
    ), warnings
