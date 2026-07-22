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

let eqCanvas = null;
let eqContext = null;
let eqLoopStarted = false;
let level = 0;
let tick = 0;

function clamp01(value) {
  return Math.min(1, Math.max(0, value));
}

function queueEqualizerFrame() {
  window.requestAnimationFrame(drawEqualizer);
}

function drawEqualizer() {
  tick += 1;
  const kitt = document.querySelector("#kitt");
  const speaking = Boolean(kitt && kitt.classList.contains("is-speaking"));
  const active = Boolean(kitt && kitt.classList.contains("is-active"));
  const connected = Boolean(kitt && kitt.dataset.state === "live");
  const mode = speaking ? "speaking" : (connected ? "connected" : "idle");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let target = 0.05;
  if (mode === "connected") {
    target = reduced ? 0.30 : 0.30 + 0.08 * Math.sin(tick * 0.05);
  } else if (mode === "speaking") {
    target = reduced
      ? 0.55
      : clamp01(
        0.52
          + 0.30 * Math.sin(tick * 0.085)
          + 0.16 * Math.sin(tick * 0.21 + 1.3)
          + 0.08 * Math.sin(tick * 0.47 + 2.7),
      );
  }
  if (active) {
    target = Math.max(target, 0.78);
  }
  const k = target > level ? 0.32 : 0.10;
  level += (target - level) * k;

  const w = eqCanvas ? eqCanvas.clientWidth : 0;
  const h = eqCanvas ? eqCanvas.clientHeight : 0;
  if (!w || !h || document.hidden || !eqContext) {
    queueEqualizerFrame();
    return;
  }

  const dpr = window.devicePixelRatio || 1;
  const pixelWidth = Math.round(w * dpr);
  const pixelHeight = Math.round(h * dpr);
  if (eqCanvas.width !== pixelWidth || eqCanvas.height !== pixelHeight) {
    eqCanvas.width = pixelWidth;
    eqCanvas.height = pixelHeight;
    eqContext.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  const ctx = eqContext;
  ctx.clearRect(0, 0, w, h);
  if (mode === "idle" && level < 0.02) {
    queueEqualizerFrame();
    return;
  }

  const segments = 31;
  const segGap = 2;
  const segW = (w - segGap * (segments - 1)) / segments;
  const center = (segments - 1) / 2;
  const reach = level * 1.08;
  const rows = [
    { y: h * 0.00, hh: h * 0.22, scale: 0.55 },
    { y: h * 0.30, hh: h * 0.40, scale: 1.00 },
    { y: h * 0.78, hh: h * 0.22, scale: 0.55 },
  ];
  const sat = 90;
  const baseL = mode === "speaking" ? 46 : 42;
  const spanL = mode === "speaking" ? 16 : 12;
  const alphaScale = mode === "connected" ? 0.9 : 1.0;

  for (const row of rows) {
    for (let i = 0; i < segments; i += 1) {
      const dist = Math.abs(i - center) / center;
      const lit = reach - dist;
      if (lit <= 0) {
        continue;
      }
      const intensity = Math.min(1, lit * 1.7);
      const flick = reduced
        ? 1
        : 0.88
          + Math.sin(tick * 0.18 + i * 0.42) * 0.06
          + Math.random() * 0.06;
      const alpha = Math.min(1, intensity * row.scale * flick) * alphaScale;
      const lightness = baseL + intensity * spanL;
      ctx.fillStyle = `hsla(0, ${sat}%, ${lightness}%, ${alpha})`;
      const x = i * (segW + segGap);
      ctx.fillRect(x, row.y, segW, row.hh);
    }
  }

  if (level > 0.05) {
    const glowAlpha = Math.min(0.30, level * 0.4);
    const grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, "hsla(0,90%,55%,0)");
    grad.addColorStop(0.5, `hsla(0,90%,62%,${glowAlpha})`);
    grad.addColorStop(1, "hsla(0,90%,55%,0)");
    ctx.fillStyle = grad;
    ctx.fillRect(0, h * 0.30, w, h * 0.40);
  }

  queueEqualizerFrame();
}

function mountEqualizer() {
  const topbar = document.querySelector(".topbar");
  const kitt = document.querySelector("#kitt");
  const statusCluster = document.querySelector(".status-cluster");
  if (!topbar || !kitt || !statusCluster) {
    return null;
  }

  if (kitt.parentElement !== topbar || kitt.nextElementSibling !== statusCluster) {
    topbar.insertBefore(kitt, statusCluster);
  }

  if (!eqCanvas) {
    eqCanvas = kitt.querySelector(".kitt-eq-canvas");
    eqContext = eqCanvas ? eqCanvas.getContext("2d") : null;
  }
  if (eqContext && !eqLoopStarted) {
    eqLoopStarted = true;
    drawEqualizer();
  }
  return kitt;
}

function setKittSpeaking(speaking) {
  const kitt = document.querySelector("#kitt");
  if (kitt) {
    kitt.classList.toggle("is-speaking", Boolean(speaking));
  }
}

let kittStateRequestRunning = false;

async function refreshKittSpeakingState() {
  if (kittStateRequestRunning || document.hidden) {
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
mountEqualizer();
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
    mountEqualizer();
    refreshKittSpeakingState();
  }
});
