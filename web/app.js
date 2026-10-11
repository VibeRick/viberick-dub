import { LANG } from "./langs.js?v=1";

// Recorded review mode stays local: no Firebase SDK, listeners or generation requests.
const LOCAL = window.LOCAL_JOB || null;
const reviewParam = new URLSearchParams(location.search).get("review");
const recordedMode = Boolean(LOCAL || reviewParam);
let db, doc, collection, query, where, orderBy, onSnapshot, getDocs, limit;
if (!recordedMode) {
  const {
    initializeApp
  } = await import("https://www.gstatic.com/firebasejs/11.0.2/firebase-app.js");
  const firestore = await import("https://www.gstatic.com/firebasejs/11.0.2/firebase-firestore.js");
  ({
    doc,
    collection,
    query,
    where,
    orderBy,
    onSnapshot,
    getDocs,
    limit
  } = firestore);
  // Public web config (identifies the project; access is governed by firestore.rules).
  const app = initializeApp({
    apiKey: "AIzaSyD5X1nhzZRX4CSpOErW8QiWogfZWWx8hD0",
    authDomain: "viberick-84abf.firebaseapp.com",
    projectId: "viberick",
    storageBucket: "viberick.firebasestorage.app",
    messagingSenderId: "533986569528",
    appId: "1:533986569528:web:f6a5a786be2468192a65cd",
  });
  db = firestore.getFirestore(app);
}

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;"
} [c]));
const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2,"0")}`;
const safeUrl = value => {
  if (typeof value !== "string" || !value.trim()) return "";
  try {
    const u = new URL(value, location.href);
    return ["http:", "https:"].includes(u.protocol) ? u.href : "";
  } catch {
    return "";
  }
};
const motion = () => matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
let unsub = [],
  generation = 0,
  mediaGeneration = 0,
  wantedTime = 0,
  wantedPlaying = false;
let state = {
  job: null,
  events: [],
  lines: {},
  track: "orig",
  lineLang: null,
  selected: 0
};

function lineChanges(row) {
  const actions = row.actions || [];
  const recovered = row.ok === true && actions.some(action => action.do === "check" && action.ok === false);
  return {
    recovered,
    timing: actions.some(action => ["shorten", "lengthen"].includes(action.do)),
    translation: !recovered && actions.some(action => action.do === "retranslate")
  };
}

function timelineChange(row, original) {
  if (original) return {
    className: "",
    label: ""
  };
  const change = lineChanges(row);
  return {
    className: change.recovered ? "repaired" : change.timing ? "refined" : "",
    label: [change.recovered ? "failed check recovered" : "", change.timing ? "timing refined" : "", change.translation ? "translation revised" : ""].filter(Boolean).join(", ")
  };
}
const repaired = r => lineChanges(r).recovered;
const activeLang = () => state.track !== "orig" && state.lines[state.track] ? state.track : state.lineLang || Object.keys(state.lines)[0];
const rows = l => state.lines[l]?.rows || [];
const duration = () => state.job?.report?.duration || Math.max(0, ...Object.values(state.lines).flatMap(x => (x.rows || []).map(r => r.source_end ?? r.end ?? r.start + r.slot))) || 180;
const sourceStart = r => r.source_start ?? r.start;
const sourceEnd = r => r.source_end ?? r.end ?? r.start + r.slot;
const timed = r => Number.isFinite(r.source_start) && Number.isFinite(r.dub_start ?? r.start) && Number.isFinite(r.dub_end ?? r.end);
const interval = (r, original = false) => original || !timed(r) ? [sourceStart(r), sourceEnd(r)] : [r.dub_start ?? r.start, r.dub_end ?? r.end];

function tokenFor(id) {
  try {
    return localStorage.getItem(`dub-token:${id}`) || "";
  } catch {
    return "";
  }
}
const PENDING_CREATE_KEY = "dub:pending-create:v1";

function canonicalCreateBody(url, langs) {
  return JSON.stringify({
    url: url.trim(),
    langs: [...new Set(langs)].sort()
  });
}

function parsePendingCreate(raw) {
  try {
    const pending = JSON.parse(raw);
    if (!pending || typeof pending.body !== "string" || typeof pending.key !== "string" || !/^[a-f0-9]{64}$/.test(pending.ownerToken)) return null;
    const body = JSON.parse(pending.body);
    if (typeof body.url !== "string" || !Array.isArray(body.langs) || !body.langs.length || body.langs.some(lang => typeof lang !== "string")) return null;
    if (canonicalCreateBody(body.url, body.langs) !== pending.body) return null;
    return pending;
  } catch {
    return null;
  }
}

function makePendingCreate(body, existing, uuid, randomBytes) {
  if (existing?.body === body) return existing;
  return {
    body,
    key: uuid(),
    ownerToken: Array.from(randomBytes(), byte => byte.toString(16).padStart(2, "0")).join("")
  };
}
let pendingCreate = null;
try {
  pendingCreate = parsePendingCreate(localStorage.getItem(PENDING_CREATE_KEY));
} catch {}
let creating = false;

function currentCreateBody() {
  return canonicalCreateBody($("#url").value, [...document.querySelectorAll("#langs input:checked")].map(x => x.value));
}

function renderPendingCreate() {
  $("#pending-create").hidden = recordedMode || !pendingCreate;
  if (pendingCreate) {
    const body = JSON.parse(pendingCreate.body);
    $("#pending-create-description").textContent = `Saved request: ${body.url} (${body.langs.map(lang=>LANG[lang]||lang).join(", ")})`;
  }
  $("#resume-create").disabled = creating;
  if (!creating) $("#go").textContent = pendingCreate ? (currentCreateBody() === pendingCreate.body ? "Resume this request" : "Start different dub") : "Create my dubs";
}
async function createFromBody(requestBody) {
  if (recordedMode || creating) return;
  const err = $("#err");
  err.hidden = true;
  creating = true;
  $("#go").disabled = true;
  $("#go").textContent = "Starting…";
  try {
    const saved = makePendingCreate(requestBody, pendingCreate, () => crypto.randomUUID(), () => crypto.getRandomValues(new Uint8Array(32)));
    // Persist recovery material before dispatch. Storage failure must not create an unrecoverable job.
    try {
      localStorage.setItem(PENDING_CREATE_KEY, JSON.stringify(saved));
    } catch {
      throw Error("Browser storage is unavailable. Enable it before creating a dub so this request can be recovered.");
    }
    pendingCreate = saved;
    renderPendingCreate();
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": saved.key,
        "X-Job-Token": saved.ownerToken
      },
      body: saved.body
    });
    const body = await response.json();
    if (!response.ok) throw Error(typeof body.detail === "string" ? body.detail : "Could not start the job. Resume the saved request to try again.");
    if (!body.id) throw Error("The server response did not contain a job. Resume the saved request to recover it.");
    // Keep pending recovery intact until durable owner access has been saved.
    localStorage.setItem(`dub-token:${body.id}`, body.owner_token || saved.ownerToken);
    localStorage.removeItem(PENDING_CREATE_KEY);
    pendingCreate = null;
    history.pushState({}, "", `?job=${encodeURIComponent(body.id)}`);
    open(body.id);
  } catch (error) {
    err.textContent = error.message;
    err.hidden = false;
  } finally {
    creating = false;
    $("#go").disabled = false;
    renderPendingCreate();
  }
}
const MAX_LANGS = 4;
function addLangOption(code, checked) {
  let input = document.querySelector(`#langs input[value="${CSS.escape(code)}"]`);
  if (!input) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" value="${esc(code)}"><span lang="${esc(code)}">${esc(LANG[code] || code)}</span>`;
    $("#more-langs").before(label);
    input = label.querySelector("input");
  }
  input.checked = checked;
}
$("#more-langs").innerHTML += Object.keys(LANG).filter(code => !document.querySelector(`#langs input[value="${CSS.escape(code)}"]`))
  .map(code => `<option value="${esc(code)}">${esc(LANG[code])}</option>`).join("");
