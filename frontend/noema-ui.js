"use strict";

function installKittStyles() {
  if (document.querySelector("link[data-kitt-header]")) {
    return;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `/kitt-header.css${window.location.search || ""}`;
  link.dataset.kittHeader = "true";
  document.head.append(link);
}

function mountKittStrip() {
  const topbar = document.querySelector(".topbar");
  const scanner = document.querySelector("#kitt");
  const statusCluster = document.querySelector(".status-cluster");
  if (!topbar || !scanner || !statusCluster) {
    return null;
  }

  const existing = document.querySelector("#kitt-strip");
  if (existing) {
    if (!existing.contains(scanner)) {
      existing.append(scanner);
    }
    return existing;
  }

  const strip = document.createElement("div");
  strip.className = "kitt-strip";
  strip.id = "kitt-strip";
  strip.dataset.speaking = "false";
  strip.setAttribute("role", "img");
  strip.setAttribute(
    "aria-label",
    "KITT-Scanner: reagiert auf eingehende Nachrichten und laufende Sprachausgabe",
  );

  topbar.insertBefore(strip, statusCluster);
  strip.append(scanner);
  return strip;
}

function setKittSpeaking(speaking) {
  const active = Boolean(speaking);
  const strip = document.querySelector("#kitt-strip");
  const scanner = document.querySelector("#kitt");

  for (const element of [strip, scanner]) {
    if (element) {
      element.classList.toggle("is-speaking", active);
    }
  }
  if (strip) {
    strip.dataset.speaking = active ? "true" : "false";
  }
}

let kittStateRequestRunning = false;

async function refreshKittSpeakingState() {
  if (kittStateRequestRunning || document.visibilityState === "hidden") {
    return;
  }
  kittStateRequestRunning = true;
  try {
    const response = await fetch("/tts/state", { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const state = await response.json();
    setKittSpeaking(Boolean(state && state.speaking));
  } catch (_) {
    // Bei einem kurzen API-Aussetzer den letzten sichtbaren Zustand behalten.
  } finally {
    kittStateRequestRunning = false;
  }
}

async function synchronizeVersion() {
  const chip = document.querySelector("#app-version");
  if (!chip) {
    return;
  }
  try {
    const response = await fetch("/openapi.json", { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const documentInfo = await response.json();
    const version = documentInfo && documentInfo.info && documentInfo.info.version;
    if (version) {
      chip.textContent = `v${version}`;
      document.title = `NOEMA Live Bridge v${version}`;
    }
  } catch (_) {
    // Die feste Versionsangabe im HTML bleibt als sicherer Fallback sichtbar.
  }
}

function refreshStatusEventVisibility() {
  const list = document.querySelector("#chat-list");
  if (!list) {
    return;
  }

  const entries = [...list.querySelectorAll(".chat-entry")];
  for (const entry of entries) {
    const badge = entry.querySelector(".event-badge[data-type='status']");
    entry.dataset.noemaStatus = badge ? "hidden" : "visible";
  }

  const visibleEvents = entries.some(
    (entry) => entry.dataset.noemaStatus !== "hidden",
  );
  const nativeEmptyState = Boolean(list.querySelector(".empty-state"));
  list.dataset.statusOnly = !visibleEvents && !nativeEmptyState ? "true" : "false";
}

installKittStyles();
mountKittStrip();
synchronizeVersion();
refreshStatusEventVisibility();
refreshKittSpeakingState();
window.setInterval(refreshKittSpeakingState, 250);

const chatList = document.querySelector("#chat-list");
if (chatList) {
  const observer = new MutationObserver(refreshStatusEventVisibility);
  observer.observe(chatList, { childList: true });
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    mountKittStrip();
    refreshKittSpeakingState();
  }
});
