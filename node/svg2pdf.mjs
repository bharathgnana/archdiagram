#!/usr/bin/env node
// Convert a single page SVG to PDF using pdfkit + svg-to-pdfkit.
//
// Protocol:
//   stdin  : JSON { "svg": "<svg.../>", "out": "C:/path/out.pdf",
//                   "width": 850, "height": 1100, "title": "..." }
//   stdout : JSON { "ok": true, "out": "..." }
//
// Exit codes: 0 ok, 2 if a dependency is missing, 3 on malformed input,
// 4 on render/write failure.

import { readFileSync, createWriteStream } from "node:fs";

function readStdin() {
  try {
    return readFileSync(0, "utf8");
  } catch {
    return "";
  }
}

let PDFDocument;
let SVGtoPDF;
try {
  PDFDocument = (await import("pdfkit")).default;
  SVGtoPDF = (await import("svg-to-pdfkit")).default;
} catch (err) {
  process.stderr.write(
    "missing dependency 'pdfkit' / 'svg-to-pdfkit'. Run: cd node && npm install\n" +
      String(err) +
      "\n",
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

const { svg, out } = payload;
if (typeof svg !== "string" || typeof out !== "string") {
  process.stderr.write("payload must include string 'svg' and 'out'\n");
  process.exit(3);
}

const width = Number(payload.width) > 0 ? Number(payload.width) : 850;
const height = Number(payload.height) > 0 ? Number(payload.height) : 1100;

try {
  const doc = new PDFDocument({
    size: [width, height],
    margin: 0,
    info: { Title: payload.title || "Architecture" },
  });
  const stream = createWriteStream(out);
  const done = new Promise((resolve, reject) => {
    stream.on("finish", resolve);
    stream.on("error", reject);
  });
  doc.pipe(stream);
  SVGtoPDF(doc, svg, 0, 0, { width, height, assumePt: true });
  doc.end();
  await done;
  process.stdout.write(JSON.stringify({ ok: true, out }));
} catch (err) {
  process.stderr.write("pdf render failed: " + String(err && err.stack ? err.stack : err) + "\n");
  process.exit(4);
}
