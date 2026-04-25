/**
 * After `vite build --mode <X>` the entry HTML is emitted under its
 * source name (e.g. `index.dashboard.html`). FastAPI serves a single
 * `web/index.html`, so rename it.
 *
 * Usage: node scripts/finalize-dist.mjs <distDir> <entryHtmlName>
 */
import { existsSync, renameSync } from "node:fs";
import { join } from "node:path";

const [, , distDir, entry] = process.argv;
if (!distDir || !entry) {
  console.error("usage: finalize-dist.mjs <dist-dir> <entry.html>");
  process.exit(2);
}

const src = join(distDir, entry);
const dst = join(distDir, "index.html");

if (!existsSync(src)) {
  console.error(`finalize-dist: ${src} not found (did vite build emit a different name?)`);
  process.exit(1);
}

renameSync(src, dst);
console.log(`finalize-dist: ${src} -> ${dst}`);
