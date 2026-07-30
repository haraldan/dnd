"use strict";

// Config field ids that map 1:1 to the persisted Config dataclass.
const NUM_FIELDS = [
  "slots_y0", "slots_y1", "modifiers_y0", "modifiers_y1",
  "top_margin", "push_offset", "render_dpi",
];
const BOOL_FIELDS = ["include_slots_on_first", "include_modifiers_on_rest"];
const BAND_FIELDS = {
  slots: { y0: "slots_y0", y1: "slots_y1", rect: "rect-slots" },
  modifiers: { y0: "modifiers_y0", y1: "modifiers_y1", rect: "rect-mods" },
};

const el = (id) => document.getElementById(id);
const state = {
  config: null,
  pageHeightPts: null, // PDF points of the currently displayed header page
  headerReady: false,
  spellsReady: false,
};

// ----------------------------------------------------------------- config I/O
async function loadConfig() {
  const r = await fetch("/config");
  state.config = await r.json();
  applyConfigToInputs();
  el("header-page").value = (state.config.header_page_index || 0) + 1;
}

function applyConfigToInputs() {
  const c = state.config;
  NUM_FIELDS.forEach((f) => { el(f).value = c[f]; });
  BOOL_FIELDS.forEach((f) => { el(f).checked = !!c[f]; });
}

function readInputsToConfig() {
  const c = state.config;
  NUM_FIELDS.forEach((f) => { c[f] = parseFloat(el(f).value); });
  BOOL_FIELDS.forEach((f) => { c[f] = el(f).checked; });
  c.header_page_index = Math.max(0, (parseInt(el("header-page").value, 10) || 1) - 1);
  return c;
}

let saveTimer = null;
function scheduleSave() {
  readInputsToConfig();
  el("save-state").textContent = "editing…";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveConfig, 700);
}

async function saveConfig() {
  el("save-state").textContent = "saving…";
  const r = await fetch("/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.config),
  });
  state.config = await r.json();
  el("save-state").textContent = "saved";
}

// ------------------------------------------------------------------- uploads
async function upload(kind, file) {
  const fd = new FormData();
  fd.append("file", file);
  const info = el(kind + "-info");
  info.textContent = "uploading…";
  const r = await fetch(`/upload/${kind}`, { method: "POST", body: fd });
  const data = await r.json();
  if (!r.ok) { info.textContent = data.error || "upload failed"; return null; }
  info.textContent = `${data.page_count} page(s)`;
  return data;
}

el("header-file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const data = await upload("header", f);
  if (!data) return;
  state.headerReady = true;
  el("header-page").max = data.page_count;
  await refreshHeaderImage();
});

el("spells-file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const data = await upload("spells", f);
  if (data) state.spellsReady = true;
});

// ------------------------------------------------------- header page + bands
async function refreshHeaderImage() {
  if (!state.headerReady) return;
  const page = Math.max(0, (parseInt(el("header-page").value, 10) || 1) - 1);
  const img = el("header-img");
  const url = `/header-page.png?page=${page}&t=${Date.now()}`;
  // Read the page height header via a fetch so we can map points<->pixels.
  const r = await fetch(url);
  state.pageHeightPts = parseFloat(r.headers.get("X-Page-Height")) || null;
  const blob = await r.blob();
  img.src = URL.createObjectURL(blob);
  img.onload = () => {
    el("tuner-stage").classList.remove("empty-state");
    positionRects();
  };
}

// px position in the stage for a given PDF-point y-value.
function ptsToPx(pts) {
  const img = el("header-img");
  if (!state.pageHeightPts || !img.clientHeight) return 0;
  return (pts / state.pageHeightPts) * img.clientHeight;
}
function pxToPts(px) {
  const img = el("header-img");
  if (!state.pageHeightPts || !img.clientHeight) return 0;
  return (px / img.clientHeight) * state.pageHeightPts;
}

function positionRects() {
  for (const [band, f] of Object.entries(BAND_FIELDS)) {
    const rect = el(f.rect);
    const y0 = parseFloat(el(f.y0).value);
    const y1 = parseFloat(el(f.y1).value);
    if (isNaN(y0) || isNaN(y1)) { rect.classList.remove("active"); continue; }
    const top = ptsToPx(Math.min(y0, y1));
    const h = Math.abs(ptsToPx(y1) - ptsToPx(y0));
    rect.style.top = top + "px";
    rect.style.height = Math.max(2, h) + "px";
    rect.classList.add("active");
  }
}

// Drag / resize the band rectangles.
function initDrag() {
  let drag = null; // { band, mode, startY, y0, y1 }
  const stage = el("tuner-stage");

  function onDown(e, band, mode) {
    e.preventDefault();
    const f = BAND_FIELDS[band];
    drag = {
      band, mode,
      startY: e.clientY,
      y0: parseFloat(el(f.y0).value),
      y1: parseFloat(el(f.y1).value),
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function onMove(e) {
    if (!drag) return;
    const f = BAND_FIELDS[drag.band];
    const dPts = pxToPts(e.clientY - drag.startY);
    let y0 = drag.y0, y1 = drag.y1;
    if (drag.mode === "move") { y0 += dPts; y1 += dPts; }
    else if (drag.mode === "top") { y0 += dPts; }
    else if (drag.mode === "bottom") { y1 += dPts; }
    const clamp = (v) => Math.max(0, Math.round(
      Math.min(v, state.pageHeightPts || v)));
    el(f.y0).value = clamp(y0);
    el(f.y1).value = clamp(y1);
    positionRects();
  }

  function onUp() {
    window.removeEventListener("mousemove", onMove);
    window.removeEventListener("mouseup", onUp);
    if (drag) { drag = null; scheduleSave(); }
  }

  stage.addEventListener("mousedown", (e) => {
    const rect = e.target.closest(".rect");
    if (!rect) return;
    const band = rect.dataset.band;
    if (e.target.classList.contains("handle-top")) onDown(e, band, "top");
    else if (e.target.classList.contains("handle-bottom")) onDown(e, band, "bottom");
    else onDown(e, band, "move");
  });
}

// --------------------------------------------------------------- render/preview
async function render(path, disposition) {
  el("render-error").textContent = "";
  if (!state.headerReady || !state.spellsReady) {
    el("render-error").textContent = "Upload both PDFs first.";
    return null;
  }
  readInputsToConfig();
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.config),
  });
  if (!r.ok) {
    let msg = "render failed";
    try { msg = (await r.json()).error || msg; } catch (_) {}
    el("render-error").textContent = msg;
    return null;
  }
  return r.blob();
}

el("preview-btn").addEventListener("click", async () => {
  const blob = await render("/preview", "inline");
  if (!blob) return;
  el("preview-empty").style.display = "none";
  el("preview-frame").src = URL.createObjectURL(blob);
});

el("download-btn").addEventListener("click", async () => {
  const blob = await render("/download", "attachment");
  if (!blob) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "spellbook.pdf";
  a.click();
});

// ------------------------------------------------------------------ wiring
NUM_FIELDS.forEach((f) => el(f).addEventListener("input", () => {
  scheduleSave();
  positionRects();
}));
BOOL_FIELDS.forEach((f) => el(f).addEventListener("change", scheduleSave));
el("header-page").addEventListener("change", async () => {
  scheduleSave();
  await refreshHeaderImage();
});
window.addEventListener("resize", positionRects);

initDrag();
loadConfig();
