/* SceneForge Studio - front end (plain JavaScript, no internet needed). */
"use strict";

// ----------------------------------------------------------------------------------------------- icons
const ICONS = {
  "plus-circle": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5 13.8 11.3 12 16l-1.8-4.7L5.5 9.5l4.7-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4z"/>',
  save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8M7 3v5h8"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M3 16h4M17 8h4M17 16h4M3 12h18"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  wave: '<path d="M2 12h2M6 8v8M10 5v14M14 8v8M18 10v4M22 12h-2"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  play: '<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4z"/>',
  "play-s": '<path d="m7 4 13 8-13 8z"/>',
  export: '<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 15v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  audio: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5M5 20h14"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  move: '<path d="M5 9l-3 3 3 3M9 5l3-3 3 3M15 19l-3 3-3-3M19 9l3 3-3 3M2 12h20M12 2v20"/>',
  layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>',
  type: '<path d="M4 7V4h16v3M9 20h6M12 4v16"/>',
  clip: '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 10 6-3v10l-6-3z"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  scissors: '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  "arrow-r": '<path d="M5 12h14M13 6l6 6-6 6"/>',
  open: '<path d="M14 3h7v7M21 3l-9 9"/><path d="M19 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>',
};
function icon(name, cls = "") { return `<svg class="i ${cls}" viewBox="0 0 24 24">${ICONS[name] || ""}</svg>`; }
function fillIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => { el.outerHTML = icon(el.dataset.icon); });
}

// ----------------------------------------------------------------------------------------------- utils
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function el(html) { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; }
function fmtT(sec) {
  if (sec === null || sec === undefined) return "–";
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}
function fmtDur(sec) {
  sec = Math.round(sec || 0);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : m ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}
function fmtSize(b) { return b > 1e9 ? (b / 1e9).toFixed(2) + " GB" : (b / 1e6).toFixed(1) + " MB"; }
function fmtDate(ts) { return new Date(ts * 1000).toLocaleString(); }
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private window */ } },
};

async function api(method, url, body) {
  const opt = { method, headers: {} };
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  let r;
  try { r = await fetch(url, opt); } catch (e) { throw new Error("SceneForge is not running. Start it again from the Desktop."); }
  let data = null;
  try { data = await r.json(); } catch (e) { /* not json */ }
  if (!r.ok) throw new Error((data && (data.error || data.detail)) || `Error ${r.status}`);
  return data;
}

function toast(msg, kind = "") {
  const t = el(`<div class="toast ${kind}">${esc(msg)}</div>`);
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), kind === "err" ? 9000 : 4000);
}
async function guard(fn) {
  try { return await fn(); } catch (e) { toast(e.message, "err"); console.error(e); }
}

// ----------------------------------------------------------------------------------------------- state
const S = {
  meta: null, presets: null, project: null, step: 1,
  draft: null,          // script text not yet saved
  draftName: null, draftInfo: null,
  job: null, jobPane: null,
  model: store.get("sf-model") || "small", language: store.get("sf-lang") || "en",
};

const STEPS = [
  { n: 1, name: "Script & Voice", icon: "mic" },
  { n: 2, name: "Scene Sync", icon: "wave" },
  { n: 3, name: "Media", icon: "image" },
  { n: 4, name: "Sync & Review", icon: "play" },
  { n: 5, name: "Export", icon: "export" },
];

const LABELS = {
  motion: { zoom_in: "Zoom in", zoom_out: "Zoom out", pan_left: "Pan left", pan_right: "Pan right", zoom_in_pan: "Zoom in + pan", zoom_out_pan: "Zoom out + pan" },
  easing: { ease_in_out: "Smooth start & stop", ease_in_out_sine: "Gentle (sine)", linear: "Steady", ease_out: "Fast start, slow end" },
  trans: { fade: "Fade", slide_left: "Slide left", slide_right: "Slide right", zoom_in: "Zoom in", zoom_out: "Zoom out" },
  tmode: { rotate: "Rotate types", lock: "One type only", cut: "Hard cut" },
  fit: { slow_then_freeze: "Slow down a little, then freeze", slow_then_loop: "Slow down a little, then loop", freeze: "Freeze last frame", loop: "Loop last part" },
  cmode: { word: "Word-by-word highlight", phrase: "Short phrases", single: "One word at a time" },
  pos: { bottom: "Bottom", middle: "Middle", top: "Top" },
};

// ----------------------------------------------------------------------------------------------- router
function route() {
  const parts = (location.hash || "#/workspace").slice(2).split("/").map(decodeURIComponent);
  const page = parts[0] || "workspace";
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.page === page));
  if (page === "workspace") return showWorkspace(parts[1], parseInt(parts[2] || "0", 10));
  if (page === "projects") return showProjects();
  if (page === "history") return showHistory();
  if (page === "presets") return showPresets();
  if (page === "settings") return showSettings();
  location.hash = "#/workspace";
}
function go(step) {
  const p = S.project;
  location.hash = p ? `#/workspace/${encodeURIComponent(p.folder)}/${step}` : "#/workspace";
}
function setTitle() {
  const inp = $("#title-input");
  inp.value = S.project ? S.project.name : "";
  inp.disabled = !S.project;
}

// ----------------------------------------------------------------------------------------------- workspace
async function showWorkspace(folder, step) {
  folder = folder || store.get("sf-last");
  if (folder && (!S.project || S.project.folder !== folder)) {
    try { S.project = await api("GET", `/api/projects/${encodeURIComponent(folder)}`); S.draft = null; S.draftInfo = null; }
    catch (e) { S.project = null; store.set("sf-last", ""); }
  }
  setTitle();
  const view = $("#view");
  if (!S.project) return renderWelcome(view);
  store.set("sf-last", S.project.folder);
  S.step = step || suggestedStep(S.project);
  if (!step) { history.replaceState(null, "", `#/workspace/${encodeURIComponent(S.project.folder)}/${S.step}`); }
  view.innerHTML = "";
  view.appendChild(renderStepper());
  const body = el(`<div></div>`);
  view.appendChild(body);
  ({ 1: step1, 2: step2, 3: step3, 4: step4, 5: step5 }[S.step] || step1)(body);
  fillIcons(view);
}

function suggestedStep(p) {
  if (!p.voice_files.length || !p.scenes.length || !p.synced) return 1;
  if (p.missing.length) return 3;
  return p.outputs.length ? 5 : 4;
}
function stepDone(n, p) {
  return { 1: p.voice_files.length && p.scenes.length, 2: p.synced, 3: p.scenes.length && !p.missing.length,
    4: p.synced && !p.flagged.length, 5: p.outputs.length }[n];
}
function renderStepper() {
  const p = S.project;
  const wrap = el(`<div class="stepper"></div>`);
  STEPS.forEach((s) => {
    const b = el(`<button class="step ${s.n === S.step ? "active" : ""} ${stepDone(s.n, p) ? "done" : ""}">
      <span class="ic">${stepDone(s.n, p) && s.n !== S.step ? icon("check") : icon(s.icon)}</span>
      <span><div class="k">Step ${s.n}</div><div class="n">${s.name}</div></span></button>`);
    b.onclick = () => go(s.n);
    wrap.appendChild(b);
  });
  return wrap;
}

function renderWelcome(view) {
  view.innerHTML = `
  <div class="grid2" style="margin-top:6px">
    <div class="card"><div class="card-h"><h2>${icon("video")} Welcome to SceneForge</h2>
      <p>Turn a voice-over, a scene-by-scene script and one image or clip per scene into a finished, perfectly synced video.</p></div>
      <div class="card-b">
        <div class="notice info">${icon("lock")}<div>Everything runs on this laptop. Your files are never uploaded.</div></div>
        <button class="big-btn" id="w-new">${icon("plus-circle")} Create a new project</button>
        <div class="under">or open one of your projects on the right</div>
      </div></div>
    <div class="panel"><div class="panel-h"><h3>Recent projects</h3><span class="spacer"></span><a class="btn sm" href="#/projects">See all</a></div>
      <div class="scene-list" id="w-recent"><div class="help">Loading ...</div></div></div>
  </div>`;
  $("#w-new").onclick = openNewProject;
  guard(async () => {
    const list = await api("GET", "/api/projects");
    const box = $("#w-recent");
    box.innerHTML = list.length ? "" : `<div class="help" style="padding:10px">No projects yet.</div>`;
    list.slice(0, 8).forEach((pr) => {
      const it = el(`<a class="scene-item" href="#/workspace/${encodeURIComponent(pr.folder)}" style="color:inherit">
        <div class="badge">${icon("video")}</div><div><b>${esc(pr.name)}</b><div class="help" style="margin:0">${pr.aspect} · ${esc(pr.preset)} · ${pr.scenes} scenes · ${fmtDur(pr.duration)}</div></div>
        <div class="tm">${pr.outputs.length ? '<span class="pill-s green">rendered</span>' : pr.synced ? '<span class="pill-s purple">synced</span>' : ""}</div></a>`);
      box.appendChild(it);
    });
  });
}