$("#more-langs").addEventListener("change", e => {
  if (e.target.value) addLangOption(e.target.value, true);
  e.target.value = "";
  renderPendingCreate();
});
$("#new").addEventListener("submit", e => {
  e.preventDefault();
  if (recordedMode) return;
  const body = currentCreateBody();
  const count = JSON.parse(body).langs.length;
  if (!count || count > MAX_LANGS) {
    $("#err").textContent = count ? `Pick up to ${MAX_LANGS} languages per video.` : "Pick at least one language.";
    $("#err").hidden = false;
    return;
  }
  createFromBody(body);
});
$("#resume-create").onclick = () => {
  if (!pendingCreate || creating) return;
  const body = JSON.parse(pendingCreate.body);
  $("#url").value = body.url;
  document.querySelectorAll("#langs input").forEach(input => input.checked = false);
  body.langs.forEach(code => addLangOption(code, true));
  createFromBody(pendingCreate.body);
};
$("#new").addEventListener("input", renderPendingCreate);
$("#new").addEventListener("change", renderPendingCreate);
renderPendingCreate();

function open(id) {
  unsub.forEach(u => u());
  unsub = [];
  const gen = ++generation;
  mediaGeneration++;
  state = {
    job: null,
    events: [],
    lines: {},
    track: "orig",
    lineLang: null,
    selected: 0
  };
  wantedTime = 0;
  wantedPlaying = false;
  $("#studio").hidden = false;
  document.body.classList.add("in-studio");
  heroPause();
  $("#log").innerHTML = "";
  $("#tx").innerHTML = '<li class="muted pad">Transcript is not ready yet.</li>';
  $("#inspector").innerHTML = '<p class="muted">Choose a segment when transcript data is ready.</p>';
  ["#lines-wrap", "#timeline-wrap"].forEach(s => $(s).hidden = true);
  ["#stats", "#tracks", "#downloads", "#result-summary"].forEach(s => $(s).innerHTML = "");
  const v = $("#video");
  v.pause();
  v.removeAttribute("src");
  delete v.dataset.url;
  v.innerHTML = "";
  v.load();
  $("#ph").hidden = false;
  $("#review-context").hidden = true;
  $("#speaker-legend").hidden = true;
  $("#stats-provenance").hidden = true;
  $("#caption-target").textContent = "Captions appear here during playback.";
  $("#caption-source").textContent = "";
  window.scrollTo({top: 0});
  const ref = doc(db, "jobs", id);
  const failed = () => {
    $("#j-status").textContent = "Could not load job data. Reload to try again.";
  };
  unsub.push(onSnapshot(ref, snap => {
    if (gen !== generation) return;
    if (!snap.exists()) {
      $("#j-title").textContent = "Job not found";
      return;
    }
    state.job = {
      id,
      ...snap.data()
    };
    renderJob();
  }, failed));
  unsub.push(onSnapshot(query(collection(ref, "events"), orderBy("t")), snap => {
    if (gen !== generation) return;
    state.events = snap.docs.map(d => d.data());
    renderLog();
    renderSteps();
    renderInspector();
  }, failed));
  unsub.push(onSnapshot(collection(ref, "lines"), snap => {
    if (gen !== generation) return;
    state.lines = Object.fromEntries(snap.docs.map(d => [d.id, d.data()]));
    renderContent();
    restoreOwnerPreview(id, gen);
  }, failed));
}

function mergeRecoveredPreview(draft, editId, edit) {
  // A text-only local draft must not hide a server-side active preview after reload.
  if (draft?.id && draft.id !== editId && ["queued", "running", "ready", "error"].includes(draft.preview?.status)) return null;
  return {
    ...draft,
    text: edit.text,
    revision: edit.revision,
    id: editId,
    preview: edit,
    submitting: false,
    restored: true
  };
}

function restoreOwnerPreview(id, gen) {
  if (!tokenFor(id) || state.editListener) return;
  state.editListener = true;
  unsub.push(onSnapshot(query(collection(db, "jobs", id, "edits"), orderBy("created", "desc"), limit(1)), snap => {
    if (gen !== generation) return;
    const latest = snap.docs[0];
    if (!latest) return;
    const edit = latest.data();
    if (!["queued", "running", "ready", "error"].includes(edit.status)) return;
    const key = `${id}:${edit.lang}:${edit.line_id}`;
    const merged = mergeRecoveredPreview(edits.get(key), latest.id, edit);
    if (!merged) return;
    edits.set(key, merged);
    state.lineLang = edit.lang;
    state.track = edit.lang;
    const index = rows(edit.lang).findIndex(r => r.id === edit.line_id);
    if (index >= 0) state.selected = index;
    renderJob();
  }, () => {}));
}

function openLocal(L) {
  state = {
    job: L.job,
    events: L.events,
    lines: L.lines,
    track: "en",
    lineLang: null,
    selected: 0
  };
  $(".hero").hidden = true;
  $("#examples").hidden = true;
  $("#how").hidden = true;
  document.querySelectorAll('.bar nav a[href="#how"], .bar nav a[href="#examples"]').forEach(link => link.hidden = true);
  $("#studio").hidden = false;
  document.body.classList.add("in-studio");
  renderJob();
  renderLog();
  renderSteps();
  renderContent();
}

function renderJob() {
  const j = state.job;
  if (!j) return;
  $("#worker-check").hidden = recordedMode || !tokenFor(j.id) || !looksStalled(j);
  $("#j-title").textContent = j.title || j.report?.title || j.url;
  $("#source-caption-note").textContent = j.source_captioned === false ?
    "Caption-free source. Choose below-video or on-video captions without overlapping the original speech captions." :
    "Text burned into the original video cannot be removed by this player. For a clean dub, use a source without burned-in captions.";
  $("#j-yt").href = safeUrl(j.url);
  const context = [],
    concise = [];
  if (j.source_interval && Number.isFinite(j.source_interval.start) && Number.isFinite(j.source_interval.end)) concise.push(`${Math.round(j.source_interval.end-j.source_interval.start)}-second excerpt`);
  const people = Object.values(j.report?.speakers || j.speakers || {});
  if (people.length && people.every(person => person?.voice_type === "preset")) concise.push("AI preset voices");
  if (j.source_interval && Number.isFinite(j.source_interval.start) && Number.isFinite(j.source_interval.end)) concise.push(`Source ${mmss(j.source_interval.start)}–${mmss(j.source_interval.end)}`);
  if (j.voice_disclosure) context.push(j.voice_disclosure);
  if (j.alignment_provenance) context.push(`Source alignment: ${j.alignment_provenance}.`);
  if (j.validation_scope === "prepared_source_turns") context.push("Generation validation from prepared speaker turns. This sample does not demonstrate automatic transcription or speaker identification.");
  $("#review-context").hidden = !context.length && !concise.length;
  $("#review-context").innerHTML = `${concise.length?`<p class="review-summary">${esc(concise.join(" · "))}</p>`:""}${context.length?`<details><summary>Sample details</summary><div>${context.map(text=>`<p>${esc(text)}</p>`).join("")}</div></details>`:""}`;
  const running = !recordedMode && ["running", "queued"].includes(j.status);
  $("#j-status").textContent = ({
    done: "Finished",
    partial: "Partially finished · review failed languages",
    error: "Job failed",
    queued: liveStatus(j),
    running: liveStatus(j)
  })[j.status] || j.status;
  $("#activity-mode").textContent = running ? "Live events from this job. Completed languages become playable as they finish." : j.status === "error" ? "Recorded activity from a failed job. Any available language outputs can still be reviewed." : "Recorded activity from this job. Automated checks may still require human review.";
  $("#live-dot").classList.toggle("live", running);
  if (recordedMode) {
    $("#j-status").textContent = "Recorded local run · Review mode";
    $("#activity-mode").textContent = "Archived events from the supplied run. This view does not start generation or connect to live job data.";
  }
  $("#ph-img").src = safeUrl(j.thumbnail || "");
  $("#ph-text").textContent = j.status === "error" ? "This job failed. Please create a new job." :
    !j.stage || j.stage === "Queued" ? "Starting a Cloud Run worker… usually under a minute" : j.stage + "…";
  if (j.outputs) {
    renderTracks();
    renderStats();
  }
  renderSteps();
  renderOutcome();
}

