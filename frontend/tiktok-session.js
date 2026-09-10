"use strict";

function mountTikTokSessionUi() {
  if (document.querySelector("#tiktok-session-box")) return;
  const usernameInput = document.querySelector("#conn-username");
  const usernameField = usernameInput ? usernameInput.closest(".field") : null;
  if (!usernameField || !usernameField.parentElement) return;

  const box = document.createElement("div");
  box.className = "field field--wide";
  box.id = "tiktok-session-box";
  box.innerHTML = `
    <div class="field-label-line">
      <label>TikTok Browser-Session</label>
      <strong id="tiktok-session-status">WIRD GEPRÜFT …</strong>
    </div>
    <p class="key-hint" id="tiktok-session-detail">NOEMA prüft die lokale TikTok-Session.</p>
    <div class="form-actions" style="justify-content:flex-start;gap:.55rem;flex-wrap:wrap;margin-top:.55rem">
      <button class="primary-button" id="tiktok-login" type="button">Bei TikTok anmelden</button>
      <button class="secondary-button" id="tiktok-session-refresh" type="button">Login prüfen</button>
      <button class="secondary-button" id="tiktok-room-check" type="button">LIVE prüfen</button>
      <button class="ghost-button" id="tiktok-session-reset" type="button">Session löschen</button>
    </div>
    <p class="key-hint">Die Anmeldung öffnet Microsoft Edge oder Chrome mit einem eigenen lokalen NOEMA-Profil. Dein TikTok-Passwort wird ausschließlich auf tiktok.com eingegeben und nicht von NOEMA gespeichert.</p>
    <p class="action-message" id="tiktok-room-result" role="status"></p>
  `;
  usernameField.insertAdjacentElement("afterend", box);
}

mountTikTokSessionUi();

const sessionStatus = document.querySelector("#tiktok-session-status");
const sessionDetail = document.querySelector("#tiktok-session-detail");
const loginButton = document.querySelector("#tiktok-login");
const refreshButton = document.querySelector("#tiktok-session-refresh");
const resetButton = document.querySelector("#tiktok-session-reset");
const roomButton = document.querySelector("#tiktok-room-check");
const roomResult = document.querySelector("#tiktok-room-result");
const usernameInput = document.querySelector("#conn-username");

let loginPoll = null;

function setSessionText(data) {
  if (!sessionStatus || !sessionDetail) return;
  const state = data && data.state ? data.state : "idle";
  const loggedIn = Boolean(data && data.logged_in);
  sessionStatus.textContent = loggedIn ? "ANGEMELDET" : state.replaceAll("_", " ").toUpperCase();
  if (data && data.error) {
    sessionDetail.textContent = data.error;
  } else if (loggedIn) {
    sessionDetail.textContent = `${data.browser || "Browser"} · lokale TikTok-Session aktiv`;
  } else if (data && data.profile_exists) {
    sessionDetail.textContent = "Lokales Browserprofil vorhanden, Login noch nicht bestätigt.";
  } else {
    sessionDetail.textContent = "Noch keine lokale TikTok-Session eingerichtet.";
  }
}

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.detail || body.error || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body;
}

async function refreshSession() {
  try {
    const data = await jsonRequest("/tiktok/session");
    setSessionText(data);
    return data;
  } catch (error) {
    setSessionText({ state: "error", error: error.message });
    return null;
  }
}

async function verifySession() {
  if (refreshButton) refreshButton.disabled = true;
  try {
    setSessionText({ state: "checking" });
    const data = await jsonRequest("/tiktok/session/refresh", { method: "POST" });
    setSessionText(data);
  } catch (error) {
    setSessionText({ state: "error", error: error.message });
  } finally {
    if (refreshButton) refreshButton.disabled = false;
  }
}

async function startLogin() {
  if (!loginButton) return;
  loginButton.disabled = true;
  try {
    const data = await jsonRequest("/tiktok/session/login", { method: "POST" });
    setSessionText(data);
    if (loginPoll) window.clearInterval(loginPoll);
    loginPoll = window.setInterval(async () => {
      const current = await refreshSession();
      if (!current) return;
      if (current.logged_in || current.state === "error") {
        window.clearInterval(loginPoll);
        loginPoll = null;
        loginButton.disabled = false;
      }
    }, 1500);
  } catch (error) {
    setSessionText({ state: "error", error: error.message });
    loginButton.disabled = false;
  }
}

async function resetSession() {
  if (!resetButton) return;
  resetButton.disabled = true;
  try {
    const data = await jsonRequest("/tiktok/session/reset", { method: "POST" });
    setSessionText(data);
    if (roomResult) roomResult.textContent = "";
  } catch (error) {
    setSessionText({ state: "error", error: error.message });
  } finally {
    resetButton.disabled = false;
  }
}

async function checkRoom() {
  if (!roomButton || !roomResult || !usernameInput) return;
  const username = usernameInput.value.trim().replace(/^@/, "");
  if (!username) {
    roomResult.textContent = "Bitte zuerst den TikTok-Namen eintragen.";
    return;
  }
  roomButton.disabled = true;
  roomResult.textContent = "TikTok LIVE wird im lokalen Browser geprüft …";
  try {
    const data = await jsonRequest(`/tiktok/room?username=${encodeURIComponent(username)}`);
    if (data.is_live) {
      roomResult.textContent = `LIVE erkannt · Room-ID ${data.room_id || "unbekannt"} · Status ${data.live_status}`;
    } else if (data.ok) {
      roomResult.textContent = `Account erreichbar, aktuell nicht LIVE · Status ${data.live_status ?? "unbekannt"}`;
    } else {
      roomResult.textContent = `TikTok antwortet mit HTTP ${data.http_status ?? "?"}.`;
    }
  } catch (error) {
    roomResult.textContent = `LIVE-Prüfung fehlgeschlagen: ${error.message}`;
  } finally {
    roomButton.disabled = false;
  }
}

if (loginButton) loginButton.addEventListener("click", startLogin);
if (refreshButton) refreshButton.addEventListener("click", verifySession);
if (resetButton) resetButton.addEventListener("click", resetSession);
if (roomButton) roomButton.addEventListener("click", checkRoom);

refreshSession();