// ---- step 1: script & voice --------------------------------------------------------------------
function dropzone(id, title, sub, accept, multiple, onFiles, opts = {}) {
  const z = el(`<label class="drop" id="${id}">${icon("upload")}<div class="t">${title}</div><div class="s">${sub}</div>
    <input type="file" ${multiple ? "multiple" : ""} accept="${accept}" ${opts.dir ? "webkitdirectory directory" : ""}></label>`);
  const inp = $("input", z);
  inp.onchange = () => { if (inp.files.length) onFiles(Array.from(inp.files)); inp.value = ""; };
  z.addEventListener("dragover", (e) => { e.preventDefault(); z.classList.add("over"); });
  z.addEventListener("dragleave", () => z.classList.remove("over"));
  z.addEventListener("drop", (e) => { e.preventDefault(); z.classList.remove("over"); if (e.dataTransfer.files.length) onFiles(Array.from(e.dataTransfer.files)); });
  return z;
}

function step1(body) {
  const p = S.project;
  if (S.draft === null) { S.draft = p.script_text || ""; S.draftInfo = p.scenes.length ? { count: p.scenes.length, warnings: [], saved: true } : null; }
  const g = el(`<div class="grid2"></div>`);
  const card = el(`<div class="card">
    <div class="card-h"><h2>${icon("file")} Scene Sync</h2><p>Upload your voice-over and script, then sync your script to the exact timestamps.</p></div>
    <div class="card-b">
      <div class="label-up">Audio source</div>
      <div class="segment"><button class="on">${icon("upload")} Upload File</button><button id="seg-multi" title="Several files are joined in name order">${icon("layers")} Several Parts</button></div>
      <div class="field-title">${icon("audio")} Voice-Over Audio</div>
      <div id="voice-box"></div>
      <div class="field-title">${icon("file")} Script Document
        <span class="hintbox">Label scenes "Scene 1:", "Scene 2:" ... <a href="/api/sample-script">${icon("download")} Download sample script</a></span></div>
      <div id="script-box"></div>
      <div class="field-title">${icon("list")} Expected Scene Count</div>
      <input class="input" id="expected" type="number" min="1" max="400" placeholder="e.g. 5" value="${p.expected ?? ""}">
      <div class="help">So SceneForge can warn you if the script has a different number of scenes.</div>
      <details class="adv"><summary>Speech recognition options</summary>
        <div class="row">
          <div><label class="help" style="display:block;margin:0 0 6px">Speech model</label>
            <select class="input" id="model"><option value="small">small - fast (recommended)</option><option value="medium">medium - more accurate, ~3x slower</option></select></div>
          <div><label class="help" style="display:block;margin:0 0 6px">Voice-over language</label>
            <select class="input" id="lang">${[["en", "English"], ["auto", "Detect automatically"], ["fr", "French"], ["es", "Spanish"], ["de", "German"], ["pt", "Portuguese"], ["it", "Italian"], ["nl", "Dutch"], ["ar", "Arabic"], ["hi", "Hindi"]].map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></div>
        </div></details>
      <button class="big-btn" id="sync-btn">${icon("refresh")} Sync Scenes <span class="pill">runs on this laptop</span></button>
      <div class="under">Takes roughly 1 minute per 2-3 minutes of voice-over with the "small" model.</div>
    </div></div>`);
  g.appendChild(card);
  const right = el(`<div id="right-pane"></div>`);
  g.appendChild(right);
  body.appendChild(g);
  $("#seg-multi", card).onclick = () => toast("Pick all the parts at once in the voice-over box. They are joined in name order: part1, part2, part3 ...");
  $("#model", card).value = S.model;
  $("#lang", card).value = S.language;
  $("#model", card).onchange = (e) => { S.model = e.target.value; store.set("sf-model", S.model); };
  $("#lang", card).onchange = (e) => { S.language = e.target.value; store.set("sf-lang", S.language); };
  renderVoiceBox();
  renderScriptBox();
  $("#sync-btn", card).onclick = doSync;
  renderRightPane();
}

function renderVoiceBox() {
  const box = $("#voice-box");
  if (!box) return;
  const p = S.project;
  box.innerHTML = "";
  box.appendChild(dropzone("voice-drop", p.voice_files.length ? "Click or drop to replace the voice-over" : "Click or tap to upload audio",
    "MP3, WAV, M4A - pick several files to join them in order", ".mp3,.wav,.m4a,.aac,.flac,.ogg", true, uploadVoice));
  if (p.voice_files.length) {
    const list = el(`<div class="filelist"></div>`);
    p.voice_files.forEach((f, i) => list.appendChild(el(`<div class="fileitem">${icon("audio")}<span class="nm">${i + 1}. ${esc(f)}</span>
      ${i === 0 ? `<span class="meta">total ${fmtDur(p.audio_duration)} (${p.audio_duration.toFixed(2)} s)</span>` : ""}</div>`)));
    box.appendChild(list);
  }
}

async function uploadVoice(files) {
  const z = $("#voice-drop");
  if (z) $(".t", z).textContent = "Uploading and joining ...";
  await guard(async () => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    S.project = await api("POST", `/api/projects/${encodeURIComponent(S.project.folder)}/voice`, fd);
    toast(`Voice-over ready: ${fmtDur(S.project.audio_duration)}`, "ok");
  });
  renderVoiceBox();
}

function renderScriptBox() {
  const box = $("#script-box");
  if (!box) return;
  box.innerHTML = "";
  const info = S.draftInfo;
  box.appendChild(dropzone("script-drop", info ? "Click or drop to replace the script" : "Click or tap to upload script", ".docx, .txt, or .md", ".docx,.txt,.md", false, uploadScript));
  if (info) {
    const it = el(`<div class="filelist"><div class="fileitem">${icon("file")}<span class="nm">${esc(S.draftName || "Script")}${info.saved ? "" : " (not saved yet)"}</span>
      <span class="meta"><b>${info.count}</b> scenes found</span><button class="btn xs" id="edit-script">${icon("edit")} View / edit text</button></div></div>`);
    box.appendChild(it);
    (info.warnings || []).forEach((w) => box.appendChild(el(`<div class="notice warn" style="margin:8px 0 0">${icon("alert")}<div>${esc(w)}</div></div>`)));
  }
  if (!info) {
    const t = el(`<div class="help" style="text-align:center"><button class="linkish" type="button">or paste the script text instead</button></div>`);
    $("button", t).onclick = () => { ta.classList.toggle("hidden"); ta.focus(); };
    box.appendChild(t);
  }
  const ta = el(`<textarea class="input ${S.draft && !info ? "" : "hidden"}" id="script-text" rows="10" placeholder="...or paste your script here:&#10;Scene 1: First scene narration...&#10;Scene 2: Second scene narration..."></textarea>`);
  ta.value = S.draft || "";
  ta.style.marginTop = "10px";
  ta.oninput = () => { S.draft = ta.value; if (S.draftInfo) S.draftInfo.saved = false; };
  box.appendChild(ta);
  const btn = $("#edit-script", box);
  if (btn) btn.onclick = (e) => { e.preventDefault(); ta.classList.toggle("hidden"); };
}

async function uploadScript(files) {
  await guard(async () => {
    const fd = new FormData();
    fd.append("file", files[0], files[0].name);
    const r = await api("POST", "/api/script/read", fd);
    S.draft = r.text; S.draftName = files[0].name;
    S.draftInfo = { count: r.count, warnings: r.warnings, saved: false };
    const exp = $("#expected");
    const n = parseInt(exp.value, 10);
    if (n && n !== r.count) S.draftInfo.warnings = [`You expect ${n} scenes but this script has ${r.count}.`, ...r.warnings];
    toast(`Script read: ${r.count} scenes found.`);
  });
  renderScriptBox();
}

function confirmDialog(title, message, okText = "Continue anyway") {
  return new Promise((resolve) => {
    const m = modal(`<div class="modal"><div class="modal-h"><div class="mi" style="background:#f59e0b">${icon("alert")}</div>
      <div><h3>${esc(title)}</h3></div><button class="x" data-x>&times;</button></div>
      <div class="modal-b">${message}</div>
      <div class="modal-f"><button class="btn ghost" data-x>Go back</button><button class="btn primary" id="cf-ok">${esc(okText)}</button></div></div>`,
    () => resolve(false));
    $("#cf-ok", m).onclick = () => { m._onClose = null; closeModal(); resolve(true); };
  });
}

async function saveScript(confirmed = false) {
  const p = S.project;
  const text = ($("#script-text") || {}).value ?? S.draft ?? "";
  const exp = parseInt(($("#expected") || {}).value, 10) || null;
  if (!text.trim()) throw new Error("Upload or paste the script first.");
  const r = await api("POST", `/api/projects/${encodeURIComponent(p.folder)}/script`, { text, expected: exp, confirm: confirmed });
  if (!r.saved && r.needs_confirm) {
    const go = await confirmDialog("Scene count doesn't match",
      `<p>You expected <b>${exp}</b> scenes, but the script has <b>${r.count}</b>.</p>
       ${r.warnings.filter((w) => !w.startsWith("You expected")).length ? `<ul>${r.warnings.filter((w) => !w.startsWith("You expected")).map((w) => `<li>${esc(w)}</li>`).join("")}</ul>` : ""}
       <p class="help">Check the "Scene N:" labels in your script. Continue only if the script is right.</p>`);
    if (!go) return false;
    return saveScript(true);
  }
  if (r.project) S.project = r.project;
  S.draftInfo = { count: r.count, warnings: r.warnings.filter((w) => !w.startsWith("You expected")), saved: true };
  return true;
}