// Mirrors the server's stale rule (server/app.py: QUEUE_TIMEOUT_SEC 600, LEASE_SEC 180).
function looksStalled(j) {
  const now = Date.now() / 1000;
  if (j.status === "queued") return now > (j.created || now) + 600;
  if (j.status === "running") return now > (j.lease_until || (j.heartbeat || j.started || now) + 180);
  return false;
}
// Elapsed time and the stalled check change without a Firestore update.
setInterval(() => {
  const j = state.job;
  if (recordedMode || !j || !["queued", "running"].includes(j.status)) return;
  $("#j-status").textContent = liveStatus(j);
  $("#worker-check").hidden = !tokenFor(j.id) || !looksStalled(j);
}, 1000);
function liveStatus(j) {
  const stage = j.stage && j.stage !== "Queued" ? j.stage : "Starting a worker";
  return `${stage} · ${mmss(Math.max(0, Date.now() / 1000 - (j.created || Date.now() / 1000)))}`;
}

$("#worker-check").onclick = async () => {
  const j = state.job,
    button = $("#worker-check"),
    message = $("#worker-check-status");
  if (recordedMode || !j || !tokenFor(j.id)) return;
  button.disabled = true;
  message.hidden = false;
  message.textContent = "Checking worker status…";
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(j.id)}/reconcile`, {
      method: "POST",
      headers: {
        "X-Job-Token": tokenFor(j.id)
      }
    });
    if (!response.ok) throw Error("Could not check this worker. Reload and try again.");
    message.textContent = "Worker status checked. Expired processing is marked failed; a failed preview can be discarded.";
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
  }
};

function languageOutcome(job, language, lineData) {
  const output = job.outputs || {};
  const available = Boolean(output[`video.${language}.mp4`] || output[`dub.${language}.m4a`]);
  const report = (job.report?.langs || []).find(item => item.lang === language) || job.language_reports?.[language];
  const rows = lineData?.rows;
  const flags = rows?.length ? rows.filter(row => row.ok !== true).length :
    Number.isFinite(report?.lines) && Number.isFinite(report?.ok) ? Math.max(0, report.lines - report.ok) : null;
  const failed = (job.report?.failures || []).some(item => item.lang === language);
  const running = ["queued", "running"].includes(job.status);
  return { available, flags, label: available ? flags > 0 ? "Needs attention" : flags === 0 ? "Checks passed" : "Checks unavailable" : failed || !running ? "Unavailable" : "Processing" };
}

function renderOutcome() {
  const j = state.job;
  if (!j) return;
  const source = j.report?.src || j.src;
  const languages = [...new Set([...(j.langs || []), ...(j.report?.langs || []).map(item => item.lang), ...Object.keys(state.lines)])].filter(lang => lang !== source);
  const results = languages.map(lang => languageOutcome(j, lang, state.lines[lang]));
  document.querySelectorAll(".download-status[data-language]").forEach(element => {
    const result = languageOutcome(j, element.dataset.language, state.lines[element.dataset.language]);
    element.textContent = result.label;
    element.classList.toggle("flagged", result.flags > 0);
  });
  const ready = results.filter(item => item.available).length;
  const flags = results.reduce((total, item) => total + (item.flags || 0), 0);
  const unavailable = results.filter(item => item.label === "Unavailable").length;
  const pending = results.filter(item => item.label === "Processing").length;
  const unknown = results.filter(item => item.available && item.flags === null).length;
  const notes = [];
  if (ready) notes.push(`${ready} language version${ready === 1 ? "" : "s"} available.`);
  if (flags) notes.push(`${flags} line${flags === 1 ? " needs" : "s need"} attention. Open quality checks before using affected tracks.`);
  if (unavailable) notes.push(`${unavailable} language version${unavailable === 1 ? " is" : "s are"} unavailable.`);
  if (pending) notes.push(`${pending} still processing.`);
  if (unknown) notes.push("Some outputs have no loaded quality results yet.");
  if (ready && !flags && !unavailable && !unknown) notes.push("Switch languages to listen, then download. Automated checks are not a human quality guarantee.");
  $("#result-summary").textContent = notes.join(" ") || "Your language versions will appear here as they finish.";
  $("#result-summary").classList.toggle("needs-attention", flags > 0 || unavailable > 0);
}

function renderTracks() {
  const j = state.job;
  if (!j?.outputs) return;
  const focusedTrack = $("#tracks").contains(document.activeElement) ? document.activeElement.dataset.l : null;
  const out = j.outputs;
  const available = Object.keys(out).filter(k => /^video\..+\.mp4$/.test(k)).map(k => k.slice(6, -4));
  const requested = [...new Set([...(j.langs || []), ...(j.report?.langs || []).map(l => l.lang), ...Object.keys(state.lines), ...available.filter(x => x !== "orig")])].filter(l => l !== (j.report?.src || j.src));
  if (!state.trackChosen && state.track === "orig") {
    const firstDub = ["en", "ja", "zh-Hans", "ko"].find(l => l !== (j.report?.src || j.src) && available.includes(l));
    if (firstDub) state.track = state.lineLang = firstDub;
  }
  if (!available.includes(state.track) && available.length) state.track = available.includes("orig") ? "orig" : available[0];
  $("#tracks").innerHTML = ["orig", ...requested].map(l => {
    const ready = available.includes(l);
    const ls = j.language_states?.[l] || (j.completed_langs?.includes(l) ? "Finished" : j.language_reports?.[l]?.status || j.status);
    return `<button data-l="${esc(l)}" aria-pressed="${l===state.track}" ${ready?"":"disabled"}>${esc(l==="orig"?"Original · "+(LANG[j.report?.src||j.src]||"source"):LANG[l]||l)}${ready?"":`<small>${esc(typeof ls==="string"?ls:ls?.status||"Pending")}</small>`}</button>`;
  }).join("");
  $("#tracks").querySelectorAll("button").forEach(b => b.onclick = () => selectTrack(b.dataset.l));
  if (available.includes(state.track)) {
    $("#ph").hidden = true;
    setVideo(out[`video.${state.track}.mp4`], out[`subs.${state.track==="orig"?(j.report?.src||j.src):state.track}.vtt`]);
  }
  $("#downloads").innerHTML = requested.map(l => {
    const audio = safeUrl(out[`dub.${l}.m4a`]);
    const sub = safeUrl(out[`subs.${l}.srt`]);
    const video = safeUrl(out[`video.${l}.mp4`]);
    const quality = languageOutcome(j, l, state.lines[l]);
    return audio || sub || video ? `<div class="download-language"><b>${esc(LANG[l]||l)}</b><span data-language="${esc(l)}" class="download-status ${quality.flags > 0 ? "flagged" : ""}">${esc(quality.label)}</span><div>${video?`<a href="${esc(video)}" download aria-label="Download ${esc(LANG[l]||l)} video">Video</a>`:""}${audio?`<a href="${esc(audio)}" download aria-label="Download ${esc(LANG[l]||l)} audio">Audio</a>`:""}${sub?`<a href="${esc(sub)}" download aria-label="Download ${esc(LANG[l]||l)} subtitles">Subtitles</a>`:""}</div></div>` : "";
  }).join("");
  renderContent();
  if (focusedTrack) [...$("#tracks").querySelectorAll("button")].find(button => button.dataset.l === focusedTrack)?.focus({preventScroll:true});
}

function selectTrack(l) {
  state.track = l;
  state.trackChosen = true;
  if (l !== "orig") state.lineLang = l;
  renderTracks();
}

function setVideo(url, vtt) {
  const v = $("#video");
  url = safeUrl(url);
  if (!url || v.dataset.url === url) return;
  const version = ++mediaGeneration;
  wantedTime = v.readyState >= 1 ? v.currentTime : wantedTime;
  wantedPlaying = v.readyState >= 1 ? !v.paused : wantedPlaying;
  v.dataset.url = url;
  v.innerHTML = vtt ? `<track kind="subtitles" label="Selected language" srclang="${esc(state.track==="orig"?state.job.report?.src||state.job.src||"ko":state.track)}" src="${esc(safeUrl(vtt))}">` : "";
  v.src = url;
  v.onloadedmetadata = () => {
    if (version !== mediaGeneration) return;
    v.currentTime = Math.min(wantedTime, Math.max(0, v.duration - .1));
    applySubs();
    if (wantedPlaying) v.play().catch(() => {});
  };
}

function seek(t) {
  const v = $("#video");
  wantedTime = Math.max(0, t);
  if (v.readyState >= 1) v.currentTime = wantedTime;
  highlight();
}

function choose(l, i) {
  state.selected = i;
  if (l !== state.track) selectTrack(l);
  const r = rows(l === "orig" ? activeLang() : l)[i];
  if (r) seek(interval(r, l === "orig")[0]);
  renderInspector();
  renderTimeline();
}

function applySubs() {
  const mode = $("#caption-mode").value;
  // "On video" is drawn by the page so the source line can sit under the dub line.
  [...$("#video").textTracks].forEach(t => t.mode = "hidden");
  $("#caption-display").hidden = mode !== "below";
  $("#caption-overlay").hidden = mode !== "overlay";
  highlight();
}
$("#caption-mode").onchange = applySubs;
$("#source-subs").onchange = highlight;
$("#timeline-seek").oninput = e => seek(+e.target.value);
let userScrolled = 0;
$("#tx").onwheel = () => userScrolled = Date.now();
$("#tx").ontouchmove = () => userScrolled = Date.now();

function renderContent() {
  if (!state.lineLang || !state.lines[state.lineLang]) state.lineLang = Object.keys(state.lines)[0];
  renderOutcome();
  renderSpeakers();
  renderTranscript();
  renderLines();
  renderTimeline();
  renderInspector();
  highlight();
}

function speakerIdentity(row, speakers) {
  const id = row.spk == null ? "" : String(row.spk);
  if (!id) return null;
  const entry = Array.isArray(speakers) ? speakers.find(s => String(s.spk ?? s.id) === id) : speakers?.[id];
  // Diarization ids ("0:1") mean nothing to a viewer; number speakers in the order the cast lists them.
  const order = (Array.isArray(speakers) ? speakers.map(s => String(s.spk ?? s.id)) : Object.keys(speakers || {})).indexOf(id);
  const label = order >= 0 ? `Speaker ${order + 1}` : `Speaker ${id}`;
  if (typeof entry === "string") return {
    id,
    name: entry,
    voice: "",
    voiceType: ""
  };
  return {
    id,
    name: entry?.name || entry?.label || label,
    voice: entry?.voice || "",
    voiceType: entry?.voice_type || ""
  };
}

function speakerIds() {
  return [...new Set(Object.values(state.lines).flatMap(data => (data.rows || []).filter(row => row.spk != null).map(row => String(row.spk))))].sort();
}

function speakerFor(row) {
  const person = speakerIdentity(row, state.job?.report?.speakers || state.job?.speakers || {});
  const n = person ? speakerIds().indexOf(person.id) : -1;
  return person && n >= 0 && person.name === `Speaker ${person.id}` ? { ...person, name: `Speaker ${n + 1}` } : person;
}

function speakerColor(id) {
  const ids = speakerIds();
  return ["var(--spk-0)", "var(--spk-1)", "var(--spk-2)", "var(--spk-3)"][Math.max(0, ids.indexOf(id)) % 4];
}

function multiSpeaker() {
  return new Set(Object.values(state.lines).flatMap(data => (data.rows || []).map(row => String(row.spk ?? "")))).size > 1;
}

function speakerBadge(row) {
  const person = multiSpeaker() ? speakerFor(row) : null;
  return person ? `<span class="speaker-badge" style="--speaker:${speakerColor(person.id)}">${esc(person.name)}</span>` : "";
}

function renderSpeakers() {
  const seen = new Map();
  Object.values(state.lines).forEach(data => (data.rows || []).forEach(row => {
    const person = speakerFor(row);
    if (person) seen.set(person.id, person);
  }));
  const host = $("#speaker-legend");
  host.hidden = seen.size < 2;
  host.innerHTML = [...seen.values()].map(person => `<span>${speakerBadge({spk:person.id})}${person.voiceType==="preset"?'<small>AI preset voice</small>':person.voiceType==="clone"?'<small>Consented cloned voice</small>':""}</span>`).join("");
}

function renderTranscript() {
  const rs = rows(activeLang());
  if (!rs.length) return;
  $("#tx").innerHTML = rs.map((r, i) => `<li data-i="${i}"><button type="button" data-i="${i}"><time>${mmss(interval(r,state.track==="orig")[0])}</time><span>${speakerBadge(r)}<span class="srctext">${esc(r.src)}</span>${state.track!=="orig"?`<span class="dubtext">${esc(r.text)}</span>`:""}</span></button></li>`).join("");
  $("#tx").querySelectorAll("button").forEach(b => b.onclick = () => choose(state.track, +b.dataset.i));
}

function highlight() {
  const v = $("#video"),
    t = v.readyState >= 1 ? v.currentTime : wantedTime;
  const rs = rows(activeLang());
  const idx = rs.findIndex(r => {
    const [a, b] = interval(r, state.track === "orig");
    return t >= a && t < b;
  });
  $("#tx").querySelectorAll("li").forEach((li, i) => li.classList.toggle("now", i === idx));
  const r = rs[idx];
  const spoken = x => String(x || "").replace(/\[[^\]]*\]\s*/g, "").trim();  // drop [laughter]-style tags
  $("#caption-target").textContent = r ? spoken(state.track === "orig" ? r.src : r.text) : "";
  $("#caption-source").hidden = !$("#source-subs").checked || state.track === "orig";
  $("#caption-source").textContent = spoken(r?.src);
  $("#ov-target").textContent = $("#caption-target").textContent;
  $("#ov-source").textContent = spoken(r?.src);
  $("#ov-source").hidden = $("#caption-source").hidden || !r;
  $("#caption-overlay").classList.toggle("empty", !r);
  $("#timeline-seek").value = t;
  $("#timeline-clock").textContent = mmss(t) + " / " + mmss(duration());
  document.querySelectorAll(".playhead").forEach(x => x.style.left = `${Math.min(100,t/duration()*100)}%`);
  if (idx !== state.txNow) {
    state.txNow = idx;
    // While playing, the inspector follows the spoken line unless the creator is editing one.
    const editing = $("#inspector").contains(document.activeElement) || $("#line-editor")?.querySelector("audio, .draft");
    if (idx >= 0 && !v.paused && !editing && idx !== state.selected) {
      state.selected = idx;
      renderInspector();
      document.querySelectorAll(".interval.selected").forEach(x => x.classList.remove("selected"));
      document.querySelectorAll(`.interval[data-l="${CSS.escape(state.track)}"][data-i="${idx}"]`).forEach(x => x.classList.add("selected"));
    }
    const li = $("#tx").querySelector(`li[data-i="${idx}"]`);
    if (li && Date.now() - userScrolled > 4000) $("#tx").scrollTop = li.offsetTop - $("#tx").clientHeight / 3;
  }
}
$("#video").addEventListener("timeupdate", highlight);
$("#video").addEventListener("seeked", highlight);
$("#video").addEventListener("error", () => {
  $("#ph").hidden = false;
  $("#ph-text").textContent = "Media could not load. Select another ready language or reload.";
});

function renderTimeline() {
  const ls = Object.keys(state.lines);
  if (!ls.length) return;
  $("#timeline-wrap").hidden = false;
  const d = duration();
  $("#timeline-seek").max = d;
  const exact = ls.every(l => rows(l).every(timed));
  $("#timing-note").textContent = exact ? "Source speech intervals and measured dubbed placement. Amber marks a recovered failed check; a dotted underline marks a timing refinement. Select a line to inspect its actions." : "Older runs show recorded source intervals on each lane, not measured dub placement or waveforms. Amber marks a recovered failed check; a dotted underline marks a timing refinement.";
  $("#ruler").innerHTML = Array.from({
    length: 7
  }, (_, i) => `<span style="left:${i/6*100}%">${mmss(d*i/6)}</span>`).join("");
  $("#lanes").innerHTML = ["orig", ...ls].map(l => `<div class="timeline-lane"><div class="lane-name">${esc(l==="orig"?"Original":LANG[l]||l)}<small>${l==="orig"?"Source speech":rows(l).every(timed)?"Measured placement":"Source intervals"}</small></div><div class="lane-slots">${rows(l==="orig"?ls[0]:l).map((r,i)=>{const [a,b]=interval(r,l==="orig");const change=timelineChange(r,l==="orig");const person=speakerFor(r);return `<button class="interval ${l} ${change.className} ${state.selected===i&&state.track===l?"selected":""}" style="${person?`--speaker:${speakerColor(person.id)};border-top:3px solid var(--speaker);`:""}left:${Math.max(0,a/d*100)}%;width:${Math.max(.2,(Math.min(d,b)-a)/d*100)}%" data-l="${esc(l)}" data-i="${i}" aria-label="${esc(l==="orig"?"Original":LANG[l]||l)} line ${i+1}${person?", "+esc(person.name):""}, ${mmss(a)}${change.label?", "+change.label:""}">${b-a>5&&person&&multiSpeaker()?esc(person.name.split(" ")[0])+" · ":""}${b-a>3?i+1:""}</button>`;}).join("")}<div class="playhead"></div></div></div>`).join("");
  $("#lanes").querySelectorAll("button").forEach(b => b.onclick = () => choose(b.dataset.l, +b.dataset.i));
  highlight();
}

function failedAudioAttempts(row, outputs) {
  return (row.actions || []).filter(action => action.do === "check")
    .map((action, index) => ({
      action,
      attempt: index + 1
    }))
    .filter(({
      action
    }) => action.ok === false && typeof action.audio_key === "string" && typeof outputs?.[action.audio_key] === "string");
}

function renderFailedAuditions(row) {
  const host = $("#failed-auditions");
  const attempts = failedAudioAttempts(row, state.job?.outputs)
    .map(item => ({
      ...item,
      url: safeUrl(state.job.outputs[item.action.audio_key])
    })).filter(item => item.url);
  if (!attempts.length) return;
  host.innerHTML = '<h4>Listen to the failed attempts</h4><p class="caption-note">These are saved audio clips from actual failed checks. The main player keeps its position.</p>' + attempts.map(({
    action,
    attempt,
    url
  }) => `<div class="failed-attempt"><p><b>Failed attempt ${attempt}</b>${action.issue?`<span>${esc(action.issue)}</span>`:""}</p>${action.text?`<p class="attempt-text">Expected text: ${esc(action.text)}</p>`:""}<audio controls preload="metadata" src="${esc(url)}" aria-label="Failed attempt ${attempt}"></audio></div>`).join("");
}

// A/B listening never overlaps the source, an archived failure or an edit preview.
document.addEventListener("play", event => {
  if (!["AUDIO", "VIDEO"].includes(event.target.tagName)) return;
  document.querySelectorAll("audio,video").forEach(media => {
    if (media !== event.target) media.pause();
  });
}, true);

function lineActionLabel(action) {
  switch (action.do) {
    case "check":
      return action.ok ? "Listening check passed" : "Check flagged: " + (action.issue || "needs review");
    case "resynth":
      return "Generated this line again";
    case "retranslate":
      return "Re-translated: " + (action.text || "");
    case "shorten":
      return "Shortened to fit the slot: " + (action.text || "");
    case "lengthen":
      return "Expanded the translation to reduce silence: " + (action.text || "");
    case "translation_flag":
      return "Translation needs review: " + (action.issue || "validation failed");
    case "flag":
      return "Flagged for human review: " + (action.issue || "automatic repair could not resolve this line");
    case "synth":
      return "Generated speech";
    default:
      return action.do || "Recorded action";
  }
}

function canAcceptPreview(preview, acknowledged) {
  return preview?.status === "ready" && (preview.row?.ok === true || acknowledged === true);
}

function renderInspector() {
  const l = activeLang(),
    rs = rows(l);
  if (!rs.length) return;
  state.selected = Math.min(state.selected, rs.length - 1);
  const r = rs[state.selected];
  $("#inspect-label").textContent = `${LANG[l]||l} · line ${state.selected+1}`;
  const actions = state.events.filter(a => a.kind === "line" && a.lang === l && a.id === (r.id ?? state.selected));
  const hist = actions.length ? actions : r.actions || [];
  $("#inspector").innerHTML = `${speakerBadge(r)}<p class="inspect-source">${esc(r.src)}</p><p class="inspect-target">${esc(r.text)}</p><div class="inspect-facts"><span>Source slot <b>${Number(r.slot||0).toFixed(2)} s</b></span><span>Clip duration <b>${Number(r.dur||0).toFixed(2)} s</b></span><span>Tempo <b>${Number(r.tempo||1).toFixed(3)}×</b></span></div><p class="verdict ${r.ok?"pass":"flag"}">${r.ok?"Passed automated listening check":"Flagged for review"}${r.issue?": "+esc(r.issue):""}</p><ol class="repair-history">${hist.map(a=>{const t=a.t?`<time>Run +${mmss(a.t-(state.events[0]?.t||a.t))}</time>`:"";const text=lineActionLabel(a);return `<li>${t}${esc(text)}</li>`;}).join("")}</ol><p class="caption-note">Automated verification is not a human quality rating. Listen before publishing.</p><div id="failed-auditions"></div><div id="line-editor"></div>`;
  renderFailedAuditions(r);
  renderEditor(r, l);
}
const edits = new Map();

function renderEditor(r, l) {
  const j = state.job,
    token = tokenFor(j?.id),
    host = $("#line-editor");
  if (recordedMode || !j?.can_regenerate || !token || !["done", "partial"].includes(j.status)) return;
  const lineId = r.id ?? state.selected;
  const stillSelected = () => state.job?.id === j.id && activeLang() === l && (rows(l)[state.selected]?.id ?? state.selected) === lineId;
  const key = `${j.id}:${l}:${lineId}`;
  const draft = edits.get(key) || {
    text: r.text,
    revision: j.revision || 0
  };
  edits.set(key, draft);
  const busy = draft.submitting || ["queued", "running"].includes(draft.preview?.status);
  const ready = draft.preview?.status === "ready";
  const failed = draft.preview?.status === "error";
  const status = draft.message || (busy ? "Generating a draft preview. The published track stays unchanged." : ready ? "Preview is ready. Listen before accepting this change." : "");
  host.innerHTML = `<form class="edit-form"><label for="edit-text">Edit this translated line</label><textarea id="edit-text" ${busy||ready||failed?"disabled":""}>${esc(draft.text)}</textarea><p class="caption-note">Generate a draft preview, then listen and accept it. This uses voice generation. ${j.edits_remaining??5} preview attempts remaining for this job.</p><button type="submit" ${busy||ready||failed||j.edits_remaining===0?"disabled":""}>${busy?"Generating preview…":"Generate preview"}</button><p class="edit-status" role="status">${esc(status)}</p>${ready?'<p class="label">Current audio</p><audio id="current-audio" aria-label="Current published language audio" controls preload="metadata"></audio><p class="label">Draft preview</p><audio id="preview-audio" aria-label="Draft edited language preview" controls preload="metadata"></audio><button type="button" id="preview-accept">Accept preview</button> <button type="button" id="preview-discard">Discard preview</button>':failed?'<button type="button" id="preview-discard">Discard failed preview</button>':""}</form>`;
  host.querySelector("textarea").oninput = e => draft.text = e.target.value;
  const post = async (path, body) => {
    const res = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Job-Token": token
      },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw Error(typeof data.detail === "string" ? data.detail : "Request failed. Reload the job and try again.");
    return data;
  };
  host.querySelector("form").onsubmit = async e => {
    e.preventDefault();
    if (!draft.text.trim()) {
      draft.message = "Enter the translated text first.";
      renderEditor(r, l);
      return;
    }
    draft.submitting = true;
    draft.message = "";
    draft.revision = j.revision || 0;
    renderEditor(r, l);
    try {
      const out = await post(`/api/jobs/${encodeURIComponent(j.id)}/lines/${encodeURIComponent(l)}/${r.id??state.selected}/regenerate`, {
        text: draft.text,
        revision: draft.revision
      });
      draft.id = out.edit_id;
      draft.preview = {
        status: out.status
      };
      const jobId = j.id;
      unsub.push(onSnapshot(doc(db, "jobs", j.id, "edits", out.edit_id), snap => {
        if (!snap.exists()) return;
        draft.preview = snap.data();
        draft.message = draft.preview.status === "error" ? "Preview failed. Your published track is unchanged." : "";
        if (state.job?.id === jobId && activeLang() === l && rows(l)[state.selected]?.id === r.id) renderEditor(r, l);
      }, () => {
        draft.message = "Could not read preview status. Reload this job to try again.";
        if (stillSelected()) renderEditor(r, l);
      }));
    } catch (x) {
      draft.message = x.message;
    } finally {
      draft.submitting = false;
      if (stillSelected()) renderEditor(r, l);
    }
  };
  if (ready) {
    const passed = draft.preview.row?.ok === true;
    const verdict = document.createElement("div");
    verdict.className = "preview-verdict";
    verdict.innerHTML = `<p class="verdict ${passed?"pass":"flag"}"><b>${passed?"Preview passed automated checks":"Preview needs review"}</b>${draft.preview.row?.issue?": "+esc(draft.preview.row.issue):passed?"":". Automated checks failed or no passing verdict is available."}</p>${passed?"":'<label class="accept-override"><input type="checkbox" id="accept-override"> Accept despite failed automated checks</label>'}`;
    host.querySelector("#preview-audio").before(verdict);
    const accept = host.querySelector("#preview-accept");
    accept.disabled = !canAcceptPreview(draft.preview, false);
    const override = host.querySelector("#accept-override");
    if (override) override.onchange = () => {
      accept.disabled = !canAcceptPreview(draft.preview, override.checked);
    };
  }
  if (ready || failed) {
    const current = host.querySelector("#current-audio");
    const audio = host.querySelector("#preview-audio");
    if (current) {
      current.src = safeUrl(j.outputs?.[`dub.${l}.m4a`]);
      current.onloadedmetadata = () => {
        current.currentTime = Math.min(r.dub_start ?? r.start, current.duration);
      };
      current.onplay = () => {
        audio?.pause();
        $("#video").pause();
      };
    }
    if (audio) audio.onplay = () => {
      current?.pause();
      $("#video").pause();
    };
    if (audio) audio.src = safeUrl(draft.preview.outputs?.[`dub.${l}.m4a`]);
    if (audio) audio.onloadedmetadata = () => {
      audio.currentTime = Math.min(draft.preview.row?.dub_start ?? draft.preview.row?.start ?? r.start, audio.duration);
    };
    for (const action of (ready ? ["accept", "discard"] : ["discard"])) {
      host.querySelector(`#preview-${action}`).onclick = async () => {
        if (action === "accept" && !canAcceptPreview(draft.preview, host.querySelector("#accept-override")?.checked)) return;
        host.querySelectorAll("button").forEach(b => b.disabled = true);
        try {
          await post(`/api/jobs/${encodeURIComponent(j.id)}/edits/${encodeURIComponent(draft.id)}/${action}`, {
            revision: draft.revision
          });
          draft.preview = null;
          draft.message = action === "accept" ? "Preview accepted. The updated track is being loaded." : "Preview discarded. The published track is unchanged.";
          if (action === "accept") {
            draft.revision++;
            delete $("#video").dataset.url;
            renderJob();
          }
        } catch (x) {
          draft.message = x.message;
        }
        if (stillSelected()) renderEditor(r, l);
      };
    }
  }
}

