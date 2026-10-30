# Changelog

## Unreleased: four diagram families

- Added explicit process, decision, and data flow shapes alongside vendor icon
  architecture nodes, with cycle tolerant layout and ordered swim lanes.
- Added shared edge routing, SVG/HTML, editable PowerPoint, compressed draw.io,
  and modern VSDX shapes and text sizing.
- Added service resolution with suggestions and strict mode, family templates,
  MCP resources and prompts, four agent skills, and five family examples.
- Added byte snapshots for the original examples and CI checks on Linux and
  Windows, with an optional Node job for PDF and icon decks.

### Compatibility changes

- PPTX, VSDX, and PDF bytes from the original examples changed once in phase
  zero because ZIP timestamps and PDF creation metadata were fixed for stable
  golden snapshots. Diagram content was preserved.
- A providerless service name now validates. It resolves to a catalog service
  where possible; misses produce a fallback warning or a strict mode error.
- Existing `kind` and older lane specs remain supported on their original path.
- Phase-ten PowerPoint application testing found that the earlier minimal OOXML
  package scaffold was rejected as corrupt, including for old specs. The PPTX
  package now uses complete static presentation, master, layout, and theme
  parts. Five PPTX golden snapshots changed for this repair; other format
  snapshots remained byte identical.