async function doSync() {
  const p = S.project;
  await guard(async () => {
    if (!p.voice_files.length) throw new Error("Upload the voice-over audio first.");
    if (!(await saveScript())) return;
    if (S.project.synced && S.project.scenes.some((s) => s.edited)) {
      if (!(await confirmDialog("Sync again?", "<p>Syncing again resets the scene starts you nudged by hand.</p>", "Sync again"))) return;
    }
    const job = await api("POST", `/api/projects/${encodeURIComponent(p.folder)}/sync`, { model: S.model, language: S.language });
    watchJob(job, async (j) => {
      S.project = await api("GET", `/api/projects/${encodeURIComponent(p.folder)}`);
      const fl = j.result.flagged.length;
      toast(fl ? `Synced - ${fl} scene(s) need checking.` : "All scenes synced confidently.", fl ? "" : "ok");
      if (S.step === 1) { renderScriptBox(); renderRightPane(); $("#view .stepper").replaceWith(renderStepper()); }
    });
  });
}

function jobBox(job) {
  return `<div class="panel"><div class="job">
    <div class="badge" style="margin:0 auto;width:52px;height:52px">${icon("refresh", "spin")}</div>
    <h3 style="margin:14px 0 14px">${{ sync: "Syncing scenes ...", render: "Rendering video ...", preview: "Making preview ..." }[job.kind] || "Working ..."}</h3>
    <div class="progress"><div style="width:${Math.round(job.progress * 100)}%"></div></div>
    <div class="msg">${esc(job.message)}</div></div></div>`;
}

function renderRightPane() {
  const pane = $("#right-pane");
  if (!pane) return;
  const p = S.project;
  if (S.job && S.job.kind === "sync" && S.job.status === "running") { pane.innerHTML = jobBox(S.job); return; }
  if (!p.synced) {
    pane.innerHTML = `<div class="empty">${icon("file")}<h3>Your mapped scenes will appear here</h3><p>Upload your audio and script, then click Sync Scenes.</p></div>`;
    return;
  }
  pane.innerHTML = "";
  pane.appendChild(mappedPanel(p));
  fillIcons(pane);
}

function mappedPanel(p) {
  const panel = el(`<div class="panel"><div class="panel-h"><h3>Mapped scenes</h3><span class="spacer"></span>
    <button class="btn sm primary" id="mp-next">Continue ${icon("arrow-r")}</button></div>
    <div class="stats">
      <div class="stat"><b>${p.scenes.length}</b><span>scenes</span></div>
      <div class="stat"><b>${fmtDur(p.audio_duration)}</b><span>voice-over</span></div>
      <div class="stat"><b>${Math.round((p.sync.match_rate || 0) * 100)}%</b><span>words matched</span></div>
      <div class="stat ${p.flagged.length ? "warn" : ""}"><b>${p.flagged.length}</b><span>need checking</span></div>
    </div>
    ${(p.sync.match_rate || 1) < 0.5 ? `<div class="notice warn" style="margin:12px 14px 0">${icon("alert")}<div>Less than half of the script matched the voice-over. Is this the right script, and is the language right?</div></div>` : ""}
    <div class="scene-list"></div></div>`);
  const list = $(".scene-list", panel);
  p.scenes.forEach((s) => {
    list.appendChild(el(`<div class="scene-item ${s.flag ? "flag" : ""}"><div class="badge">${s.number}</div>
      <div style="min-width:0"><div class="tx">${esc(s.text)}</div>${s.flag ? `<div class="flagtxt">⚠ ${esc(s.flag)}</div>` : ""}</div>
      <div class="tm">${fmtT(s.start)} → ${fmtT(s.end)}<br>${(s.duration || 0).toFixed(2)} s</div></div>`));
  });
  $("#mp-next", panel).onclick = () => go(p.flagged.length ? 2 : 3);
  return panel;
}

// ---- jobs ---------------------------------------------------------------------------------------
function watchJob(job, onDone) {
  S.job = job;
  const tick = async () => {
    let j;
    try { j = await api("GET", `/api/jobs/${job.id}`); } catch (e) { setTimeout(tick, 1500); return; }
    S.job = j;
    updateJobViews(j);
    if (j.status === "running") { setTimeout(tick, 700); return; }
    if (j.status === "done") { if (onDone) await onDone(j); }
    else if (j.status === "error") toast(j.error, "err");
    else if (j.status === "stopped") toast(j.message);
    updateJobViews(j);
  };
  updateJobViews(job);
  setTimeout(tick, 500);
}
function updateJobViews(j) {
  if (j.kind === "sync" && $("#right-pane")) {
    if (j.status === "running") $("#right-pane").innerHTML = jobBox(j); else renderRightPane();
  }
  const rp = $("#render-progress");
  if (j.kind === "render" && rp) renderExportStatus();
  const pv = $("#preview-progress");
  if (j.kind === "preview" && pv) {
    $(".progress > div", pv).style.width = Math.round(j.progress * 100) + "%";
    $(".msg", pv).textContent = j.message;
  }
}

// ---- step 2: scene sync table -----------------------------------------------------------------
function step2(body) {
  const p = S.project;
  if (!p.synced) {
    body.appendChild(el(`<div class="empty">${icon("wave")}<h3>Not synced yet</h3><p>Go to step 1, upload the voice-over and script, and press Sync Scenes.</p>
      <button class="btn primary" style="margin-top:14px" onclick="go(1)">Go to step 1</button></div>`));
    return;
  }
  const card = el(`<div class="panel"><div class="panel-h"><h3>${icon("wave")} Scene timings</h3>
      <span class="help" style="margin:0 0 0 8px">Measured from your voice-over. Each scene starts on its first spoken word.</span><span class="spacer"></span>
      <button class="btn sm" id="resync">${icon("refresh")} Sync again</button>
      <button class="btn sm primary" id="s2-next">Continue to Media ${icon("arrow-r")}</button></div>
    <div id="s2-notice" style="padding:12px 16px 0"></div>
    <div class="table-wrap"><table class="t"><thead><tr><th>Scene</th><th>Start</th><th>End</th><th>Length</th><th>Narration</th><th>Match</th><th>Status</th><th>Adjust start</th></tr></thead><tbody></tbody></table></div></div>`);
  body.appendChild(card);
  $("#resync", card).onclick = () => go(1);
  $("#s2-next", card).onclick = () => go(3);
  fillSyncTable(card);
}

function nudgeControls(s) {
  if (s.number === S.project.scenes[0].number) return `<span class="help">starts at 0:00</span>`;
  return `<div class="nudge" data-n="${s.number}">
    <button class="btn xs" data-d="-0.5">−0.5</button><button class="btn xs" data-d="-0.1">−0.1</button>
    <input type="number" step="0.01" value="${(s.start ?? 0).toFixed(2)}" title="Start time in seconds (type and press Enter)">
    <button class="btn xs" data-d="0.1">+0.1</button><button class="btn xs" data-d="0.5">+0.5</button>
    ${s.edited ? `<button class="btn xs" data-reset title="Back to the detected time">${icon("refresh")}</button>` : ""}</div>`;
}
function wireNudges(root, after) {
  $$(".nudge", root).forEach((nd) => {
    const n = parseInt(nd.dataset.n, 10);
    const send = (body) => guard(async () => {
      S.project = await api("POST", `/api/projects/${encodeURIComponent(S.project.folder)}/scenes/${n}/start`, body);
      after();
    });
    $$("button[data-d]", nd).forEach((b) => (b.onclick = () => send({ delta: parseFloat(b.dataset.d) })));
    const r = $("button[data-reset]", nd);
    if (r) r.onclick = () => send({ reset: true });
    const inp = $("input", nd);
    inp.onchange = () => send({ absolute: parseFloat(inp.value) });
  });
}
function statusCell(s) {
  if (s.flag) return `<span class="flagtxt">⚠ ${esc(s.flag)}</span>`;
  if (s.edited) return `<span class="pill-s purple">moved by you</span>`;
  return `<span class="pill-s green">${icon("check")} found</span>`;
}
function fillSyncTable(card) {
  const p = S.project;
  $("#s2-notice", card).innerHTML = p.flagged.length
    ? `<div class="notice warn">${icon("alert")}<div><b>${p.flagged.length} scene(s) need checking:</b> ${p.flagged.slice(0, 40).join(", ")}. Their opening words could not be confidently found, so the start was estimated. Preview them in step 4 and nudge them if needed.</div></div>`
    : `<div class="notice ok">${icon("check")}<div>All ${p.scenes.length} scenes were found confidently in the voice-over.</div></div>`;
  const tb = $("tbody", card);
  tb.innerHTML = p.scenes.map((s) => `<tr class="${s.flag ? "flag" : ""}"><td><div class="badge">${s.number}</div></td>
    <td class="num">${fmtT(s.start)}</td><td class="num">${fmtT(s.end)}</td><td class="num">${(s.duration || 0).toFixed(2)} s</td>
    <td class="words">${esc(s.text.split(/\s+/).slice(0, 14).join(" "))}${s.text.split(/\s+/).length > 14 ? " ..." : ""}</td>
    <td class="num">${s.confidence !== null && s.confidence !== undefined ? Math.round(s.confidence * 100) + "%" : "–"}</td>
    <td>${statusCell(s)}</td><td>${nudgeControls(s)}</td></tr>`).join("");
  fillIcons(card);
  wireNudges(card, () => fillSyncTable(card));
}