function evText(e) {
  const L = e.lang ? `[${e.lang}${e.id !== undefined ? ` #${e.id}` : ""}] ` : "";
  switch (e.kind) {
    case "start":
      return ["stage", `Fetched “${e.title}” · ${mmss(e.duration)}`];
    case "voice":
      return ["stage", e.voice === "pending_verification" ? "Voice: consent recorded; speaker verification is pending" : e.consent ? "Voice: channel consent recorded; final voice selection requires a speaker match" : "Voice: preset Gemini voice (no channel consent on file)"];
    case "separated":
      return ["stage", "Separated speech from music and effects"];
    case "cast":
      return ["stage", "Voice cast: " + (e.speakers || []).map((c) =>
        `S${c.spk} → ${c.why?.startsWith("creator") ? "creator's cloned voice" : c.voice}${c.match !== undefined ? ` (voice match ${c.match})` : ""}`).join(" · ")];
    case "transcribed":
      return ["stage", `Chirp 3: ${e.words} words with timestamps`];
    case "proofread":
      return ["stage", `Gemini listened and corrected the transcript → ${e.cues} lines (${LANG[e.src] || e.src})`];
    case "brief":
      return ["stage", `Brief: ${e.terms} term rules · ${String(e.summary).split(". ")[0]}.`];
    case "translated":
      return ["stage", `${L}translated ${e.lines} lines to their time budgets`];
    case "voiced":
      return ["stage", e.para_lines > 0 ? `${L}prepared ${e.para_lines}/${e.lines} lines from paragraph takes` : `${L}prepared per-line speech synthesis for ${e.lines} lines`];
    case "language_done":
      return ["stage", `${L}mixed · ${e.ok}/${e.lines} verified · drift p95 ${e.late_p95}s`];
    case "done":
      return ["stage", `Finished in ${mmss(e.sec_total)}`];
    case "line":
      if (["lengthen", "translation_flag", "flag"].includes(e.do)) return [e.do === "lengthen" ? "fix" : "bad", L + lineActionLabel(e)];
      if (e.do === "shorten") return ["fix", `${L}ran long → rewrote shorter: “${e.text}”`];
      if (e.do === "resynth") return ["fix", `${L}re-synthesizing`];
      if (e.do === "retranslate") return ["fix", `${L}re-translated: “${e.text}”`];
      if (e.do === "check") return e.ok ? ["good", `${L}✓ Gemini listened: correct`] : ["bad", `${L}Gemini heard a problem: ${e.issue}`];
      if (e.do === "synth" && !e.pre) return ["", `${L}synthesized ${e.dur}s for a ${e.slot}s slot`];
      return null;
    default:
      return null;
  }
}


