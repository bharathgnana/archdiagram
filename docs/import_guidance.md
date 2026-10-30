# Import and editing guidance

| Destination | Recommended output | Practical note |
|---|---|---|
| diagrams.net / draw.io | `.drawio` native or portable | Native uses vendor stencils; portable embeds icons. Compressed mode carries the same model in raw-deflate form. |
| Lucidchart | `.pdf` for icon fidelity | Lucidchart may drop embedded images from compressed draw.io imports. PDF preserves the visual image but is not an editable topology. |
| PowerPoint | `.pptx` | Shape nodes, text, and routed lines are editable. Vendor icons are PNG media; install optional Node helpers for them. |
| Visio | `.vsdx` | Modern shapes and routed lines are editable. Vendor icons are PNG media when the optional rasterizer is installed. |
| Browser | `.html` or `.svg` | Standalone with inline SVG and icons. |

Generate all formats with `python -m archdiagram.cli render spec.json -f
FORMAT -o out/diagram.EXT`. The engine gives binary formats byte output and
text formats UTF-8 output. Validate and inspect the target application before
publishing a diagram. PowerPoint and Visio rendering are not proven by XML
validation alone.
