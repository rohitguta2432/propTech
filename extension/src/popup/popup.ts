/**
 * Popup script — runs in the toolbar popup window. No fetch happens here;
 * the popup just hands the URL off to propcheck.rohitraj.tech (which has
 * the full UI and auth story) and reads recent checks from chrome.storage.
 */

import { getRecent, type RecentCheck } from "../shared/cache.js";
import { createLogger } from "../shared/log.js";

const log = createLogger("popup");
const HOME = "https://propcheck.rohitraj.tech/";

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id} not found`);
  return el;
}

function isValidUrl(s: string): boolean {
  try {
    const u = new URL(s);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

function openCheck(url: string): void {
  const target = `${HOME}?url=${encodeURIComponent(url)}&source=extension-popup`;
  chrome.tabs.create({ url: target }).catch((e) => log.warn("open tab failed", e));
}

function openHomepage(): void {
  chrome.tabs.create({ url: HOME }).catch((e) => log.warn("open tab failed", e));
}

function openRecent(r: RecentCheck): void {
  // Prefer the canonical full report by id; fall back to the URL.
  const target = `${HOME}check/${encodeURIComponent(r.id)}?source=extension-recent`;
  chrome.tabs.create({ url: target }).catch((e) => log.warn("open tab failed", e));
}

function renderRecents(list: RecentCheck[]): void {
  const ul = $("recent-list") as HTMLUListElement;
  ul.replaceChildren();
  if (list.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = "No recent checks yet.";
    ul.appendChild(empty);
    return;
  }
  for (const r of list) {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "recent";

    const score = document.createElement("div");
    score.className = "score";
    score.dataset.label = r.label;
    score.textContent = String(r.score);

    const info = document.createElement("div");
    info.className = "info";
    const title = document.createElement("div");
    title.className = "title";
    title.textContent = r.title ?? "Property listing";
    const url = document.createElement("div");
    url.className = "url";
    url.textContent = r.url;
    info.appendChild(title);
    info.appendChild(url);

    btn.appendChild(score);
    btn.appendChild(info);
    btn.addEventListener("click", () => openRecent(r));
    li.appendChild(btn);
    ul.appendChild(li);
  }
}

async function init(): Promise<void> {
  const input = $("url-input") as HTMLInputElement;
  const checkBtn = $("check-btn") as HTMLButtonElement;
  const homeBtn = $("open-home-btn") as HTMLButtonElement;

  // Pre-fill with active tab URL if it's on a supported portal.
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url && /(magicbricks\.com|99acres\.com|housing\.com|nobroker\.in)/i.test(tab.url)) {
      input.value = tab.url;
    }
  } catch {
    // ignore — popup still works
  }

  const submit = (): void => {
    const value = input.value.trim();
    if (!isValidUrl(value)) {
      input.focus();
      input.setCustomValidity("Enter a full http(s) URL");
      input.reportValidity();
      input.addEventListener("input", () => input.setCustomValidity(""), { once: true });
      return;
    }
    openCheck(value);
  };

  checkBtn.addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
  });
  homeBtn.addEventListener("click", openHomepage);

  try {
    const recent = await getRecent();
    renderRecents(recent);
  } catch (e) {
    log.warn("recent list failed", e);
  }
}

void init();