function renderLog() {
  const t0 = state.events[0]?.t || 0;
  const items = state.events.map(x => {
    const label = evText(x);
    return label ? `<li class="${label[0]}"><time>${mmss(x.t-t0)}</time><span>${esc(label[1].replace("✓ Gemini listened: correct","✓ Automated listening check passed"))}</span></li>` : "";
  });
  const ol = $("#log"),
    stick = ol.scrollTop + ol.clientHeight >= ol.scrollHeight - 30;
  ol.innerHTML = items.join("");
  if (stick) ol.scrollTop = ol.scrollHeight;
  $("#log-count").textContent = `${items.filter(Boolean).length} events`;
}

function renderSteps() {
  const preparedExample = recordedMode || state.job?.validation_scope === "prepared_source_turns";
  $("#steps").hidden = preparedExample;
  if (preparedExample) return;
  const stages = [
    ["start", "Download"],
    ["transcribed", "Transcribe"],
    ["translated", "Translate"],
    ["voiced", "Speak"],
    ["line", "Check and repair"],
    ["done", "Complete"]
  ];
  const seen = new Set(state.events.map(x => x.kind));
  $("#steps").innerHTML = stages.map(([k, n]) => `<li class="${seen.has(k)?"done":""}">${n}</li>`).join("");
}

