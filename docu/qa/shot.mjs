import { chromium } from "/opt/npm-tools/node_modules/playwright/index.mjs";
const [,, page, out] = process.argv;
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args:["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
p.on("pageerror", e => console.log("ERR", e.message));
await p.goto("file://" + process.cwd() + "/" + page);
await p.screenshot({ path: out });
await b.close();
