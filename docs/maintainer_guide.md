# Maintainer guide

## Invariants

- The Python core uses only the standard library. Import the MCP SDK only from
  `mcp_server/server.py`. Node helpers are optional and detected at runtime.
- The CLI and MCP tools parse input and call `archdiagram.engine`. The engine
  validates, normalizes, resolves services, lays out, renders, and writes bytes.
- `archdiagram/formats.py` is the single format registry. Add a renderer there
  with its extension, MIME type, and binary flag.
- A spec without explicit `shape`, `tier`, edge styling, or `lane_orientation`
  follows the compatibility path. Compare `tests/golden` before changing it.
- New shape geometry and colors are centralized in `archdiagram/shapes.py`.
  Routing is shared by SVG/PDF and modern presentation formats.
- Keep icons, archives, generated output, and `node_modules` out of Git.

## Tests and phase checks

Run `python -m unittest discover -s tests -v` after each phase. Run `npm ci
--prefix node` first when checking PDF golden files and icon decks. Tests cover
the five old examples as byte snapshots and five family examples via CLI and
MCP. `tests/test_skills_sync.py` compares the repo and shared Claude skill
copies when the shared library is mounted.

The release branch should preserve old golden bytes. If a necessary change
alters them, document the exact format and reason in the changelog and baseline
record. Do not replace snapshots merely to make a test pass.

## Format notes

Draw.io compressed mode raw-deflates URI encoded model XML. The portable style
removes `;base64` from its image token, because semicolons split draw.io styles.
For Lucidchart with vendor icons, use PDF. PowerPoint routed edges are editable
freeform shapes with custom geometry; do not put custom geometry in a connector
shape. VSDX text uses an explicit Character size cell for modern shapes.

Package/XML checks prove structural integrity, not visual correctness in target
applications. The PPTX emitter uses static XML parts under `pptx_parts/` from a
locally generated blank PowerPoint deck. PowerPoint opened and exported both a
modern KYC deck and a legacy deck after this repair; an icon-bearing Azure deck
also opened with four picture shapes. Visio remains visually unverified until
opened there. Record the exact application and version for future checks.