// ---- step 3: media ------------------------------------------------------------------------------
function thumbUrl(s) { return `/api/projects/${encodeURIComponent(S.project.folder)}/thumb/${s.number}?v=${s.media_v}`; }

function step3(body) {
  const p = S.project;
  if (!p.scenes.length) {
    body.appendChild(el(`<div class="empty">${icon("image")}<h3>Add the script first</h3><p>SceneForge needs to know your scenes before matching media files.</p>
      <button class="btn primary" style="margin-top:14px" onclick="go(1)">Go to step 1</button></div>`));
    return;
  }
  const portrait = p.aspect === "9:16";
  const card = el(`<div class="card"><div class="card-h"><h2>${icon("image")} Scene Media</h2>
    <p>One image or video clip per scene. The <b>number in the file name</b> picks the scene: "Scene 1.png", "scene_1.mp4" and "1.jpg" all go to scene 1.</p></div>
    <div class="card-b">
      <div class="row" style="align-items:stretch">
        <div id="m-drop"></div>
        <div style="flex:0 0 300px;display:flex;flex-direction:column;gap:10px">
          <div id="m-folder"></div>
          <div><input class="input" id="m-path" placeholder="...or paste a folder path, e.g. C:\\Videos\\media">
          <button class="btn sm" id="m-path-btn" style="margin-top:8px;width:100%">${icon("folder")} Import from this folder</button></div>
        </div>
      </div>
      <div id="m-notes"></div>
      <div class="extras"><div id="x-music"></div><div id="x-sfx"></div></div>
    </div></div>`);
  body.appendChild(card);
  $("#m-drop", card).appendChild(dropzone("media-drop", "Click or drop your images and clips", "PNG, JPG, WEBP, MP4, MOV - select many at once", ".png,.jpg,.jpeg,.webp,.mp4,.mov,.m4v", true, uploadMedia));
  const fz = dropzone("folder-drop", "Pick a whole folder", "all files inside are matched", "", true, uploadMedia, { dir: true });
  fz.style.padding = "14px";
  $("#m-folder", card).appendChild(fz);
  $("#m-path-btn", card).onclick = () => guard(async () => {
    const path = $("#m-path").value.trim();
    if (!path) throw new Error("Paste a folder path first.");
    const r = await api("POST", `/api/projects/${encodeURIComponent(p.folder)}/media/folder`, { path });
    afterMedia(r);
  });
  const grid = el(`<div class="panel" style="margin-top:20px"><div class="panel-h"><h3>Scenes</h3><span id="m-count" class="help" style="margin:0"></span><span class="spacer"></span>
    <button class="btn sm primary" id="s3-next">Continue to Review ${icon("arrow-r")}</button></div>
    <div class="media-grid ${portrait ? "portrait" : ""}" id="m-grid"></div></div>`);
  body.appendChild(grid);
  $("#s3-next", grid).onclick = () => go(4);
  renderMediaGrid();
  renderExtras();
}

function renderMediaGrid() {
  const p = S.project;
  const g = $("#m-grid");
  if (!g) return;
  const portrait = p.aspect === "9:16";
  $("#m-count").innerHTML = p.missing.length ? `<span class="pill-s red">${p.missing.length} missing</span> &nbsp;${p.scenes.length - p.missing.length} of ${p.scenes.length} scenes have media`
    : `<span class="pill-s green">${icon("check")} all ${p.scenes.length} scenes have media</span>`;
  g.innerHTML = "";
  p.scenes.forEach((s) => {
    const c = el(`<div class="mcard ${portrait ? "portrait" : ""} ${s.media ? "" : "miss"}" title="Click to choose a different file for scene ${s.number}">
      <div class="img" style="${s.media ? `background-image:url('${thumbUrl(s)}')` : ""}">${s.media ? "" : "MISSING"}</div>
      ${s.media ? `<span class="pill-s ${s.media_kind === "video" ? "purple" : ""} kind">${s.media_kind === "video" ? "clip" : "image"}</span>` : ""}
      <div class="cap"><b>Scene ${s.number}</b><span>${esc(s.media || "click to add")}</span></div>
      <input type="file" class="hidden" accept=".png,.jpg,.jpeg,.webp,.mp4,.mov,.m4v"></div>`);
    const inp = $("input", c);
    c.onclick = (e) => { if (e.target !== inp) inp.click(); };
    inp.onchange = () => { if (inp.files.length) swapMedia(s.number, inp.files[0], renderMediaGrid); };
    g.appendChild(c);
  });
  fillIcons(g);
}

async function swapMedia(number, file, after) {
  await guard(async () => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    S.project = await api("POST", `/api/projects/${encodeURIComponent(S.project.folder)}/scenes/${number}/media`, fd);
    toast(`Scene ${number} now uses ${file.name}`, "ok");
    after();
  });
}

async function uploadMedia(files) {
  const ok = files.filter((f) => /\.(png|jpe?g|webp|bmp|mp4|mov|m4v|mkv|webm)$/i.test(f.name));
  if (!ok.length) return toast("No images or clips in that selection.", "err");
  const z = $("#media-drop");
  if (z) $(".t", z).textContent = `Copying ${ok.length} file(s) ...`;
  await guard(async () => {
    // send in batches so very large folders don't time out
    let last = null;
    for (let i = 0; i < ok.length; i += 20) {
      const fd = new FormData();
      ok.slice(i, i + 20).forEach((f) => fd.append("files", f, f.name));
      const r = await api("POST", `/api/projects/${encodeURIComponent(S.project.folder)}/media`, fd);
      if (last) { r.unmatched = last.unmatched.concat(r.unmatched); r.notes = last.notes.concat(r.notes); r.added += last.added; }
      last = r;
      if (z) $(".t", z).textContent = `Copying ... ${Math.min(i + 20, ok.length)} / ${ok.length}`;
    }
    afterMedia(last);
  });
  if (z) $(".t", z).textContent = "Click or drop your images and clips";
}

function afterMedia(r) {
  S.project = r.project;
  const notes = $("#m-notes");
  let html = "";
  if (r.unmatched.length) html += `<div class="notice warn" style="margin-top:14px">${icon("alert")}<div>No scene number in these file names, so they were not used: ${r.unmatched.slice(0, 20).map(esc).join(", ")}</div></div>`;
  if (r.notes.length) html += `<div class="notice info" style="margin-top:14px">${icon("info")}<div>${r.notes.map(esc).join("<br>")}</div></div>`;
  if (notes) notes.innerHTML = html;
  toast(`Added ${r.added} file(s).`, "ok");
  renderMediaGrid();
  $("#view .stepper").replaceWith(renderStepper());
}

function renderExtras() {
  const p = S.project;
  const one = (kind, title, sub) => {
    const box = $(`#x-${kind}`);
    box.innerHTML = `<div class="field-title" style="margin-top:0">${icon(kind === "music" ? "audio" : "sparkles")} ${title}</div>`;
    const cur = p[kind];
    if (cur) {
      const it = el(`<div class="fileitem">${icon("audio")}<span class="nm">${esc(cur)}</span><button class="btn xs danger">${icon("trash")} Remove</button></div>`);
      $("button", it).onclick = () => guard(async () => { S.project = await api("DELETE", `/api/projects/${encodeURIComponent(p.folder)}/audio/${kind}`); renderExtras(); });
      box.appendChild(it);
    } else {
      const z = dropzone(`${kind}-drop`, `Add ${title.toLowerCase()}`, sub, ".mp3,.wav,.m4a,.aac,.flac,.ogg", false, (files) => guard(async () => {
        const fd = new FormData();
        fd.append("file", files[0], files[0].name);
        S.project = await api("POST", `/api/projects/${encodeURIComponent(p.folder)}/audio/${kind}`, fd);
        renderExtras();
      }));
      z.style.padding = "16px";
      box.appendChild(z);
    }
  };
  one("music", "Background music", "Optional. Looped to the video length and lowered while you speak.");
  one("sfx", "Transition sound", "Optional, e.g. a whoosh played on every transition.");
}

// ---- step 4: review -----------------------------------------------------------------------------
function step4(body) {
  const p = S.project;
  if (!p.synced) {
    body.appendChild(el(`<div class="empty">${icon("play")}<h3>Nothing to review yet</h3><p>Sync the scenes in step 1 first.</p>
      <button class="btn primary" style="margin-top:14px" onclick="go(1)">Go to step 1</button></div>`));
    return;
  }
  const wrap = el(`<div style="display:flex;flex-direction:column;gap:20px"></div>`);
  const panel = el(`<div class="panel"><div class="panel-h"><h3>${icon("play")} Review scenes</h3><span class="spacer"></span>
    <button class="btn sm primary" id="s4-next">Continue to Export ${icon("arrow-r")}</button></div>
    <div id="s4-notice" style="padding:12px 16px 0"></div>
    <div class="table-wrap"><table class="t"><thead><tr><th>Scene</th><th>Media</th><th>Start</th><th>End</th><th>Length</th><th>First words</th><th>Status</th><th>Adjust start</th><th>Preview</th></tr></thead><tbody></tbody></table></div></div>`);
  wrap.appendChild(panel);
  const side = el(`<div class="card"><div class="card-h" style="padding:20px 24px 14px;display:flex;align-items:center;gap:12px"><div><h2 style="font-size:17px">${icon("settings")} Project style</h2>
    <p style="font-size:13px">Started from the <b>${esc(p.preset)}</b> preset. Changes here only affect this project.</p></div><span style="flex:1"></span>
    <button class="btn" id="pf-reset">Reset to preset</button><button class="btn primary" id="pf-save">${icon("save")} Save style</button></div>
    <div class="card-b" style="padding:16px 20px"><div id="proj-form" class="cols"></div></div></div>`);
  wrap.appendChild(side);
  body.appendChild(wrap);
  $("#s4-next", panel).onclick = () => go(5);
  fillReview(panel);
  const form = settingsForm(p.settings);
  $("#proj-form", side).appendChild(form);
  $("#pf-save", side).onclick = () => saveProjectStyle();
  $("#pf-reset", side).onclick = () => guard(async () => {
    S.project = await api("PATCH", `/api/projects/${encodeURIComponent(p.folder)}`, { reset_settings: true });
    $("#proj-form").innerHTML = "";
    $("#proj-form").appendChild(settingsForm(S.project.settings));
    toast("Style reset to the preset.", "ok");
  });
}

