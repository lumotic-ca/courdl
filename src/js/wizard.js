import { invoke } from "./api.js";

export function hideInit() {
  document.getElementById("init-overlay").classList.add("hidden");
}

export function showWizard(show) {
  document.getElementById("wizard-overlay").classList.toggle("hidden", !show);
}

export function renderPrereqs(report, listEl, notesEl) {
  const items = [
    ["CourDL engine", report.sidecar],
    ["Coursera cookies", report.cookies],
    ["WebView2", report.webview2],
  ];
  if (report.platform !== "windows") {
    items.pop();
  }
  listEl.innerHTML = "";
  for (const [label, ok] of items) {
    const li = document.createElement("li");
    li.className = ok ? "ok" : "bad";
    li.textContent = `${ok ? "OK" : "Missing"}: ${label}`;
    listEl.appendChild(li);
  }
  notesEl.textContent = (report.notes || []).join(" ");
}

export function wizardNeeded(report, settings) {
  if (!settings.wizardComplete) return true;
  if (!report.cookies) return true;
  if (report.platform === "windows" && !report.webview2) return true;
  return false;
}

export async function importCookiesFromPicker() {
  const picked = await invoke("pick_cookies_file");
  if (!picked) return null;
  await invoke("import_cookies", { source: picked });
  return picked;
}
