import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.2/firebase-app.js";
import {
  getFirestore, doc, collection, query, where, orderBy, onSnapshot, getDocs, limit,
} from "https://www.gstatic.com/firebasejs/11.0.2/firebase-firestore.js";

// Public web config (identifies the project; access is governed by firestore.rules).
const app = initializeApp({
  apiKey: "AIzaSyD5X1nhzZRX4CSpOErW8QiWogfZWWx8hD0",
  authDomain: "viberick-84abf.firebaseapp.com",
  projectId: "viberick",
  storageBucket: "viberick.firebasestorage.app",
  messagingSenderId: "533986569528",
  appId: "1:533986569528:web:f6a5a786be2468192a65cd",
});
const db = getFirestore(app);
const LOCAL = window.LOCAL_JOB || null;   // review.html of a local run embeds the job instead of Firestore

const LANG = { ko: "한국어", en: "English", ja: "日本語", "zh-Hans": "中文" };
const STEPS = [
  ["start", "Download"], ["separated", "Separate music"], ["transcribed", "Chirp 3 words"],
  ["proofread", "Gemini proofread"], ["brief", "Brief"], ["translated", "Translate to time"],
  ["voiced", "Speak"], ["line", "Listen & repair"], ["language_done", "Mix"], ["done", "Done"],
];
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

let unsub = [];
let state = { job: null, events: [], lines: {}, track: "orig", lineLang: null };

// ---------- new job ----------
$("#new").addEventListener("submit", async (e) => {
  e.preventDefault();
  const langs = [...document.querySelectorAll("#langs input:checked")].map((i) => i.value);
  const err = $("#err");
  err.hidden = true;
  if (!langs.length) { err.textContent = "Pick at least one language."; err.hidden = false; return; }
  $("#go").disabled = true;
  $("#go").textContent = "Starting…";
  try {
    const r = await fetch("/api/jobs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: $("#url").value.trim(), langs }),
    });
    const body = await r.json();
    if (!r.ok) throw new Error(body.detail || "Could not start the job.");
    history.pushState({}, "", `?job=${body.id}`);
    open(body.id);
  } catch (x) {
    err.textContent = x.message; err.hidden = false;
  } finally {
    $("#go").disabled = false; $("#go").textContent = "Dub it";
  }
});

// ---------- studio ----------
function open(id) {
  unsub.forEach((u) => u());
  unsub = [];
  state = { job: null, events: [], lines: {}, track: state.track || "orig", lineLang: null };
  $("#studio").hidden = false;
  $("#log").innerHTML = "";
  $("#tx").innerHTML = `<li class="muted pad">The transcript appears when the dub is ready.</li>`;
  state.txStarts = [];
  $("#lines-wrap").hidden = true;
  $("#stats").innerHTML = "";
  $("#tracks").innerHTML = "";
  $("#downloads").innerHTML = "";
  const v = $("#video");
  v.removeAttribute("src"); v.load();
  $("#ph").hidden = false;
  if (new URLSearchParams(location.search).get("job") === id) $("#studio").scrollIntoView({ behavior: "smooth" });

  const ref = doc(db, "jobs", id);
  unsub.push(onSnapshot(ref, (snap) => {
    if (!snap.exists()) { $("#j-title").textContent = "Job not found"; return; }
    state.job = { id, ...snap.data() };
    renderJob();
  }));
  unsub.push(onSnapshot(query(collection(ref, "events"), orderBy("t")), (snap) => {
    state.events = snap.docs.map((d) => d.data());
    renderLog();
    renderSteps();
  }));
  unsub.push(onSnapshot(collection(ref, "lines"), (snap) => {
    snap.docs.forEach((d) => { state.lines[d.id] = d.data(); });
    renderLines();
    renderTranscript();
  }));
}

function openLocal(L) {
  state = { job: L.job, events: L.events, lines: L.lines, track: "en", lineLang: null };
  $(".hero").hidden = true; $("#examples").hidden = true; $("#how").hidden = true;
  $("#studio").hidden = false;
  renderJob(); renderLog(); renderSteps(); renderLines(); renderTranscript();
}

// ---------- synced transcript ----------
let userScrolled = 0;
$("#tx").addEventListener("wheel", () => { userScrolled = Date.now(); }, { passive: true });
$("#tx").addEventListener("touchmove", () => { userScrolled = Date.now(); }, { passive: true });
function showTab(which) {
  $("#tab-tx").setAttribute("aria-selected", which === "tx");
  $("#tab-log").setAttribute("aria-selected", which === "log");
  $("#tx").hidden = which !== "tx";
  $("#log").hidden = which !== "log";
}
$("#tab-tx").onclick = () => showTab("tx");
$("#tab-log").onclick = () => showTab("log");

