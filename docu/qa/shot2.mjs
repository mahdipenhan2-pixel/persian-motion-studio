import { chromium } from "/opt/npm-tools/node_modules/playwright/index.mjs";
const b = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args:["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
p.on("pageerror", e => console.log("ERR", e.message));
const d = "/tmp/claude-0/-home-claude/a96ae5db-0896-5ec2-a45b-c8f2c5d499bb/scratchpad/";
for (const k of ["livingRoom","street","studio"]) { await p.goto("file://"+process.cwd()+"/qa/bg.html?b="+k); await p.screenshot({path:d+"bg_"+k+".png"}); }
await b.close();
