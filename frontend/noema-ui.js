"use strict";

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

synchronizeVersion();
refreshStatusEventVisibility();

const chatList = document.querySelector("#chat-list");
if (chatList) {
  const observer = new MutationObserver(refreshStatusEventVisibility);
  observer.observe(chatList, { childList: true });
}
