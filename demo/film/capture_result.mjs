// Frame-by-frame capture of the finished NASA job page for film scene 6b: the player is paused and stepped, so
// picture and the dub track share one clock. Needs playwright-core and Chrome; writes frames/ (30 fps PNGs).

import { chromium } from "playwright-core";
const FPS = 30, ES = [0.0, 7.6], HI = [7.6, 11.6], TAIL = 13.5;
const b = await chromium.launch({ channel: "chrome", headless: true, args: ["--window-size=1600,900", "--force-device-scale-factor=1"] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
await p.goto(`https://viberick-dub.web.app/?job=h0wLZJeYGxw-e8930d`, { waitUntil: "load" });
await p.waitForTimeout(6000);
await p.evaluate(() => window.scrollTo({ top: 200 }));
let k = 0;
const shot = async () => { await p.screenshot({ path: `frames/${String(k++).padStart(5, "0")}.png` }); };
const seek = t => p.evaluate(t => new Promise(r => { const v = document.querySelector("#video"); v.pause(); if (Math.abs(v.currentTime - t) < 1e-3) return r(); v.addEventListener("seeked", () => requestAnimationFrame(() => requestAnimationFrame(r)), { once: true }); v.currentTime = t; }), t);
const play = async ([a, z]) => { for (let t = a; t < z - 1e-6; t += 1 / FPS) { await seek(t); await shot(); } };
await p.getByRole("button", { name: "Español" }).first().click();
await p.waitForTimeout(1500);
await play(ES);
await p.getByRole("button", { name: "हिन्दी" }).first().click();
await p.waitForTimeout(1500);
await seek(HI[0]);
await play(HI);
// narration from 11.8 s: keep the Hindi picture running (muted), then the checks, then the downloads
await play([HI[1], HI[1] + 5.8]);
const y0 = await p.evaluate(() => scrollY);
const yd = await p.evaluate(() => { const r = document.querySelector("#downloads").getBoundingClientRect(); return scrollY + r.top + r.height / 2 - 450; });
const ys = await p.evaluate(() => { const el = [...document.querySelectorAll("h2,h3,div")].find(e => e.textContent.trim().startsWith("88 / 90") || e.textContent.trim().startsWith("88/90")); const r = el.getBoundingClientRect(); return scrollY + r.top - 140; });
const ease = x => x < .5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2;
const glide = async (from, to, secs) => { const n = Math.round(secs * FPS); for (let i = 1; i <= n; i++) { await p.evaluate(y => scrollTo(0, y), from + (to - from) * ease(i / n)); await shot(); } };
const hold = async secs => { for (let i = 0; i < Math.round(secs * FPS); i++) await shot(); };
await glide(y0, ys, 1.2);
await hold(1.0);
await glide(ys, yd, 1.0);
for (const a of await p.locator("#downloads a").all()) { await a.hover(); await hold(.45); }
await p.mouse.move(5, 5);
await hold(3);
console.log(JSON.stringify({ frames: k, secs: k / FPS }));
await b.close();
