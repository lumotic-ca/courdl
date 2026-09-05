export function unwrap(result) {
  if (result && result.ok === false) {
    throw new Error(result.message || result.code || "Request failed");
  }
  if (result && result.ok === true && "value" in result) {
    return result.value;
  }
  return result;
}

function tauri() {
  const t = window.__TAURI__;
  if (!t || !t.core) {
    throw new Error("Tauri API is not available. Run CourDL as the desktop app.");
  }
  return t;
}

export async function invoke(cmd, args) {
  return unwrap(await tauri().core.invoke(cmd, args));
}

export function listen(event, handler) {
  return tauri().event.listen(event, handler);
}
