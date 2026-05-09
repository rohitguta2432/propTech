/**
 * Service worker (Manifest V3 module). Two responsibilities:
 *
 *   1. On first install, open the propcheck.rohitraj.tech onboarding page
 *      so the user knows what they just installed.
 *   2. Route messages from content scripts and popup:
 *        OPEN_FULL_REPORT       → open propcheck.rohitraj.tech/check/<id>
 *        OPEN_PROPCHECK_HOMEPAGE → open homepage with optional ?url=...
 */

import type { WorkerMessage } from "../shared/types.js";
import { createLogger } from "../shared/log.js";

const log = createLogger("worker");
const ONBOARDING_URL = "https://propcheck.rohitraj.tech/?source=extension-install";
const REPORT_BASE = "https://propcheck.rohitraj.tech/check/";
const HOME_BASE = "https://propcheck.rohitraj.tech/";

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.tabs.create({ url: ONBOARDING_URL }).catch((e) => {
      log.warn("could not open onboarding tab", e);
    });
  }
});

chrome.runtime.onMessage.addListener((message: unknown, _sender, sendResponse) => {
  const msg = message as WorkerMessage | null;
  if (!msg || typeof msg !== "object" || typeof msg.type !== "string") {
    sendResponse({ ok: false, error: "invalid message" });
    return false;
  }
  switch (msg.type) {
    case "OPEN_FULL_REPORT": {
      const target = `${REPORT_BASE}${encodeURIComponent(msg.id)}`;
      chrome.tabs.create({ url: target }).then(
        () => sendResponse({ ok: true }),
        (e) => sendResponse({ ok: false, error: String(e) }),
      );
      return true; // async response
    }
    case "OPEN_PROPCHECK_HOMEPAGE": {
      const params = msg.url ? `?url=${encodeURIComponent(msg.url)}` : "";
      chrome.tabs.create({ url: HOME_BASE + params }).then(
        () => sendResponse({ ok: true }),
        (e) => sendResponse({ ok: false, error: String(e) }),
      );
      return true;
    }
    default: {
      sendResponse({ ok: false, error: `unknown type` });
      return false;
    }
  }
});

log.info("service worker booted");
