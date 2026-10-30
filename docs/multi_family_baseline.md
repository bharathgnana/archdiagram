# Multi-family diagram baseline

Recorded 2026-10-30 (Asia/Kolkata) on `feature/multi-family-diagrams`.
The default branch was `main` at `ba9ed3d6ed30a19bbab715c41e3a84057f78a97a`.

The committed default branch has 23 test methods in four modules. The working
tree at the start of this work already had workflow nodes, lanes, SVG, HTML,
editable PPTX, templates, a generated catalog builder, and 32 passing tests in
six modules. Those pre-existing changes are part of the feature-branch baseline;
the two speech transcripts and unrelated article/images are not part of it.

Current source layout: typed models in `archdiagram/spec/model.py`, strict
validation in `archdiagram/spec/validate.py`, layout in
`archdiagram/layout/engine.py`, format emitters in `archdiagram/emit/`, CLI in
`archdiagram/cli.py`, MCP tools in `mcp_server/server.py`, and one skill at
`skill/SKILL.md`. The bundle includes Azure, AWS, GCP, and Kubernetes catalog
metadata and an icon downloader. The project has a `pyproject.toml` console
script and a GitHub Actions workflow.

The original validator raises `SpecValidationError` with all messages rather
than returning a list. Later work will preserve that public API and add a
non-throwing collection API. The current `kind` field already selects five
workflow shapes; later work will keep it as an alias for `shape`. Existing
lane specs require every node to name a lane; later work will change that for
new lane-orientation specs while preserving old render bytes.

Baseline suite: 32/32 passed using `python:3.12-slim` in Docker. The installed
Windows Python executable was blocked by Windows Application Control.

Phase-zero compatibility snapshots cover all five shipped diagram examples in
portable and native draw.io, SVG, HTML, VSDX, PPTX, and PDF. They are stored in
`tests/golden/`. The test fixes icon lookup to an empty cache so it also passes
on a checkout without downloaded vendor icons. PDF runs when the optional Node
bridge is installed; the other snapshots run with stdlib Python alone.
`node/package-lock.json` pins the optional helper versions for PDF snapshots.

The first golden run exposed timestamps in PPTX/VSDX ZIP entries and in PDFKit
metadata. Those timestamps are now fixed so repeated renders produce identical
bytes. This intentionally changes binary output bytes for existing specs while
preserving their content. The full suite now passes: 34/34 with the Node bridge,
and 34/34 with one expected PDF skip in stdlib-only Python.

The reference implementation was not available locally; only user-supplied
transcripts were available. This repository is MIT-licensed. No reference code
has been copied.

Phase-ten target-application testing found that PowerPoint rejected the original
hand-built PPTX scaffold, even for `sample_spec.json`. The generated slide XML
itself opened when placed into a PowerPoint-created package. The emitter now
bundles static presentation, master, blank layout, theme, and property XML
parts from a locally generated blank deck. It still writes the package and
dynamic slide with the standard library. Only the five PPTX golden snapshots
changed in this repair; this is a documented byte-level compatibility change
required to make the format open in PowerPoint.
