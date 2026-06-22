# Contributing

Thanks for your interest in `archdiagram`! The repo is public, so anyone can
clone, install, use it, and propose changes.

## Install (developer setup)

```bash
git clone https://github.com/bharathgnana/archdiagram.git
cd archdiagram

# editable install (core has no third-party Python deps)
python -m pip install -e .

# fetch vendor icons into ./icons (not committed)
python -m tools.download_icons

# optional: Node bridge for .pdf and crisp raster icons
cd node && npm install && cd ..
```

Run the CLI with `python -m archdiagram.cli ...` (works regardless of PATH), or
the installed `archdiagram` console script.

## Run the tests

```bash
python -m unittest discover -s tests
```

Tests use the standard-library `unittest` only and pass without Node or
downloaded icons. Please keep them green and add coverage for new behavior.

## Project conventions

- **Core (`archdiagram/`) is stdlib-only.** Do not add third-party Python
  dependencies to the core. Spec validation stays hand-rolled (no `jsonschema`).
- The `mcp` SDK is allowed **only** under `mcp_server/`.
- Node (`@resvg/resvg-js`, `pdfkit`, `svg-to-pdfkit`) is optional and confined to
  `node/` and `archdiagram/rasterize/`. Features must degrade gracefully when it
  is absent.
- Vendor icons are **not committed**. Add new icons via a catalog entry under
  `archdiagram/registry/catalog_data/<vendor>.json` plus a source URL in
  `tools/icon_sources.json`.

## How to propose changes

### Outside contributors (no write access): fork + pull request

```bash
# 1. Fork on GitHub, then:
gh repo fork bharathgnana/archdiagram --clone
cd archdiagram

# 2. branch, change, test
git checkout -b my-change
python -m unittest discover -s tests

# 3. push to your fork and open a PR
git push -u origin my-change
gh pr create --fill
```

### Maintainers / collaborators (write access): branch + PR

```bash
git checkout -b feature/x
# ...changes...
git push -u origin feature/x
gh pr create --fill
```

Direct pushes to `main` are reserved for the repo owner. Everyone else should
open a pull request; the owner reviews and merges. To grant someone direct push
access, the owner adds them as a collaborator (GitHub: Settings → Collaborators).

## Commit messages

Keep them concise and focused on the "why". One logical change per PR where
possible.
