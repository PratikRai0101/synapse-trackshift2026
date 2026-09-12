/**
 * Headless screenshot tool for iterating on the 3D scene.
 *
 * Renders the viewer in headless Chromium and writes orbit + follow captures.
 * Uses a locally installed Chromium-family browser (Brave/Chrome/Edge) by
 * default; override with BROWSER_PATH.
 *
 *     bun run shot                 # -> .shots/orbit.png, .shots/follow.png
 *     bun run shot 12000           # wait 12s before the first capture
 *
 * Start `bun run mock` and `bun run dev` first, or point VITE_BRIDGE_URL at a
 * running bridge.
 */

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser";
const executablePath = process.env.BROWSER_PATH ?? BRAVE;
const wait = Number(process.argv[2] ?? 7000);
const url = process.env.VIEWER_URL ?? "http://localhost:5173/";
const outDir = process.env.SHOT_DIR ?? ".shots";

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath,
  args: [
    "--enable-unsafe-swiftshader",
    "--use-angle=swiftshader",
    "--ignore-gpu-blocklist",
    "--disable-dev-shm-usage",
  ],
});

const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });

const errors: string[] = [];
page.on("console", (message) => {
  if (message.type() === "error" && !message.text().includes("404")) {
    errors.push(message.text());
  }
});
page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));

await page.goto(url, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(wait);
await page.screenshot({ path: `${outDir}/orbit.png` });

await page.locator("button", { hasText: "CAM:" }).click();
await page.waitForTimeout(4000);
await page.screenshot({ path: `${outDir}/follow.png` });

console.log(errors.length ? `console errors:\n${errors.join("\n")}` : "no console errors");
console.log(`saved ${outDir}/orbit.png and ${outDir}/follow.png`);

await browser.close();
