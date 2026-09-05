import { invoke } from "./api.js";

export async function refreshLibrary(listEl) {
  const items = await invoke("list_library");
  listEl.innerHTML = "";
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "No downloaded courses in this folder yet.";
    listEl.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item.name;
    li.title = item.path;
    listEl.appendChild(li);
  }
}