async function saveProjectStyle(quiet) {
  const f = $("#proj-form .sf");
  if (!f) return;
  const settings = readSettingsForm(f, S.project.settings);
  S.project = await api("PATCH", `/api/projects/${encodeURIComponent(S.project.folder)}`, { settings });
  if (!quiet) toast("Project style saved.", "ok");
}

function fillReview(panel) {
  const p = S.project;
  const portrait = p.aspect === "9:16";
  const n = $("#s4-notice", panel);
  const parts = [];
  if (p.flagged.length) parts.push(`<div class="notice warn">${icon("alert")}<div><b>Check these scenes:</b> ${p.flagged.slice(0, 40).join(", ")}. Press ▶ to preview, then nudge the start if needed.</div></div>`);
  if (p.missing.length) parts.push(`<div class="notice err">${icon("image")}<div><b>Missing media:</b> scenes ${p.missing.slice(0, 40).join(", ")}. They will show a dark "media missing" card.</div></div>`);
  n.innerHTML = parts.join("");
  $("tbody", panel).innerHTML = p.scenes.map((s) => `<tr class="${s.flag ? "flag" : ""}">
    <td><div class="badge">${s.number}</div></td>
    <td>${s.media ? `<img class="thumb ${portrait ? "portrait" : ""}" loading="lazy" src="${thumbUrl(s)}" alt="">` : `<div class="thumb missing ${portrait ? "portrait" : ""}">missing</div>`}
      <label class="linkish" style="font-size:12px;cursor:pointer">${s.media ? "swap" : "add"}<input type="file" class="hidden" data-swap="${s.number}" accept=".png,.jpg,.jpeg,.webp,.mp4,.mov,.m4v"></label></td>
    <td class="num">${fmtT(s.start)}</td>
    <td class="num">${fmtT(s.end)}</td><td class="num">${(s.duration || 0).toFixed(2)} s</td>
    <td class="words">${esc(s.text.split(/\s+/).slice(0, 16).join(" "))} ...</td>
    <td>${statusCell(s)}</td><td>${nudgeControls(s)}</td>
    <td><button class="btn sm" data-prev="${s.number}" title="Preview this scene">${icon("play-s")}</button></td></tr>`).join("");
  fillIcons(panel);
  wireNudges(panel, () => fillReview(panel));
  $$("input[data-swap]", panel).forEach((inp) => (inp.onchange = () => {
    if (inp.files.length) swapMedia(parseInt(inp.dataset.swap, 10), inp.files[0], () => fillReview(panel));
  }));
  $$("button[data-prev]", panel).forEach((b) => (b.onclick = () => previewScene(parseInt(b.dataset.prev, 10))));
}

async function previewScene(number) {
  await guard(async () => {
    if ($("#proj-form .sf")) await saveProjectStyle(true);
    const job = await api("POST", `/api/projects/${encodeURIComponent(S.project.folder)}/preview/${number}`);
    const m = modal(`<div class="modal video"><div class="modal-h"><div class="mi">${icon("play")}</div>
      <div><h3>Scene ${number} preview</h3><p>Small and quick, with its transitions in and out.</p></div><button class="x" data-x>&times;</button></div>
      <div class="modal-b" id="pv-body"><div id="preview-progress" class="job"><div class="progress"><div style="width:0%"></div></div><div class="msg">Starting ...</div></div></div></div>`);
    watchJob(job, (j) => {
      const b = $("#pv-body", m);
      if (b) b.innerHTML = `<video class="video-out" controls autoplay src="/api/projects/${encodeURIComponent(S.project.folder)}/file/${j.result.file}?v=${j.result.v}"></video>`;
    });
  });
}

// ---- step 5: export -----------------------------------------------------------------------------
function step5(body) {
  const p = S.project;
  const r = p.render || {};
  const box = el(`<div class="render-box">
    <div class="card"><div class="card-h"><h2>${icon("export")} Export</h2><p>Render the finished MP4 (H.264 video, AAC audio, 30 fps).</p></div>
      <div class="card-b">
        <div class="label-up">Resolution</div>
        <div class="choices" id="res">
          <button class="choice" data-v="1080p"><span class="ar">HD</span><span><b>1080p</b><small>${p.aspect === "9:16" ? "1080 × 1920" : "1920 × 1080"} · recommended</small></span></button>
          <button class="choice" data-v="4K"><span class="ar">4K</span><span><b>4K</b><small>About 4x slower on a laptop</small></span></button>
        </div>
        <div class="label-up" style="margin-top:20px">Quality</div>
        <div class="choices three" id="qual">
          <button class="tpl" data-v="fast"><b>Fast</b><small>Quick draft</small></button>
          <button class="tpl" data-v="standard"><b>Standard</b><small>Great for YouTube</small></button>
          <button class="tpl" data-v="high"><b>High</b><small>Slower, smaller file</small></button>
        </div>
        <div id="ready" style="margin-top:20px"></div>
        <div id="render-progress"></div>
      </div></div>
    <div class="panel"><div class="panel-h"><h3>${icon("film")} Finished video</h3><span class="spacer"></span>
      <button class="btn sm" id="open-out">${icon("open")} Open output folder</button></div>
      <div style="padding:16px" id="out-box"></div></div></div>`);
  body.appendChild(box);
  let res = r.resolution || "1080p", qual = r.quality || "standard";
  const sel = () => {
    $$("#res .choice", box).forEach((b) => b.classList.toggle("on", b.dataset.v === res));
    $$("#qual .tpl", box).forEach((b) => b.classList.toggle("on", b.dataset.v === qual));
  };
  $$("#res .choice", box).forEach((b) => (b.onclick = () => { res = b.dataset.v; sel(); if (res === "4K") toast("4K takes about 4 times longer to render on your laptop."); }));
  $$("#qual .tpl", box).forEach((b) => (b.onclick = () => { qual = b.dataset.v; sel(); }));
  sel();
  S.renderChoice = () => ({ resolution: res, quality: qual });
  $("#open-out", box).onclick = () => guard(() => api("POST", `/api/projects/${encodeURIComponent(p.folder)}/open-output`));
  const ready = [];
  if (!p.synced) ready.push(`<div class="notice err">${icon("alert")}<div>Sync the scenes first (step 1).</div></div>`);
  if (p.missing.length) ready.push(`<div class="notice warn">${icon("image")}<div>Scenes without media (${p.missing.slice(0, 30).join(", ")}) will show a dark "media missing" card.</div></div>`);
  if (p.flagged.length) ready.push(`<div class="notice warn">${icon("alert")}<div>Flagged scenes to check: ${p.flagged.slice(0, 30).join(", ")} (step 4).</div></div>`);
  if (!ready.length) ready.push(`<div class="notice ok">${icon("check")}<div>Ready to render ${p.scenes.length} scenes, ${fmtDur(p.audio_duration)}.</div></div>`);
  $("#ready", box).innerHTML = ready.join("");
  renderExportStatus();
  renderOutputs();
}

function renderExportStatus() {
  const box = $("#render-progress");
  if (!box) return;
  const j = S.job && S.job.kind === "render" && S.job.project === S.project.folder ? S.job : null;
  if (j && j.status === "running") {
    box.innerHTML = `<div class="progress" style="margin-top:6px"><div style="width:${Math.round(j.progress * 100)}%"></div></div>
      <div class="row" style="margin-top:10px"><div class="help" style="margin:0">${Math.round(j.progress * 100)}% · ${esc(j.message)}</div>
      <button class="btn sm danger" style="flex:0 0 auto" id="stop-btn">${icon("stop")} Stop</button></div>`;
    $("#stop-btn").onclick = () => guard(async () => { await api("POST", "/api/render/stop"); toast("Stopping ... Press Render again later to continue where it stopped."); });
    return;
  }
  box.innerHTML = `<button class="big-btn" id="render-btn">${icon("film")} Render Video</button>
    <div class="under">Rendering continues if you close this browser tab. Stopped renders resume where they left off.</div>`;
  $("#render-btn").onclick = startRender;
  if (j && j.status === "done") renderOutputs();
}

