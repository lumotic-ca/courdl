export function appendLog(el, text) {
  el.textContent += text.endsWith("\n") ? text : `${text}\n`;
  el.scrollTop = el.scrollHeight;
}

export function setProgress(el, payload) {
  if (!payload) {
    el.textContent = "";
    return;
  }
  const phase = payload.phase || "";
  const msg = payload.message || "";
  if (payload.current != null && payload.total != null) {
    el.textContent = `${phase}: ${payload.current}/${payload.total} ${msg}`.trim();
  } else {
    el.textContent = `${phase}: ${msg}`.trim();
  }
}