function txRows() {
  const langs = Object.keys(state.lines);
  if (!langs.length) return [];
  const lang = state.track !== "orig" && state.lines[state.track] ? state.track : null;
  const base = state.lines[lang || langs[0]].rows || [];
  return base.map((r) => ({ start: r.start, src: r.src, dub: lang ? r.text : null, spk: r.spk,
    voice: r.voice?.startsWith("voice_") ? "cloned" : r.voice }));
}
function renderTranscript() {
  const rows = txRows();
  if (!rows.length) return;
  const many = new Set(rows.map((r) => r.spk || "1")).size > 1;
  $("#tx").innerHTML = rows.map((r, i) => `<li data-i="${i}" data-t="${r.start}"><time>${mmss(r.start)}</time><div>
    ${r.dub ? `<span class="srctext">${many ? `<span class="who">S${esc(r.spk || "1")}${r.voice ? ` · ${esc(r.voice)}` : ""}</span>` : ""}${esc(r.src)}</span><span class="dubtext">${esc(r.dub)}</span>`
            : `<span class="dubtext">${many ? `<span class="who">S${esc(r.spk || "1")}${r.voice ? ` · ${esc(r.voice)}` : ""}</span>` : ""}${esc(r.src)}</span>`}</div></li>`).join("");
  $("#tx").querySelectorAll("li").forEach((li) => li.onclick = () => seek(+li.dataset.t));
  state.txStarts = rows.map((r) => r.start);
  state.txNow = -1;
  highlight();
}
function seek(t) {
  const v = $("#video");
  const go = () => { v.currentTime = Math.max(0, t - 0.15); v.play(); };
  v.readyState >= 1 ? go() : v.addEventListener("loadedmetadata", go, { once: true });
}
function highlight() {
  const st = state.txStarts || [];
  const t = $("#video").currentTime;
  let i = -1;
  for (let k = 0; k < st.length && st[k] <= t + 0.05; k++) i = k;
  if (i === state.txNow) return;
  state.txNow = i;
  const ol = $("#tx");
  ol.querySelectorAll("li.now").forEach((x) => x.classList.remove("now"));
  const li = ol.querySelector(`li[data-i="${i}"]`);
  if (!li) return;
  li.classList.add("now");
  if (Date.now() - userScrolled > 4000 && !ol.hidden) ol.scrollTop = li.offsetTop - ol.clientHeight / 3;
}
$("#video").addEventListener("timeupdate", highlight);
$("#video").addEventListener("seeked", highlight);

function renderJob() {
  const j = state.job;
  $("#j-title").textContent = j.title || j.report?.title || j.url;
  $("#j-yt").href = j.url;
  const label = { queued: "Queued", running: j.stage || "Running", done: "Finished", error: "Failed" }[j.status] || j.status;
  $("#j-status").textContent = j.status === "error" ? `Failed · ${j.error || ""}` : label;
  $("#live-dot").classList.toggle("live", j.status === "running" || j.status === "queued");
  $("#ph-img").src = j.thumbnail || "";
  $("#ph-text").textContent = j.status === "error" ? "This job failed." : (j.stage || "Queued") + "…";
  if (j.status === "done" && j.outputs) {
    $("#ph").hidden = true;
    renderTracks();
    renderStats();
  }
}

function renderTracks() {
  const j = state.job, o = j.outputs;
  const src = j.report?.src;
  const langs = (j.report?.langs || []).map((l) => l.lang);
  const tracks = [["orig", `Original${src ? ` · ${LANG[src] || src}` : ""}`], ...langs.map((l) => [l, LANG[l] || l])];
  if (!tracks.some(([k]) => k === state.track)) state.track = langs[0] || "orig";
  $("#tracks").innerHTML = tracks.map(([k, name]) =>
    `<button role="tab" data-k="${k}" aria-selected="${k === state.track}">${esc(name)}${k === "orig" ? "" : "<small>dub</small>"}</button>`).join("");
  $("#tracks").querySelectorAll("button").forEach((b) => b.onclick = () => { state.track = b.dataset.k; renderTracks(); });
  setVideo(o[`video.${state.track}.mp4`], o[`subs.${state.track === "orig" ? src : state.track}.vtt`]);
  renderTranscript();
  $("#downloads").innerHTML = langs.map((l) =>
    `<span>${esc(LANG[l])}: <a href="${o[`dub.${l}.m4a`]}" download>audio</a> · <a href="${o[`subs.${l}.srt`]}" download>SRT</a></span>`).join("");
}