async function startRender() {
  await guard(async () => {
    const p = S.project;
    const job = await api("POST", `/api/projects/${encodeURIComponent(p.folder)}/render`, S.renderChoice());
    watchJob(job, async (j) => {
      S.project = await api("GET", `/api/projects/${encodeURIComponent(p.folder)}`);
      toast(`Video finished in ${fmtDur(j.result.seconds)}!`, "ok");
      renderOutputs();
      const st = $("#view .stepper");
      if (st) st.replaceWith(renderStepper());
    });
  });
}

function renderOutputs() {
  const box = $("#out-box");
  if (!box) return;
  const p = S.project;
  if (!p.outputs.length) {
    box.innerHTML = `<div class="empty" style="min-height:300px">${icon("film")}<h3>No video yet</h3><p>Press Render Video. Your MP4 is saved in the project's output folder.</p></div>`;
    return;
  }
  const o = p.outputs[0];
  box.innerHTML = `<video class="video-out" controls src="/api/projects/${encodeURIComponent(p.folder)}/file/${o.path}?v=${Math.round(o.mtime)}"></video>
    <div class="kv" style="margin-top:12px"><span>File</span><b>${esc(o.name)}</b><span>Size</span><b>${fmtSize(o.size)}</b><span>Saved</span><b>${fmtDate(o.mtime)}</b>
    <span>Folder</span><code style="font-size:12px;word-break:break-all">${esc(p.path)}</code></div>
    <div class="row" style="margin-top:14px"><button class="btn sm" id="clean">${icon("trash")} Delete temporary render files</button></div>`;
  $("#clean").onclick = () => guard(async () => { await api("POST", `/api/projects/${encodeURIComponent(p.folder)}/clean`); toast("Temporary files deleted.", "ok"); });
  fillIcons(box);
}

// ----------------------------------------------------------------------------------------------- settings form
function schema() {
  const fonts = (S.meta && S.meta.fonts) || ["Arial Bold"];
  return [
    { sec: "captions", title: "Captions", icon: "type", open: true, fields: [
      { k: "enabled", t: "toggle", l: "Show captions" },
      { k: "mode", t: "one", l: "Style", opts: LABELS.cmode },
      { k: "font", t: "select", l: "Font", opts: Object.fromEntries(fonts.map((f) => [f, f])) },
      { k: "size", t: "range", l: "Size (px at 1080p)", min: 20, max: 160, step: 1 },
      { k: "color", t: "color", l: "Text colour" },
      { k: "highlight_color", t: "color", l: "Highlight colour" },
      { k: "outline_color", t: "color", l: "Outline colour" },
      { k: "outline", t: "range", l: "Outline thickness", min: 0, max: 15, step: 1 },
      { k: "position", t: "one", l: "Position", opts: LABELS.pos },
      { k: "max_words", t: "range", l: "Most words per caption", min: 2, max: 8, step: 1 },
      { k: "shadow", t: "toggle", l: "Soft shadow" },
      { k: "uppercase", t: "toggle", l: "CAPITAL LETTERS" },
      { k: "pop", t: "toggle", l: "Pop animation" },
    ] },
    { sec: "motion", title: "Image motion", icon: "move", fields: [
      { k: "zoom_min", t: "range", l: "Smallest zoom", min: 1, max: 1.5, step: 0.01 },
      { k: "zoom_max", t: "range", l: "Largest zoom", min: 1, max: 1.5, step: 0.01 },
      { k: "pan_min", t: "range", l: "Shortest pan (× width)", min: 0, max: 0.3, step: 0.01 },
      { k: "pan_max", t: "range", l: "Longest pan (× width)", min: 0, max: 0.3, step: 0.01 },
      { k: "types", t: "many", l: "Movements (never the same twice in a row)", opts: LABELS.motion, wide: 1 },
      { k: "easing", t: "many", l: "Speed curves", opts: LABELS.easing, wide: 1 },
    ] },
    { sec: "transitions", title: "Transitions", icon: "layers", fields: [
      { k: "mode", t: "one", l: "Style", opts: LABELS.tmode, wide: 1 },
      { k: "types", t: "many", l: "Types to rotate (no type twice in a row)", opts: LABELS.trans, wide: 1 },
      { k: "lock_type", t: "select", l: "The one type", opts: LABELS.trans },
      { k: "duration", t: "range", l: "Length (seconds)", min: 0.1, max: 2, step: 0.05 },
    ] },
    { sec: "clips", title: "Video clips", icon: "clip", fields: [
      { k: "fit_mode", t: "select", l: "When a clip is shorter than its scene", opts: LABELS.fit, wide: 1 },
      { k: "max_slowdown", t: "range", l: "Maximum slow-down", min: 0, max: 0.5, step: 0.01 },
      { k: "clip_volume", t: "range", l: "Clip audio volume", min: 0, max: 1, step: 0.01 },
      { k: "keep_audio", t: "toggle", l: "Keep clip audio (sound effects under the voice)", wide: 1 },
    ] },
    { sec: "audio", title: "Audio & sync", icon: "audio", fields: [
      { k: "music_volume", t: "range", l: "Music volume", min: 0, max: 1, step: 0.01, sec: "audio" },
      { k: "sfx_volume", t: "range", l: "Transition sound volume", min: 0, max: 1, step: 0.01, sec: "audio" },
      { k: "duck", t: "toggle", l: "Lower music while the voice speaks", sec: "audio", wide: 1 },
      { k: "lead_in", t: "range", l: "Cut this long before each scene's first word (s)", min: 0, max: 0.5, step: 0.01, sec: "sync", wide: 1 },
    ] },
  ];
}