function renderStats() {
  const r = state.job?.report;
  if (!r?.langs?.length) return;
  const all = r.langs.reduce((n, l) => n + l.lines, 0),
    ok = r.langs.reduce((n, l) => n + l.ok, 0),
    first = r.langs.reduce((n, l) => n + l.first_pass_ok, 0);
  const serialValidation = Boolean(r.validation && r.timing_provenance);
  const preparedSource = state.job.validation_scope === "prepared_source_turns";
  const provenance = $("#stats-provenance");
  provenance.hidden = !r.timing_provenance && !preparedSource;
  provenance.textContent = preparedSource ? (r.timing_provenance || "Recorded local validation time. This is not an end-to-end pipeline benchmark.") : serialValidation ? "Local serial validation, measured from artifact timestamps. This is not concurrent job processing time or Cloud Run latency." : r.timing_provenance || "";
  $("#stats").innerHTML = [
    [`${ok} / ${all}`, "automated checks passed"],
    [`${all-ok}`, "lines flagged for review"],
    [`${ok-first}`, "failed-check recoveries"],
    [mmss(r.sec_total), preparedSource ? "local validation time" : serialValidation ? "serial validation time" : "recorded processing time"]
  ].map(([n, l]) => `<div class="stat"><b>${esc(n)}</b><span>${l}</span></div>`).join("");
}