function setVideo(url, vtt) {
  const v = $("#video");
  if (!url || v.dataset.url === url) return;
  const t = v.currentTime, playing = !v.paused;
  v.dataset.url = url;
  v.innerHTML = vtt ? `<track kind="subtitles" src="${vtt}" default>` : "";
  v.src = url;
  v.addEventListener("loadedmetadata", () => {
    v.currentTime = t;
    applySubs();
    if (playing) v.play();
  }, { once: true });
}
function applySubs() {
  const on = $("#subs-on").checked;
  [...$("#video").textTracks].forEach((tr) => tr.mode = on ? "showing" : "hidden");
}
$("#subs-on").addEventListener("change", applySubs);

function renderStats() {
  const r = state.job.report;
  if (!r) return;
  const lines = r.langs.reduce((a, l) => a + l.lines, 0);
  const ok = r.langs.reduce((a, l) => a + l.ok, 0);
  const first = r.langs.reduce((a, l) => a + l.first_pass_ok, 0);
  const p95 = Math.max(...r.langs.map((l) => l.late_p95));
  const items = [
    [mmss(r.duration), "of video dubbed"],
    [`${r.langs.length} × ${r.units}`, "languages × lines"],
    [`${Math.round((100 * ok) / lines)}%`, "lines verified by Gemini listening"],
    [`${ok - first}`, "lines auto-repaired by the agent"],
    [`${p95.toFixed(1)} s`, "timing drift (p95)"],
    [mmss(r.sec_total), "wall-clock time"],
  ];
  $("#stats").innerHTML = items.map(([b, s]) => `<div class="stat"><b>${esc(b)}</b><span>${esc(s)}</span></div>`).join("");
}

function evText(e) {
  const L = e.lang ? `[${e.lang}${e.id !== undefined ? ` #${e.id}` : ""}] ` : "";
  switch (e.kind) {
    case "start": return ["stage", `Fetched “${e.title}” · ${mmss(e.duration)}`];
    case "voice": return ["stage", e.consent ? "Voice: creator's cloned voice (consent on file)" : "Voice: stock Gemini voice (no consent on file for this channel)"];
    case "separated": return ["stage", "Separated speech from music and effects"];
    case "cast": return ["stage", "Voice cast: " + (e.speakers || []).map((c) =>
      `S${c.spk} → ${c.why?.startsWith("creator") ? "creator's cloned voice" : c.voice}${c.match !== undefined ? ` (voice match ${c.match})` : ""}`).join(" · ")];
    case "transcribed": return ["stage", `Chirp 3: ${e.words} words with timestamps`];
    case "proofread": return ["stage", `Gemini listened and corrected the transcript → ${e.cues} lines (${LANG[e.src] || e.src})`];
    case "brief": return ["stage", `Brief: ${e.terms} term rules · ${String(e.summary).split(". ")[0]}.`];
    case "translated": return ["stage", `${L}translated ${e.lines} lines to their time budgets`];
    case "voiced": return ["stage", `${L}spoke ${e.para_lines}/${e.lines} lines in paragraph takes`];
    case "language_done": return ["stage", `${L}mixed · ${e.ok}/${e.lines} verified · drift p95 ${e.late_p95}s`];
    case "done": return ["stage", `Finished in ${mmss(e.sec_total)}`];
    case "line":
      if (e.do === "shorten") return ["fix", `${L}ran long → rewrote shorter: “${e.text}”`];
      if (e.do === "resynth") return ["fix", `${L}re-synthesizing`];
      if (e.do === "retranslate") return ["fix", `${L}re-translated: “${e.text}”`];
      if (e.do === "check") return e.ok ? ["good", `${L}✓ Gemini listened: correct`] : ["bad", `${L}Gemini heard a problem: ${e.issue}`];
      if (e.do === "synth" && !e.pre) return ["", `${L}synthesized ${e.dur}s for a ${e.slot}s slot`];
      return null;
    default: return null;
  }
}

function renderLog() {
  const t0 = state.events[0]?.t || 0;
  const rows = [];
  for (const e of state.events) {
    const x = evText(e);
    if (!x) continue;
    const [cls, html] = x;
    rows.push(`<li class="${cls}"><time>${mmss(e.t - t0)}</time><span>${esc(html)}</span></li>`);
  }
  const ol = $("#log");
  const stick = ol.scrollTop + ol.clientHeight >= ol.scrollHeight - 30;
  ol.innerHTML = rows.join("");
  if (stick || state.job?.status === "running") ol.scrollTop = ol.scrollHeight;
  $("#log-count").textContent = `${rows.length} events`;
}

