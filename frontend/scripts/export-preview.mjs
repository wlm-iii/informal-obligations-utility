// Run build:preview first, then: node scripts/export-preview.mjs <output.html>
import { readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../dist-preview/", import.meta.url));
const output = process.argv[2];
if (!output) throw new Error("Provide an output HTML path.");
let html = readFileSync(resolve(root, "dashboard-preview.html"), "utf8");
const mime = { png: "image/png", woff2: "font/woff2", svg: "image/svg+xml" };
html = html.replace(/<link\b[^>]*rel="stylesheet"[^>]*>/g, tag => {
 const href = tag.match(/href="([^"]+)"/)[1];
 let css = readFileSync(resolve(root, href), "utf8");
 css = css.replace(/url\(([^)]+)\)/g, (match, url) => {
  if (url.startsWith("data:")) return match;
  const name = basename(url.replace(/["']/g, ""));
  const data = readFileSync(resolve(root, "assets", name)).toString("base64");
  return `url(data:${mime[name.split(".").pop()] || "application/octet-stream"};base64,${data})`;
 });
 return `<style>${css}</style>`;
});
html = html.replace(/<script\b[^>]*src="([^"]+)"[^>]*><\/script>/g, (_, src) => {
 const js = readFileSync(resolve(root, src), "utf8").replaceAll("</script", "<\\/script");
 return `<script type="module">${js}</script>`;
});
writeFileSync(output, html);
console.log(`Standalone preview saved to ${output}`);