function renderLines() {
  const ls = Object.keys(state.lines);
  if (!ls.length) return;
  $("#lines-wrap").hidden = false;
  const l = state.lineLang || ls[0];
  $("#line-lang").innerHTML = ls.map(k => `<button data-l="${esc(k)}" aria-pressed="${k===l}">${esc(LANG[k]||k)}</button>`).join("");
  $("#line-lang").querySelectorAll("button").forEach(b => b.onclick = () => {
    state.lineLang = b.dataset.l;
    renderLines();
  });
  const list = rows(l).map((r, i) => ({
    r,
    i
  })).filter(({
    r
  }) => !$("#only-fixed").checked || !r.ok || Object.values(lineChanges(r)).some(Boolean));
  $("#lines tbody").innerHTML = list.map(({
    r,
    i
  }) => `<tr><td><button class="time-button" data-i="${i}">${mmss(interval(r)[0])}</button></td><td class="src">${esc(r.src)}</td><td>${esc(r.text)}${!r.ok?`<span class="issue">Flagged: ${esc(r.issue||"Needs review")}</span>`:""}</td><td class="fit">${Number(r.dur||0).toFixed(1)}s / ${Number(r.slot||0).toFixed(1)}s</td><td><span class="chip ${r.ok?"ok":"bad"}">${r.ok?"Automated pass":"Flagged"}</span>${repaired(r)?'<span class="chip fix">Check recovered</span>':""}${lineChanges(r).timing?'<span class="chip">Timing refined</span>':""}${lineChanges(r).translation?'<span class="chip">Translation revised</span>':""}</td></tr>`).join("") || '<tr><td colspan="5">No adjusted or flagged lines.</td></tr>';
  $("#lines tbody").querySelectorAll("button").forEach(b => b.onclick = () => {
    choose(l, +b.dataset.i);
    $(".inspector-panel").open = true;
    $(".inspector-panel").scrollIntoView({
      behavior: motion(),
      block: "center"
    });
  });
}
$("#only-fixed").onchange = renderLines;