function settingsForm(st) {
  const f = el(`<div class="sf"></div>`);
  schema().forEach((sec) => {
    const d = el(`<details class="sf-sec" ${sec.open ? "open" : ""}><summary>${icon(sec.icon)} ${sec.title}</summary><div class="sf-body"></div></details>`);
    const b = $(".sf-body", d);
    sec.fields.forEach((fd) => {
      const s = fd.sec || sec.sec;
      const v = (st[s] || {})[fd.k];
      const w = el(`<div class="sf-f ${fd.wide ? "wide" : ""}" data-s="${s}" data-k="${fd.k}" data-t="${fd.t}"></div>`);
      if (fd.t !== "toggle") w.appendChild(el(`<label class="l">${esc(fd.l)}</label>`));
      if (fd.t === "range") {
        const r = el(`<div class="rng"><input type="range" min="${fd.min}" max="${fd.max}" step="${fd.step}" value="${v}"><output>${v}</output></div>`);
        const inp = $("input", r);
        inp.oninput = () => { $("output", r).textContent = inp.value; };
        w.appendChild(r);
      } else if (fd.t === "toggle") {
        w.appendChild(el(`<label class="toggle"><input type="checkbox" ${v ? "checked" : ""}><span class="sw"></span>${esc(fd.l)}</label>`));
      } else if (fd.t === "one" || fd.t === "many") {
        const c = el(`<div class="chips"></div>`);
        Object.entries(fd.opts).forEach(([val, lab]) => {
          const on = fd.t === "many" ? (v || []).includes(val) : v === val;
          const chip = el(`<button type="button" class="chip ${on ? "on" : ""}" data-v="${val}">${esc(lab)}</button>`);
          chip.onclick = () => {
            if (fd.t === "one") $$(".chip", c).forEach((x) => x.classList.toggle("on", x === chip));
            else chip.classList.toggle("on");
          };
          c.appendChild(chip);
        });
        w.appendChild(c);
      } else if (fd.t === "select") {
        const s2 = el(`<select class="input" style="height:38px">${Object.entries(fd.opts).map(([val, lab]) => `<option value="${esc(val)}">${esc(lab)}</option>`).join("")}</select>`);
        if (v && !(v in fd.opts)) s2.appendChild(el(`<option value="${esc(v)}">${esc(v)}</option>`));
        s2.value = v;
        w.appendChild(s2);
      } else if (fd.t === "color") {
        const c = el(`<div class="color"><input type="color" value="${esc(v || "#ffffff")}"><input type="text" value="${esc(v || "#FFFFFF")}"></div>`);
        const [pick, txt] = $$("input", c);
        pick.oninput = () => { txt.value = pick.value.toUpperCase(); };
        txt.onchange = () => { if (/^#[0-9a-f]{6}$/i.test(txt.value)) pick.value = txt.value; };
        w.appendChild(c);
      }
      b.appendChild(w);
    });
    f.appendChild(d);
  });
  return f;
}

function readSettingsForm(f, base) {
  const st = JSON.parse(JSON.stringify(base));
  $$(".sf-f", f).forEach((w) => {
    const s = w.dataset.s, k = w.dataset.k, t = w.dataset.t;
    st[s] = st[s] || {};
    let v;
    if (t === "range") v = parseFloat($("input", w).value);
    else if (t === "toggle") v = $("input", w).checked;
    else if (t === "one") v = ($(".chip.on", w) || {}).dataset?.v;
    else if (t === "many") v = $$(".chip.on", w).map((c) => c.dataset.v);
    else if (t === "select") v = $("select", w).value;
    else if (t === "color") v = $("input[type=text]", w).value.toUpperCase();
    if (["size", "outline", "max_words"].includes(k)) v = Math.round(v);
    st[s][k] = v;
  });
  const m = st.motion;
  if (m.zoom_min > m.zoom_max) [m.zoom_min, m.zoom_max] = [m.zoom_max, m.zoom_min];
  if (m.pan_min > m.pan_max) [m.pan_min, m.pan_max] = [m.pan_max, m.pan_min];
  if (!m.types.length) throw new Error("Tick at least one image movement.");
  if (!m.easing.length) m.easing = ["ease_in_out"];
  if (st.transitions.mode === "rotate" && !st.transitions.types.length) throw new Error("Tick at least one transition type, or choose Hard cut.");
  return st;
}

// ----------------------------------------------------------------------------------------------- modals
function modal(html, onClose) {
  closeModal();
  const ov = el(`<div class="overlay"></div>`);
  ov.innerHTML = html;
  ov._onClose = onClose;
  ov.addEventListener("mousedown", (e) => { if (e.target === ov) closeModal(); });
  $$("[data-x]", ov).forEach((b) => (b.onclick = closeModal));
  $("#modal-root").appendChild(ov);
  fillIcons(ov);
  return ov;
}
function closeModal() {
  const ov = $("#modal-root .overlay");
  if (!ov) return;
  ov.remove();
  if (ov._onClose) ov._onClose();
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

function presetBlurb(name, st) {
  const t = st.transitions, c = st.captions;
  const trans = t.mode === "cut" ? "hard cuts" : t.mode === "lock" ? `${LABELS.trans[t.lock_type]} transitions` : t.types.map((x) => LABELS.trans[x].toLowerCase()).join(", ") + " transitions";
  const caps = c.enabled ? `${LABELS.cmode[c.mode].toLowerCase()} captions` : "no captions";
  return `${trans}, ${caps}${st.clips.keep_audio ? ", keeps clip audio" : ""}.`;
}

async function openNewProject() {
  if (!S.presets) S.presets = await api("GET", "/api/presets");
  const names = Object.keys(S.presets);
  let aspect = "16:9", preset = names[0];
  const m = modal(`<div class="modal"><div class="modal-h"><div class="mi">${icon("video")}</div>
    <div><h3>Create New Project</h3><p>Configure your title and video canvas</p></div><button class="x" data-x>&times;</button></div>
    <div class="modal-b">
      <div class="label-up">Project name <span class="req">*</span></div>
      <input class="input" id="np-name" maxlength="80" placeholder="e.g. Why Ancient Temples Have No Windows">
      <div class="label-up" style="margin-top:20px">Canvas aspect ratio</div>
      <div class="choices" id="np-ar">
        <button class="choice on" data-v="16:9"><span class="ar">16:9</span><span><b>Landscape (16:9)</b><small>YouTube, Web, Desktop</small></span></button>
        <button class="choice" data-v="9:16"><span class="ar p">9:16</span><span><b>Portrait (9:16)</b><small>Shorts, TikTok, Reels</small></span></button>
      </div>
      <div class="label-up" style="margin-top:20px">Pick your channel style</div>
      <div class="choices three" id="np-tpl">${names.map((n, i) => `<button class="tpl ${i === 0 ? "on" : ""}" data-v="${esc(n)}" title="${esc(presetBlurb(n, S.presets[n]))}">
        <b>${icon(["film", "sparkles", "grid"][i % 3])}${esc(n)}</b><small>${esc(presetBlurb(n, S.presets[n]))}</small></button>`).join("")}</div>
    </div>
    <div class="modal-f"><button class="btn ghost" data-x>Cancel</button><button class="btn primary" id="np-go">${icon("plus")} Create &amp; Open Project</button></div></div>`);
  $$("#np-ar .choice", m).forEach((b) => (b.onclick = () => { aspect = b.dataset.v; $$("#np-ar .choice", m).forEach((x) => x.classList.toggle("on", x === b)); }));
  $$("#np-tpl .tpl", m).forEach((b) => (b.onclick = () => { preset = b.dataset.v; $$("#np-tpl .tpl", m).forEach((x) => x.classList.toggle("on", x === b)); }));
  const name = $("#np-name", m);
  name.focus();
  const create = () => guard(async () => {
    if (!name.value.trim()) { name.focus(); throw new Error("Type a project name."); }
    const p = await api("POST", "/api/projects", { name: name.value.trim(), aspect, preset });
    closeModal();
    S.project = p; S.draft = null; S.draftInfo = null; S.draftName = null;
    toast(`Project "${p.name}" created.`, "ok");
    location.hash = `#/workspace/${encodeURIComponent(p.folder)}/1`;
  });
  $("#np-go", m).onclick = create;
  name.onkeydown = (e) => { if (e.key === "Enter") create(); };
}

// ----------------------------------------------------------------------------------------------- other pages
async function showProjects() {
  const view = $("#view");
  view.innerHTML = `<div class="page-h"><div><h1>Projects</h1><p>Every project is a folder with its inputs, settings, timings and videos.</p></div><span class="spacer"></span>
    <button class="btn blue" id="pp-new">${icon("plus")} New Project</button></div><div class="cards" id="pp-cards"></div>`;
  $("#pp-new").onclick = openNewProject;
  await guard(async () => {
    const list = await api("GET", "/api/projects");
    const box = $("#pp-cards");
    if (!list.length) box.innerHTML = `<div class="empty" style="grid-column:1/-1">${icon("folder")}<h3>No projects yet</h3><p>Create your first project.</p></div>`;
    list.forEach((pr) => {
      const cover = pr.thumb_scene ? `style="background-image:linear-gradient(rgba(0,0,0,.05),rgba(0,0,0,.35)),url('/api/projects/${encodeURIComponent(pr.folder)}/thumb/${pr.thumb_scene}')"` : "";
      const c = el(`<div class="pcard"><div class="cover" ${cover}><span class="tag">${pr.aspect}</span>${pr.thumb_scene ? "" : "SF"}</div>
        <div class="body"><b>${esc(pr.name)}</b><p>${esc(pr.preset)} · ${pr.scenes} scenes · ${fmtDur(pr.duration)}<br>Last changed ${fmtDate(pr.modified)}</p></div>
        <div class="foot">${pr.outputs.length ? '<span class="pill-s green">rendered</span>' : pr.synced ? '<span class="pill-s purple">synced</span>' : '<span class="pill-s">draft</span>'}
          <span class="spacer" style="flex:1"></span><button class="btn sm danger" data-del>${icon("trash")}</button>
          <a class="btn sm primary" href="#/workspace/${encodeURIComponent(pr.folder)}">Open</a></div></div>`);
      $("[data-del]", c).onclick = async () => {
        if (!(await confirmDialog(`Delete "${pr.name}"?`, "<p>This deletes the project folder with all its copied files and rendered videos. This cannot be undone.</p>", "Delete project"))) return;
        guard(async () => {
          await api("DELETE", `/api/projects/${encodeURIComponent(pr.folder)}`);
          if (S.project && S.project.folder === pr.folder) { S.project = null; store.set("sf-last", ""); setTitle(); }
          showProjects();
        });
      };
      box.appendChild(c);
    });
  });
}

async function showHistory() {
  const view = $("#view");
  view.innerHTML = `<div class="page-h"><div><h1>Render History</h1><p>All finished videos, newest first.</p></div></div>
    <div class="panel"><div class="table-wrap"><table class="t"><thead><tr><th>Video</th><th>Project</th><th>Size</th><th>Finished</th><th></th></tr></thead><tbody id="h-body"></tbody></table></div></div>`;
  await guard(async () => {
    const list = await api("GET", "/api/projects");
    const rows = [];
    list.forEach((pr) => pr.outputs.forEach((o) => rows.push({ pr, o })));
    rows.sort((a, b) => b.o.mtime - a.o.mtime);
    const tb = $("#h-body");
    tb.innerHTML = rows.length ? "" : `<tr><td colspan="5" class="help" style="padding:20px">No videos rendered yet.</td></tr>`;
    rows.forEach(({ pr, o }) => {
      const tr = el(`<tr><td><b>${esc(o.name)}</b></td><td>${esc(pr.name)}</td><td class="num">${fmtSize(o.size)}</td><td class="num">${fmtDate(o.mtime)}</td>
        <td><div class="nudge"><button class="btn xs" data-play>${icon("play-s")} Play</button><button class="btn xs" data-open>${icon("open")} Folder</button></div></td></tr>`);
      $("[data-play]", tr).onclick = () => modal(`<div class="modal video"><div class="modal-h"><div class="mi">${icon("film")}</div><div><h3>${esc(o.name)}</h3><p>${esc(pr.name)}</p></div><button class="x" data-x>&times;</button></div>
        <div class="modal-b"><video class="video-out" controls autoplay src="/api/projects/${encodeURIComponent(pr.folder)}/file/${o.path}?v=${Math.round(o.mtime)}"></video></div></div>`);
      $("[data-open]", tr).onclick = () => guard(() => api("POST", `/api/projects/${encodeURIComponent(pr.folder)}/open-output`));
      tb.appendChild(tr);
    });
  });
}

async function showPresets(filter = "all") {
  const view = $("#view");
  S.presets = await api("GET", "/api/presets").catch(() => S.presets || {});
  const names = Object.keys(S.presets);
  const count = (a) => names.filter((n) => S.presets[n].aspect === a).length;
  view.innerHTML = `<div class="page-h"><div class="badge" style="width:48px;height:48px;border-radius:14px;background:var(--grad);color:#fff">${icon("sparkles")}</div>
    <div><h1>Presets</h1><p>Your channel styles: motion, transitions, captions and audio. New projects start from one of these.</p></div><span class="spacer" style="flex:1"></span>
    <button class="btn" id="pr-reset">${icon("refresh")} Restore original presets</button></div>
    <div class="filters">
      <button class="chip ${filter === "all" ? "on" : ""}" data-f="all">All presets (${names.length})</button>
      <button class="chip ${filter === "16:9" ? "on" : ""}" data-f="16:9">Landscape 16:9 (${count("16:9")})</button>
      <button class="chip ${filter === "9:16" ? "on" : ""}" data-f="9:16">Portrait 9:16 (${count("9:16")})</button></div>
    <div class="cards" id="pr-cards"></div>`;
  $$(".filters .chip", view).forEach((b) => (b.onclick = () => showPresets(b.dataset.f)));
  $("#pr-reset").onclick = () => guard(async () => { S.presets = await api("POST", "/api/presets-reset"); toast("Original presets restored (your own presets were kept).", "ok"); showPresets(filter); });
  const box = $("#pr-cards");
  const covers = ["linear-gradient(135deg,#1b1d24,#3b2a6b)", "linear-gradient(135deg,#2b1055,#7597de)", "linear-gradient(135deg,#0f2027,#2c5364)", "linear-gradient(135deg,#42275a,#734b6d)"];
  names.filter((n) => filter === "all" || S.presets[n].aspect === filter).forEach((n, i) => {
    const st = S.presets[n];
    const c = el(`<div class="pcard"><div class="cover" style="background:${covers[i % covers.length]}"><span class="tag">${st.aspect}</span>${esc(n)}</div>
      <div class="body"><b>${esc(n)}</b><p>${esc(presetBlurb(n, st))}</p></div>
      <div class="foot"><button class="btn sm primary" data-a="edit">${icon("settings")} Edit</button><button class="btn sm" data-a="dup">${icon("copy")} Duplicate</button>
      <button class="btn sm" data-a="ren">${icon("edit")} Rename</button><span style="flex:1"></span><button class="btn sm danger icon" style="width:32px" data-a="del" title="Delete">${icon("trash")}</button></div></div>`);
    $$("[data-a]", c).forEach((b) => (b.onclick = () => presetAction(b.dataset.a, n, filter)));
    box.appendChild(c);
  });
}

function askName(title, value) {
  return new Promise((resolve) => {
    const m = modal(`<div class="modal"><div class="modal-h"><div class="mi">${icon("edit")}</div><div><h3>${esc(title)}</h3></div><button class="x" data-x>&times;</button></div>
      <div class="modal-b"><input class="input" id="nm" value="${esc(value)}" maxlength="60"></div>
      <div class="modal-f"><button class="btn ghost" data-x>Cancel</button><button class="btn primary" id="nm-ok">OK</button></div></div>`, () => resolve(null));
    const inp = $("#nm", m);
    inp.select();
    const ok = () => { const v = inp.value.trim(); m._onClose = null; closeModal(); resolve(v || null); };
    $("#nm-ok", m).onclick = ok;
    inp.onkeydown = (e) => { if (e.key === "Enter") ok(); };
  });
}

async function presetAction(a, n, filter) {
  if (a === "dup") {
    const nn = await askName("Name for the copy", `${n} copy`);
    if (nn) await guard(async () => { S.presets = await api("POST", `/api/presets/${encodeURIComponent(n)}/duplicate`, { new_name: nn }); toast(`Created "${nn}".`, "ok"); });
  } else if (a === "ren") {
    const nn = await askName("Rename preset", n);
    if (nn && nn !== n) await guard(async () => { S.presets = await api("POST", `/api/presets/${encodeURIComponent(n)}/rename`, { new_name: nn }); toast(`Renamed to "${nn}".`, "ok"); });
  } else if (a === "del") {
    if (await confirmDialog(`Delete preset "${n}"?`, "<p>Projects that already use it keep their own copy of the settings.</p>", "Delete")) {
      await guard(async () => { S.presets = await api("DELETE", `/api/presets/${encodeURIComponent(n)}`); });
    }
  } else if (a === "edit") {
    const st = S.presets[n];
    let aspect = st.aspect;
    const m = modal(`<div class="modal wide"><div class="modal-h"><div class="mi">${icon("sparkles")}</div><div><h3>Edit preset: ${esc(n)}</h3><p>Used by new projects. Saved in settings\\presets.json.</p></div><button class="x" data-x>&times;</button></div>
      <div class="modal-b"><div class="label-up">Default aspect ratio</div>
        <div class="choices" id="pe-ar" style="margin-bottom:16px">
          <button class="choice ${aspect === "16:9" ? "on" : ""}" data-v="16:9"><span class="ar">16:9</span><span><b>Landscape</b><small>YouTube</small></span></button>
          <button class="choice ${aspect === "9:16" ? "on" : ""}" data-v="9:16"><span class="ar p">9:16</span><span><b>Portrait</b><small>Shorts</small></span></button></div>
        <div id="pe-form"></div></div>
      <div class="modal-f"><button class="btn ghost" data-x>Cancel</button><button class="btn primary" id="pe-save">${icon("save")} Save preset</button></div></div>`);
    $$("#pe-ar .choice", m).forEach((b) => (b.onclick = () => { aspect = b.dataset.v; $$("#pe-ar .choice", m).forEach((x) => x.classList.toggle("on", x === b)); }));
    const form = settingsForm(st);
    $("#pe-form", m).appendChild(form);
    $("#pe-save", m).onclick = () => guard(async () => {
      const ns = readSettingsForm(form, st);
      ns.aspect = aspect;
      S.presets = await api("PUT", `/api/presets/${encodeURIComponent(n)}`, ns);
      closeModal();
      toast(`Preset "${n}" saved.`, "ok");
      showPresets(filter);
    });
    return;
  }
  showPresets(filter);
}

async function showSettings() {
  const view = $("#view");
  const m = S.meta || {};
  view.innerHTML = `<div class="page-h"><div><h1>Settings</h1><p>About this SceneForge installation.</p></div></div>
    <div class="grid2">
      <div class="card"><div class="card-h"><h2>${icon("lock")} Privacy</h2><p>SceneForge is a personal tool that runs only on this laptop.</p></div>
        <div class="card-b"><div class="notice ok">${icon("check")}<div>Your voice-overs, scripts, images, clips and videos never leave this computer. The app only listens on this computer (127.0.0.1) and can't be reached from other devices.</div></div>
        <div class="kv"><span>Projects folder</span><code style="word-break:break-all">${esc(m.projects_dir || "")}</code>
        <span>Speech models</span><b>${(m.models || []).join(", ")} (faster-whisper, CPU, int8)</b>
        <span>Fonts found</span><b>${(m.fonts || []).length}</b><span>Version</span><b>${esc(m.version || "")}</b></div></div></div>
      <div class="card"><div class="card-h"><h2>${icon("info")} Quick help</h2><p>Naming files and writing scripts.</p></div>
        <div class="card-b" style="line-height:1.7">
          <b>Script:</b> start every scene with <code>Scene 1:</code>, <code>Scene 2:</code> ... Text in [square brackets] is a note, not narration.<br>
          <b>Media:</b> the number in the file name is the scene: <code>Scene 1.png</code>, <code>scene_1.mp4</code>, <code>1.jpg</code> → scene 1.<br>
          <b>Voice-over in parts:</b> name them part1, part2 ... and pick them all at once.<br>
          <b>Flagged scenes (⚠):</b> preview them in step 4 and nudge the start if needed.<br>
          <b>Render stopped?</b> Press Render again - it continues where it left off.</div></div>
    </div>`;
}

// ----------------------------------------------------------------------------------------------- top bar
$("#side-new").onclick = () => guard(openNewProject);
$("#top-new").onclick = () => guard(openNewProject);
$("#title-input").onchange = () => guard(async () => {
  if (!S.project) return;
  const name = $("#title-input").value.trim();
  if (!name) { setTitle(); return; }
  S.project = await api("PATCH", `/api/projects/${encodeURIComponent(S.project.folder)}`, { name });
  toast("Project renamed.", "ok");
});
$("#top-save").onclick = () => guard(async () => {
  if (!S.project) throw new Error("No project open.");
  const name = $("#title-input").value.trim();
  if (name && name !== S.project.name) S.project = await api("PATCH", `/api/projects/${encodeURIComponent(S.project.folder)}`, { name });
  if ($("#script-text") && (S.draft || "").trim() && S.draftInfo && !S.draftInfo.saved) { if (!(await saveScript())) return; renderScriptBox(); }
  if ($("#proj-form .sf")) await saveProjectStyle(true);
  toast("Saved. (SceneForge also saves after every step.)", "ok");
});

window.addEventListener("hashchange", route);
window.go = go;
(async function init() {
  fillIcons(document);
  try {
    S.meta = await api("GET", "/api/meta");
    $("#version").textContent = `SceneForge ${S.meta.version} · local`;
    const cur = await api("GET", "/api/jobs");
    if (cur.job) {
      watchJob(cur.job, async () => {
        if (S.project && S.project.folder === cur.job.project) S.project = await api("GET", `/api/projects/${encodeURIComponent(S.project.folder)}`);
        route();
      });
    }
  } catch (e) { toast(e.message, "err"); }
  route();
})();
