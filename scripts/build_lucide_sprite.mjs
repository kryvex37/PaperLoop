import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const iconNames = [
  "layout-dashboard", "list", "plus", "search", "sparkles", "boxes", "clipboard-list",
  "clock-3", "receipt-text", "leaf", "settings", "user-round", "users-round", "school",
  "recycle", "clipboard-check", "users", "chart-no-axes-combined", "truck", "check-check",
  "sun", "moon", "monitor", "tree-pine", "chevron-down",
];

const escapeAttribute = (value) => String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;");
const toKebab = (value) => value.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
const symbols = await Promise.all(iconNames.map(async (name) => {
  const iconPath = path.join(root, "node_modules", "lucide", "dist", "esm", "icons", `${name}.mjs`);
  const iconModule = await import(pathToFileURL(iconPath).href);
  const markup = iconModule.default.map(([tag, attributes]) => {
    const attrs = Object.entries(attributes).map(([key, value]) => `${toKebab(key)}="${escapeAttribute(value)}"`).join(" ");
    return `    <${tag} ${attrs}/>`;
  }).join("\n");
  return `  <symbol id="icon-${name}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">\n${markup}\n  </symbol>`;
}));

const output = path.join(root, "static", "img", "lucide-icons.svg");
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, `<?xml version="1.0" encoding="UTF-8"?>\n<!-- Lucide v1.79.0 icons. ISC license: https://github.com/lucide-icons/lucide/blob/main/LICENSE -->\n<svg xmlns="http://www.w3.org/2000/svg">\n${symbols.join("\n")}\n</svg>\n`, "utf8");