// Hero: one sample, every language, same playback position.
const hero = { job: null, lang: null };
function heroPause() {
  const v = $("#hero-video");
  if (v && !v.paused) v.pause();
}
function heroLoad(j) {
  const out = j.outputs || {};
  const src = j.report?.src || j.src || "ko";
  const langs = ["orig", ...Object.keys(out).filter(k => /^video\..+\.mp4$/.test(k)).map(k => k.slice(6, -4)).filter(l => l !== "orig" && l !== src).sort((x, y) => ["en", "ja", "zh-Hans", "ko"].indexOf(x) - ["en", "ja", "zh-Hans", "ko"].indexOf(y))];
  if (!out["video.orig.mp4"] || langs.length < 2) { $("#stage").hidden = true; return; }
  hero.job = j;
  const people = Object.values(j.report?.speakers || j.speakers || {});
  const cloned = people.some(p => p?.voice_type === "clone") || j.voice_type === "clone";
  $("#hero-langs").innerHTML = langs.map(l => {
    const code = l === "orig" ? src : l;
    return `<button type="button" data-l="${esc(l)}" lang="${esc(code)}" aria-pressed="false"><b>${esc(LANG[code] || code)}</b><small>${l === "orig" ? "ORIGINAL" : cloned ? "DUB · OWN VOICE" : "DUB"}</small></button>`;
  }).join("");
  $("#hero-langs").querySelectorAll("button").forEach(b => b.onclick = () => heroSelect(b.dataset.l, true));
  $("#hero-video").poster = safeUrl(j.thumbnail || "");
  heroSelect(langs.includes("en") ? "en" : langs[1], false);
}
function heroSelect(l, user) {
  const j = hero.job, v = $("#hero-video");
  if (!j) return;
  const src = j.report?.src || j.src || "ko";
  const code = l === "orig" ? src : l;
  const url = safeUrl(j.outputs[`video.${l}.mp4`]);
  if (!url) return;
  const t = v.readyState >= 1 ? v.currentTime : 0, playing = !v.paused;
  hero.lang = l;
  $("#hero-langs").querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.l === l)));
  const vtt = safeUrl(j.outputs[`subs.${code}.vtt`]);
  v.innerHTML = vtt ? `<track kind="subtitles" srclang="${esc(code)}" src="${esc(vtt)}" default>` : "";
  $("#hero-caption").textContent = "";
  $("#hero-caption").setAttribute("lang", code);
  v.src = url;
  v.onloadedmetadata = () => {
    v.currentTime = Math.min(t, Math.max(0, v.duration - .1));
    const track = v.textTracks[0];
    if (track) {
      track.mode = "hidden";
      track.oncuechange = () => $("#hero-caption").textContent = [...(track.activeCues || [])].map(c => c.text).join(" ");
    }
    if (playing || user) v.play().catch(() => {});
  };
}
$("#hero-play").onclick = () => $("#hero-video").play().catch(() => {});
$("#hero-video").addEventListener("play", () => { $("#hero-play").classList.add("playing"); $("#stage").classList.add("is-playing"); });
$("#hero-video").addEventListener("pause", () => { $("#hero-play").classList.remove("playing"); $("#stage").classList.remove("is-playing"); });
$("#hero-video").addEventListener("click", () => { const v = $("#hero-video"); v.paused ? v.play().catch(() => {}) : v.pause(); });
$("#hero-video").addEventListener("timeupdate", () => { $("#hero-time").textContent = mmss($("#hero-video").currentTime); });
async function loadExamples() {
  const snap = await getDocs(query(collection(db, "jobs"), where("demo", "==", true), limit(12)));
  const jobs = snap.docs.map(d => ({
    id: d.id,
    ...d.data()
  })).sort((a, b) => (b.created || 0) - (a.created || 0));
  const cards = $("#cards");
  const sampleButton = $("#sample-open");
  const featured = jobs.find(j => j.featured === true) || jobs.find(j => j.report?.src === "ko" && j.report.duration <= 180 && j.report.langs?.length >= 3) || jobs[0];
  if (featured) {
    sampleButton.disabled = false;
    sampleButton.textContent = "Open the studio";
    heroLoad(featured);
    sampleButton.onclick = () => {
      history.pushState({}, "", `?job=${encodeURIComponent(featured.id)}`);
      open(featured.id);
    };
  } else {
    sampleButton.textContent = "No samples yet";
    $("#stage").hidden = true;
  }
  cards.innerHTML = "";
  for (const j of jobs) {
    const c = $("#t-card").content.cloneNode(true);
    const a = c.querySelector("a");
    a.href = `?job=${encodeURIComponent(j.id)}`;
    a.onclick = e => {
      e.preventDefault();
      history.pushState({}, "", a.href);
      open(j.id);
    };
    c.querySelector("img").src = safeUrl(j.thumbnail);
    c.querySelector("b").textContent = j.title || "Dubbed sample";
    c.querySelector("span").textContent = `Finished sample · ${(j.report?.langs||[]).map(l=>LANG[l.lang]||l.lang).join(" / ")}`;
    cards.appendChild(c);
  }
  if (!jobs.length) cards.innerHTML = '<p class="muted">No finished samples are available yet.</p>';
  return jobs;
}
window.addEventListener("popstate", () => {
  if (recordedMode) {
    location.reload();
    return;
  }
  const id = new URLSearchParams(location.search).get("job");
  if (id) open(id);
  else {
    generation++;
    mediaGeneration++;
    unsub.forEach(stop => stop());
    unsub = [];
    wantedPlaying = false;
    wantedTime = 0;
    const video = $("#video");
    video.pause();
    video.removeAttribute("src");
    delete video.dataset.url;
    video.load();
    $("#studio").hidden = true;
    document.body.classList.remove("in-studio");
    state = {job:null,events:[],lines:{},track:"orig",lineLang:null,selected:0};
  }
});
async function loadRecordedManifest(reference) {
  const url = new URL(reference, location.href);
  const directory = new URL("./review/", location.href).pathname;
  if (url.origin !== location.origin || !url.pathname.startsWith(directory) || !url.pathname.endsWith(".json") || url.username || url.password || url.search || url.hash) throw Error("Choose a JSON manifest inside this site's review directory.");
  const response = await fetch(url, {
    credentials: "same-origin"
  });
  if (!response.ok) throw Error("The recorded review manifest could not load.");
  const data = await response.json();
  if (!data.job || !data.lines || typeof data.lines !== "object" || !Array.isArray(data.events)) throw Error("The review manifest needs job, lines and events.");
  const asset = value => {
    const u = new URL(value, url);
    if (u.origin !== location.origin || !u.pathname.startsWith(directory) || u.username || u.password) throw Error("Review media must stay inside this site's review directory.");
    return u.href;
  };
  data.job.outputs = Object.fromEntries(Object.entries(data.job.outputs || {}).map(([key, value]) => [key, asset(value)]));
  if (data.job.thumbnail) data.job.thumbnail = asset(data.job.thumbnail);
  data.job.can_regenerate = false;
  openLocal(data);
}
const initial = new URLSearchParams(location.search).get("job");
if (LOCAL) openLocal(LOCAL);
else if (reviewParam) {
  loadRecordedManifest(reviewParam).catch(error => {
    $(".hero").hidden = true;
    $("#examples").hidden = true;
    $("#how").hidden = true;
    $("#studio").hidden = false;
    document.querySelectorAll('.bar nav a[href="#how"], .bar nav a[href="#examples"]').forEach(link => link.hidden = true);
    $("#j-title").textContent = "Recorded review unavailable";
    $("#j-status").textContent = error.message;
  });
} else {
  if (initial) open(initial);
  loadExamples().catch(() => {
    $("#cards").innerHTML = '<p class="muted">Samples could not load. Reload to try again.</p>';
    $("#sample-open").textContent = "Samples unavailable";
    $("#stage").hidden = true;
  });
}
