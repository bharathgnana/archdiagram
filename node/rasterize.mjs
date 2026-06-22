#!/usr/bin/env node
// Rasterise SVG icons to PNG using @resvg/resvg-js.
//
// Protocol (batch, single process):
//   stdin  : JSON { "items": [ { "id": "...", "svg": "<svg.../>", "width": 96 }, ... ] }
//   stdout : JSON { "results": { "<id>": "<base64 png>" }, "errors": { "<id>": "msg" } }
//
// Exit codes: 0 ok (even if individual items errored), 2 if resvg is missing,
// 3 on malformed input.

import { readFileSync } from "node:fs";

function readStdin() {
  try {
    return readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

let Resvg;
try {
  ({ Resvg } = await import("@resvg/resvg-js"));
} catch (err) {
  process.stderr.write(
    "missing dependency '@resvg/resvg-js'. Run: cd node && npm install\n" + String(err) + "\n",
  );
  process.exit(2);
}

let payload;
try {
  payload = JSON.parse(readStdin() || "{}");
} catch (err) {
  process.stderr.write("invalid JSON on stdin: " + String(err) + "\n");
  process.exit(3);
}

const items = Array.isArray(payload.items) ? payload.items : [];
const results = {};
const errors = {};

for (const item of items) {
  const id = String(item.id);
  try {
    const width = Number(item.width) > 0 ? Math.round(Number(item.width)) : 96;
    const resvg = new Resvg(item.svg, {
      fitTo: { mode: "width", value: width },
      background: "rgba(0,0,0,0)",
    });
    const png = resvg.render().asPng();
    results[id] = Buffer.from(png).toString("base64");
  } catch (err) {
    errors[id] = String(err && err.message ? err.message : err);
  }
}

process.stdout.write(JSON.stringify({ results, errors }));