function renderSteps() {
  const seen = new Set(state.events.map((e) => e.kind));
  const done = state.job?.status === "done";
  let nowSet = false;
  $("#steps").innerHTML = STEPS.map(([k, name]) => {
    let cls = "";
    if (seen.has(k) || done) cls = "done";
    else if (!nowSet && state.job?.status !== "error") { cls = "now"; nowSet = true; }
    if (k === "line" && seen.has("line") && !seen.has("language_done") && !done) cls = "now";
    return `<li class="${cls}">${name}</li>`;
  }).join("");
}

function renderLines() {
  const langs = Object.keys(state.lines);
  if (!langs.length) return;
  $("#lines-wrap").hidden = false;
  if (!state.lineLang || !langs.includes(state.lineLang)) state.lineLang = langs.includes("en") ? "en" : langs[0];
  $("#line-lang").innerHTML = langs.map((l) => `<button data-l="${l}" aria-selected="${l === state.lineLang}">${esc(LANG[l] || l)}</button>`).join("");
  $("#line-lang").querySelectorAll("button").forEach((b) => b.onclick = () => { state.lineLang = b.dataset.l; renderLines(); });
  const only = $("#only-fixed").checked;
  const rows = (state.lines[state.lineLang].rows || []).filter((r) =>
    !only || !r.ok || r.actions.some((a) => ["shorten", "resynth", "retranslate"].includes(a.do)));
  $("#lines tbody").innerHTML = rows.map((r) => {
    const chips = r.actions.filter((a) => a.do !== "synth" || !a.pre).map((a) => {
      if (a.do === "check") return `<span class="chip ${a.ok ? "ok" : "bad"}">${a.ok ? "✓ heard ok" : "✗ heard"}</span>`;
      if (a.do === "synth") return `<span class="chip">voice</span>`;
      return `<span class="chip fix">${a.do}</span>`;
    }).join("");
    return `<tr><td class="t" data-t="${r.start}">${mmss(r.start)}</td><td class="src">${esc(r.src)}</td>
      <td>${esc(r.text)}${r.ok ? "" : `<span class="issue">Flagged: ${esc(r.issue)}</span>`}</td>
      <td class="fit">${r.dur.toFixed(1)}s / ${r.slot.toFixed(1)}s${r.tempo !== 1 ? `<br>×${r.tempo}` : ""}</td><td>${chips}</td></tr>`;
  }).join("") || `<tr><td colspan="5" class="muted">Nothing to show.</td></tr>`;
  $("#lines tbody").querySelectorAll("td.t").forEach((td) => td.onclick = () => {
    if (state.track === "orig" || state.track !== state.lineLang) { state.track = state.lineLang; renderTracks(); }
    const v = $("#video");
    const go = () => { v.currentTime = Math.max(0, +td.dataset.t - 0.3); v.play(); };
    v.readyState >= 1 ? go() : v.addEventListener("loadedmetadata", go, { once: true });
    v.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}
$("#only-fixed").addEventListener("change", renderLines);

// ---------- examples ----------
async function loadExamples() {
  const snap = await getDocs(query(collection(db, "jobs"), where("demo", "==", true), limit(12)));
  const jobs = snap.docs.map((d) => ({ id: d.id, ...d.data() })).sort((a, b) => (b.created || 0) - (a.created || 0));
  const cards = $("#cards");
  if (!jobs.length) { cards.innerHTML = `<p class="muted">No examples yet.</p>`; return jobs; }
  cards.innerHTML = "";
  for (const j of jobs) {
    const c = $("#t-card").content.cloneNode(true);
    const a = c.querySelector("a");
    a.href = `?job=${j.id}`;
    a.onclick = (e) => { e.preventDefault(); history.pushState({}, "", `?job=${j.id}`); open(j.id); };
    c.querySelector("img").src = j.thumbnail;
    c.querySelector("b").textContent = j.title || j.url;
    const langs = (j.report?.langs || []).map((l) => LANG[l.lang]).join(" · ");
    c.querySelector("span").textContent = `${LANG[j.report?.src] || ""} → ${langs}`;
    cards.appendChild(c);
  }
  return jobs;
}

window.addEventListener("popstate", () => {
  const id = new URLSearchParams(location.search).get("job");
  if (id) open(id);
});

const initial = new URLSearchParams(location.search).get("job");
if (LOCAL) openLocal(LOCAL);
else loadExamples().then((jobs) => {
  if (initial) open(initial);
  else if (jobs[0]) open(jobs[0].id);
}).catch(() => { if (initial) open(initial); });
