import { invoke, listen } from "./api.js";
import { appendLog, setProgress } from "./log.js";
import { refreshLibrary } from "./library.js";
import {
  hideInit,
  showWizard,
  renderPrereqs,
  wizardNeeded,
  importCookiesFromPicker,
} from "./wizard.js";

const logEl = document.getElementById("log");
const progressEl = document.getElementById("progress-line");
const prereqList = document.getElementById("prereq-list");
const prereqNotes = document.getElementById("prereq-notes");
const libraryList = document.getElementById("library-list");
const downloadBtn = document.getElementById("download-btn");
const cancelBtn = document.getElementById("cancel-btn");
const jobStatus = document.getElementById("job-status");
const engineMeta = document.getElementById("engine-meta");
const libraryPathEl = document.getElementById("library-path");
const urlInput = document.getElementById("url-input");
const urlPreview = document.getElementById("url-preview");
const skipExisting = document.getElementById("skip-existing");
const runBeautify = document.getElementById("run-beautify");
const form = document.getElementById("download-form");

let running = false;
let cancelled = false;
let previewTimer = 0;
let previewSeq = 0;

async function refreshUrlPreview() {
  const value = urlInput.value.trim();
  const seq = ++previewSeq;
  if (!value) {
    urlPreview.textContent = "";
    return;
  }
  urlPreview.textContent = "Checking URL…";
  try {
    const product = await invoke("resolve_preview", { input: value });
    if (seq !== previewSeq) return;
    urlPreview.textContent = (product && product.preview) || "";
  } catch (e) {
    if (seq !== previewSeq) return;
    urlPreview.textContent = e.message || "";
  }
}

function scheduleUrlPreview() {
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(() => {
    refreshUrlPreview().catch(() => {});
  }, 400);
}

async function loadAll() {
  const report = await invoke("check_prerequisites");
  const settings = await invoke("get_settings");
  renderPrereqs(report, prereqList, prereqNotes);
  urlInput.value = settings.lastUrl || "";
  skipExisting.checked = settings.skipExisting !== false;
  runBeautify.checked = settings.beautify !== false;
  libraryPathEl.textContent = settings.libraryPath || "";
  downloadBtn.disabled = !report.sidecar || !report.cookies || (report.platform === "windows" && !report.webview2);
  try {
    const ver = await invoke("engine_version");
    const eng = ver.engine || "?";
    const dl = ver.dl_coursera || ver.dlCoursera || "?";
    engineMeta.textContent = `Engine ${eng} · dl_coursera ${dl}`;
  } catch (e) {
    engineMeta.textContent = e.message || "Engine unavailable";
  }
  await refreshLibrary(libraryList).catch(() => {});
  scheduleUrlPreview();
  return { report, settings };
}

function setBusy(on) {
  running = on;
  downloadBtn.disabled = on;
  cancelBtn.disabled = !on;
}

async function onReady() {
  try {
    const { report, settings } = await loadAll();
    showWizard(wizardNeeded(report, settings));
  } catch (e) {
    jobStatus.textContent = e.message || String(e);
    showWizard(true);
  } finally {
    hideInit();
  }
}

document.getElementById("wizard-import").addEventListener("click", async () => {
  try {
    await importCookiesFromPicker();
    const { report, settings } = await loadAll();
    if (!wizardNeeded(report, settings)) showWizard(false);
  } catch (e) {
    document.getElementById("wizard-log").textContent = e.message || String(e);
  }
});

document.getElementById("wizard-folder").addEventListener("click", async () => {
  try {
    const dir = await invoke("pick_library_dir");
    if (!dir) return;
    const settings = await invoke("get_settings");
    settings.libraryPath = dir;
    await invoke("save_settings", { data: settings });
    await loadAll();
  } catch (e) {
    document.getElementById("wizard-log").textContent = e.message || String(e);
  }
});

document.getElementById("wizard-continue").addEventListener("click", async () => {
  try {
    const settings = await invoke("get_settings");
    settings.wizardComplete = true;
    await invoke("save_settings", { data: settings });
    showWizard(false);
    await loadAll();
  } catch (e) {
    document.getElementById("wizard-log").textContent = e.message || String(e);
  }
});

document.getElementById("refresh-prereqs").addEventListener("click", () => {
  loadAll().catch((e) => {
    jobStatus.textContent = e.message || String(e);
  });
});

document.getElementById("open-wizard").addEventListener("click", () => showWizard(true));

document.getElementById("import-cookies").addEventListener("click", async () => {
  try {
    await importCookiesFromPicker();
    await loadAll();
    jobStatus.textContent = "Cookies imported.";
  } catch (e) {
    jobStatus.textContent = e.message || String(e);
  }
});

document.getElementById("change-folder").addEventListener("click", async () => {
  try {
    const dir = await invoke("pick_library_dir");
    if (!dir) return;
    const settings = await invoke("get_settings");
    settings.libraryPath = dir;
    await invoke("save_settings", { data: settings });
    await loadAll();
  } catch (e) {
    jobStatus.textContent = e.message || String(e);
  }
});

document.getElementById("open-library").addEventListener("click", async () => {
  try {
    await invoke("open_library_folder");
  } catch (e) {
    jobStatus.textContent = e.message || String(e);
  }
});

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  jobStatus.textContent = "";
  logEl.textContent = "";
  cancelled = false;
  setProgress(progressEl, { phase: "start", message: "Starting download" });
  try {
    setBusy(true);
    await invoke("start_download", {
      options: {
        input: urlInput.value.trim(),
        skipExisting: skipExisting.checked,
        beautify: runBeautify.checked,
      },
    });
  } catch (e) {
    setBusy(false);
    jobStatus.textContent = e.message || String(e);
  }
});

cancelBtn.addEventListener("click", async () => {
  try {
    const result = await invoke("cancel_download");
    cancelled = true;
    setBusy(false);
    const removed = result && result.removed;
    appendLog(logEl, removed ? `Cancel: stopped the engine and deleted ${removed}\n` : "Cancel: stopped the engine.\n");
    jobStatus.textContent = removed
      ? "Cancelled. In-progress course folder removed."
      : "Cancelled.";
    await refreshLibrary(libraryList).catch(() => {});
  } catch (e) {
    setBusy(false);
    jobStatus.textContent = e.message || String(e);
  }
});

listen("download-log", (ev) => {
  appendLog(logEl, String(ev.payload || ""));
});

listen("download-progress", (ev) => {
  setProgress(progressEl, ev.payload);
  if (ev.payload && ev.payload.message) {
    appendLog(logEl, `[${ev.payload.phase}] ${ev.payload.message}\n`);
  }
});

listen("download-started", () => {
  jobStatus.textContent = "Download running…";
});

listen("download-finished", (ev) => {
  setBusy(false);
  if (cancelled) {
    cancelled = false;
    refreshLibrary(libraryList).catch(() => {});
    return;
  }
  const code = ev.payload && ev.payload.code;
  if (code === 0) {
    jobStatus.textContent = "Finished.";
    setProgress(progressEl, { phase: "done", message: "Finished" });
  } else {
    jobStatus.textContent = `Engine exited with code ${code}. Check the log.`;
  }
  refreshLibrary(libraryList).catch(() => {});
  loadAll().catch(() => {});
});

urlInput.addEventListener("input", scheduleUrlPreview);
urlInput.addEventListener("paste", () => {
  window.setTimeout(() => scheduleUrlPreview(), 0);
});

onReady();
