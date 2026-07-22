"use strict";

const MAX_CHAT_ENTRIES = 200;
const MAX_LOG_ENTRIES = 200;
const STATUS_INTERVAL_MS = 5000;
const MAX_RECONNECT_DELAY_MS = 30000;

const elements = {
  connectionDot: document.querySelector("#connection-dot"),
  connectionStatus: document.querySelector("#connection-status"),
  modeStatus: document.querySelector("#mode-status"),
  wsStatus: document.querySelector("#ws-status"),
  chatList: document.querySelector("#chat-list"),
  chatEmpty: document.querySelector("#chat-empty"),
  logList: document.querySelector("#log-list"),
  logCount: document.querySelector("#log-count"),
  audioForm: document.querySelector("#audio-form"),
  audioMessage: document.querySelector("#audio-message"),
  settingsForm: document.querySelector("#settings-form"),
  settingsMessage: document.querySelector("#settings-message"),
  ttsEnabled: document.querySelector("#tts-enabled"),
  ttsDevice: document.querySelector("#tts-device"),
  ttsVolume: document.querySelector("#tts-volume"),
  volumeOutput: document.querySelector("#volume-output"),
  ttsCooldown: document.querySelector("#tts-cooldown"),
  ttsMaxLength: document.querySelector("#tts-max-length"),
  blacklist: document.querySelector("#blacklist"),
  whitelist: document.querySelector("#whitelist"),
  retention: document.querySelector("#retention"),
  testForm: document.querySelector("#tts-test-form"),
  testText: document.querySelector("#tts-test-text"),
  testMessage: document.querySelector("#test-message"),
  stopButton: document.querySelector("#stop-tts"),
  stopMessage: document.querySelector("#stop-message"),
};

const typeLabels = {
  chat_message: "Chat",
  join: "Beitritt",
  like: "Like",
  follow: "Follow",
  share: "Share",
  gift: "Geschenk",
  subscribe: "Abo",
};

const actionLabels = {
  join: "ist dem Live-Chat beigetreten",
  like: "hat den Stream geliked",
  follow: "folgt jetzt dem Kanal",
  share: "hat den Stream geteilt",
  gift: "hat ein Geschenk gesendet",
  subscribe: "hat ein Abo abgeschlossen",
};

let socket = null;
let reconnectTimer = null;
let reconnectDelay = 1000;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : null;
  if (!response.ok) {
    const detail = body && body.detail ? body.detail : `HTTP ${response.status}`;
    throw new Error(String(detail));
  }
  return body;
}

function setMessage(element, text, state = "") {
  element.textContent = text;
  element.dataset.state = state;
}

function setOptions(select, items, emptyLabel, selectedValue) {
  select.replaceChildren();

  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = emptyLabel;
  select.append(emptyOption);

  for (const item of items) {
    const option = document.createElement("option");
    option.value = String(item.id);
    option.textContent = String(item.name);
    select.append(option);
  }

  if (selectedValue && !items.some((item) => String(item.id) === selectedValue)) {
    const retainedOption = document.createElement("option");
    retainedOption.value = selectedValue;
    retainedOption.textContent = `Gespeichert: ${selectedValue}`;
    select.append(retainedOption);
  }
  select.value = selectedValue || "";
}

function applySettings(settings) {
  elements.ttsEnabled.checked = Boolean(settings.tts_enabled);
  elements.ttsVolume.value = String(settings.tts_volume);
  elements.volumeOutput.textContent = `${settings.tts_volume} %`;
  elements.ttsCooldown.value = String(settings.tts_user_cooldown_seconds);
  elements.ttsMaxLength.value = String(settings.tts_max_length);
  elements.blacklist.value = settings.blacklist_words.join("\n");
  elements.whitelist.value = settings.whitelist_words.join("\n");
  elements.retention.value = settings.retention;
}

function linesFrom(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function collectSettings() {
  return {
    tts_enabled: elements.ttsEnabled.checked,
    tts_user_cooldown_seconds: Number.parseFloat(elements.ttsCooldown.value),
    tts_max_length: Number.parseInt(elements.ttsMaxLength.value, 10),
    blacklist_words: linesFrom(elements.blacklist.value),
    whitelist_words: linesFrom(elements.whitelist.value),
    retention: elements.retention.value,
  };
}

function collectAudioSettings() {
  return {
    tts_device: elements.ttsDevice.value || null,
    tts_volume: Number.parseInt(elements.ttsVolume.value, 10),
  };
}

async function loadConfiguration() {
  try {
    const [settings, devices] = await Promise.all([
      api("/settings"),
      api("/audio/devices"),
    ]);
    applySettings(settings);
    setOptions(elements.ttsDevice, devices, "Standardausgabe", settings.tts_device);
  } catch (error) {
    setMessage(elements.settingsMessage, `Laden fehlgeschlagen: ${error.message}`, "error");
    addLog("error", `Konfiguration konnte nicht geladen werden: ${error.message}`);
  }
}

function localizedMode(mode) {
  return {
    fallback: "Fallback",
    mock: "Simulation",
    live: "Live",
  }[mode] || mode || "–";
}

function localizedConnection(status) {
  return {
    connected: "Verbunden",
    disconnected: "Getrennt",
    unavailable: "Nicht verfügbar",
  }[status] || status || "Unbekannt";
}

async function pollStatus() {
  try {
    const status = await api("/status");
    const connected = status.connector_status === "connected";
    const unavailable = status.connector_status === "unavailable";
    elements.connectionStatus.textContent = localizedConnection(status.connector_status);
    elements.connectionDot.dataset.state = connected
      ? "connected"
      : unavailable
        ? "pending"
        : "disconnected";
    elements.modeStatus.textContent = localizedMode(status.mode);
    document.querySelector("#kitt").dataset.state = connected ? "live" : "idle";
  } catch (error) {
    elements.connectionStatus.textContent = "API nicht erreichbar";
    elements.connectionDot.dataset.state = "disconnected";
    document.querySelector("#kitt").dataset.state = "idle";
    addLog("error", `Statusabfrage fehlgeschlagen: ${error.message}`);
  }
}

function formatTime(timestamp) {
  const date = timestamp ? new Date(timestamp) : new Date();
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }
  return date.toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function describeEvent(event) {
  if (event.event_type === "chat_message") {
    return event.message || "";
  }
  if (event.event_type === "gift") {
    const giftName = event.metadata && event.metadata.gift_name;
    const count = event.metadata && event.metadata.count;
    if (giftName) {
      return `${actionLabels.gift}: ${giftName}${count ? ` × ${count}` : ""}`;
    }
  }
  return actionLabels[event.event_type] || "hat ein Ereignis ausgelöst";
}

function addChatEvent(event) {
  if (elements.chatEmpty && elements.chatEmpty.isConnected) {
    elements.chatEmpty.remove();
  }

  const entry = document.createElement("li");
  entry.className = "chat-entry";

  const badge = document.createElement("span");
  badge.className = "event-badge";
  badge.dataset.type = event.event_type || "unknown";
  badge.textContent = typeLabels[event.event_type] || "Event";

  const user = document.createElement("span");
  user.className = "chat-user";
  user.textContent = event.user && event.user.display_name
    ? event.user.display_name
    : "Unbekannt";

  const message = document.createElement("span");
  message.className = "chat-message";
  message.textContent = describeEvent(event);

  const time = document.createElement("time");
  time.className = "chat-time";
  time.dateTime = event.timestamp || "";
  time.textContent = formatTime(event.timestamp);

  entry.append(badge, user, message, time);
  elements.chatList.append(entry);
  while (elements.chatList.children.length > MAX_CHAT_ENTRIES) {
    elements.chatList.firstElementChild.remove();
  }
  elements.chatList.scrollTop = elements.chatList.scrollHeight;

  // Voicebox schlägt bei echten Chat-Nachrichten aus (kein Status-Rauschen).
  if (event.event_type === "chat_message") {
    pulseKitt();
  }
}

function addLog(level, text, timestamp = null) {
  const entry = document.createElement("li");
  entry.className = "log-entry";

  const time = document.createElement("time");
  time.className = "log-time";
  time.textContent = formatTime(timestamp);

  const label = document.createElement("span");
  label.className = "log-level";
  label.dataset.level = level;
  label.textContent = {
    event: "EREIGNIS",
    blocked: "BLOCKIERT",
    error: "FEHLER",
    system: "SYSTEM",
  }[level] || level.toUpperCase();

  const content = document.createElement("span");
  content.className = "log-text";
  content.textContent = text;

  entry.append(time, label, content);
  elements.logList.append(entry);
  while (elements.logList.children.length > MAX_LOG_ENTRIES) {
    elements.logList.firstElementChild.remove();
  }
  elements.logCount.textContent = `${elements.logList.children.length} / ${MAX_LOG_ENTRIES}`;
  elements.logList.scrollTop = elements.logList.scrollHeight;
}

function eventSummary(event) {
  const name = event.user && event.user.display_name
    ? event.user.display_name
    : "Unbekannt";
  return `${typeLabels[event.event_type] || event.event_type}: ${name} — ${describeEvent(event)}`;
}

function handleSocketMessage(payload) {
  if (payload && payload.type === "system" && payload.text) {
    addLog("system", payload.text);
    return;
  }
  if (payload && payload.type === "blocked" && payload.event) {
    addLog(
      "blocked",
      `Grund: ${payload.reason || "unbekannt"} — ${eventSummary(payload.event)}`,
      payload.event.timestamp,
    );
    return;
  }
  if (payload && payload.event_type) {
    addChatEvent(payload);
    addLog("event", eventSummary(payload), payload.timestamp);
  }
}

function scheduleReconnect() {
  if (reconnectTimer !== null) {
    return;
  }
  const delay = reconnectDelay;
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS);
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, delay);
  elements.wsStatus.textContent = `WS erneut in ${Math.ceil(delay / 1000)} s`;
}

function connectWebSocket() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${window.location.host}/ws/events`);
  elements.wsStatus.dataset.state = "pending";
  elements.wsStatus.textContent = "WS verbindet …";

  socket.addEventListener("open", () => {
    reconnectDelay = 1000;
    elements.wsStatus.dataset.state = "connected";
    elements.wsStatus.textContent = "WS verbunden";
    addLog("system", "WebSocket verbunden");
  });

  socket.addEventListener("message", (message) => {
    try {
      handleSocketMessage(JSON.parse(message.data));
    } catch (error) {
      addLog("error", `Ungültige WebSocket-Nachricht: ${error.message}`);
    }
  });

  socket.addEventListener("close", () => {
    elements.wsStatus.dataset.state = "disconnected";
    elements.wsStatus.textContent = "WS getrennt";
    addLog("error", "WebSocket getrennt");
    scheduleReconnect();
  });

  socket.addEventListener("error", () => {
    socket.close();
  });
}

elements.ttsVolume.addEventListener("input", () => {
  elements.volumeOutput.textContent = `${elements.ttsVolume.value} %`;
});

// Ein Schalter muss sofort wirken, ohne dass man weiter unten extra
// "Speichern" klickt — sonst wirkt er ausgeschaltet, obwohl er "an" zeigt.
elements.ttsEnabled.addEventListener("change", async () => {
  const enabled = elements.ttsEnabled.checked;
  elements.ttsEnabled.disabled = true;
  setMessage(elements.settingsMessage, enabled ? "Wird aktiviert …" : "Wird deaktiviert …");
  try {
    await api("/settings", {
      method: "POST",
      body: JSON.stringify({ tts_enabled: enabled }),
    });
    setMessage(
      elements.settingsMessage,
      enabled ? "Text-to-Speech ist an" : "Text-to-Speech ist aus",
      "success",
    );
    addLog("system", enabled ? "Text-to-Speech aktiviert" : "Text-to-Speech deaktiviert");
  } catch (error) {
    elements.ttsEnabled.checked = !enabled;
    setMessage(elements.settingsMessage, `Fehlgeschlagen: ${error.message}`, "error");
  } finally {
    elements.ttsEnabled.disabled = false;
  }
});

elements.audioForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = elements.audioForm.querySelector("button[type='submit']");
  button.disabled = true;
  setMessage(elements.audioMessage, "Wird gespeichert …");
  try {
    const settings = await api("/settings", {
      method: "POST",
      body: JSON.stringify(collectAudioSettings()),
    });
    applySettings(settings);
    setMessage(elements.audioMessage, "Gespeichert", "success");
    addLog("system", "Audiogerät aktualisiert");
  } catch (error) {
    setMessage(elements.audioMessage, `Speichern fehlgeschlagen: ${error.message}`, "error");
    addLog("error", `Audiogerät konnte nicht gespeichert werden: ${error.message}`);
  } finally {
    button.disabled = false;
  }
});

elements.settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = elements.settingsForm.querySelector("button[type='submit']");
  button.disabled = true;
  setMessage(elements.settingsMessage, "Wird gespeichert …");
  try {
    const settings = await api("/settings", {
      method: "POST",
      body: JSON.stringify(collectSettings()),
    });
    applySettings(settings);
    setMessage(elements.settingsMessage, "Gespeichert", "success");
    addLog("system", "Einstellungen aktualisiert");
  } catch (error) {
    setMessage(elements.settingsMessage, `Speichern fehlgeschlagen: ${error.message}`, "error");
    addLog("error", `Einstellungen konnten nicht gespeichert werden: ${error.message}`);
  } finally {
    button.disabled = false;
  }
});

elements.testForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = elements.testForm.querySelector("button[type='submit']");
  button.disabled = true;
  setMessage(elements.testMessage, "Wird eingereiht …");
  try {
    await api("/tts/test", {
      method: "POST",
      body: JSON.stringify({ text: elements.testText.value }),
    });
    setMessage(elements.testMessage, "Testnachricht eingereiht", "success");
  } catch (error) {
    setMessage(elements.testMessage, `Test fehlgeschlagen: ${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
});

elements.stopButton.addEventListener("click", async () => {
  elements.stopButton.disabled = true;
  setMessage(elements.stopMessage, "Stoppe Ausgabe …");
  try {
    await api("/tts/stop", { method: "POST", body: "{}" });
    setMessage(elements.stopMessage, "Ausgabe und Warteschlange gestoppt", "success");
    addLog("system", "TTS per NOT-AUS gestoppt");
  } catch (error) {
    setMessage(elements.stopMessage, `Stop fehlgeschlagen: ${error.message}`, "error");
  } finally {
    elements.stopButton.disabled = false;
  }
});

const connectionForm = document.querySelector("#connection-form");
const connectionMessage = document.querySelector("#connection-message");

let edgeVoicesLoaded = false;

async function ensureEdgeVoicesLoaded() {
  if (edgeVoicesLoaded) {
    return;
  }
  const hint = document.querySelector("#edge-voice-hint");
  hint.textContent = "Stimmenliste wird geladen …";
  try {
    const voices = await api("/tts/edge-voices");
    const list = document.querySelector("#edge-voice-list");
    list.innerHTML = "";
    for (const voice of voices) {
      const option = document.createElement("option");
      option.value = voice.id;
      option.label = voice.name;
      list.appendChild(option);
    }
    edgeVoicesLoaded = true;
    hint.textContent = `${voices.length} Stimmen verfügbar — Deutsch zuerst`;
  } catch (error) {
    hint.textContent = `Stimmenliste nicht ladbar: ${error.message}`;
  }
}

let sapiVoicesLoaded = false;

async function ensureSapiVoicesLoaded(selectedValue) {
  const hint = document.querySelector("#sapi-voice-hint");
  const select = document.querySelector("#conn-sapi-voice");
  if (sapiVoicesLoaded) {
    if (selectedValue) {
      select.value = selectedValue;
    }
    return;
  }
  hint.textContent = "Stimmenliste wird geladen …";
  try {
    const voices = await api("/tts/sapi-voices");
    setOptions(select, voices, "Systemstandard", selectedValue);
    sapiVoicesLoaded = true;
    hint.textContent = voices.length
      ? `${voices.length} installierte Windows-Stimmen`
      : "Keine Windows-Stimmen gefunden";
  } catch (error) {
    hint.textContent = `Stimmenliste nicht ladbar: ${error.message}`;
  }
}

function updateEngineFields() {
  const engine = connectionForm.elements.tts_engine.value;
  for (const field of connectionForm.querySelectorAll("[data-engine-only]")) {
    const engines = field.dataset.engineOnly.split(" ");
    field.hidden = !engines.includes(engine);
  }
  if (engine === "edge") {
    ensureEdgeVoicesLoaded();
  }
  if (engine === "sapi") {
    ensureSapiVoicesLoaded();
  }
}

async function loadConnection() {
  try {
    const connection = await api("/connection");
    connectionForm.elements.mode.value = connection.mode;
    connectionForm.elements.tiktok_username.value = connection.tiktok_username || "";
    connectionForm.elements.tts_engine.value = connection.tts_engine;
    connectionForm.elements.external_tts_base_url.value =
      connection.external_tts_base_url || "";
    connectionForm.elements.external_tts_model.value =
      connection.external_tts_model || "";
    connectionForm.elements.tts_voice.value = connection.tts_voice || "";
    connectionForm.elements.tts_voice_edge.value = connection.tts_voice || "";
    document.querySelector("#deepgram-hint").textContent = connection.has_deepgram_key
      ? "Schlüssel ist hinterlegt •••••••• (Feld leer lassen zum Behalten)"
      : "Noch kein Schlüssel hinterlegt";
    document.querySelector("#external-hint").textContent = connection.has_external_key
      ? "Schlüssel ist hinterlegt •••••••• (Feld leer lassen zum Behalten)"
      : "Noch kein Schlüssel hinterlegt";
    document.querySelector("[data-reveal-key='deepgram_api_key']").hidden =
      !connection.has_deepgram_key;
    document.querySelector("[data-reveal-key='external_tts_api_key']").hidden =
      !connection.has_external_key;
    updateEngineFields();
    if (connection.tts_engine === "edge") {
      ensureEdgeVoicesLoaded();
    }
    if (connection.tts_engine === "sapi") {
      ensureSapiVoicesLoaded(connection.tts_voice || "");
    }
  } catch (error) {
    addLog("error", `Verbindungsdaten nicht ladbar: ${error.message}`);
  }
}

connectionForm.elements.tts_engine.addEventListener("change", updateEngineFields);

for (const button of document.querySelectorAll(".key-reveal")) {
  button.addEventListener("click", async () => {
    const input = document.getElementById(button.dataset.target);
    if (input.type === "text") {
      input.type = "password";
      input.value = "";
      button.textContent = "Gespeicherten Schlüssel anzeigen";
      return;
    }
    try {
      const keys = await api("/connection/keys");
      const value = keys[button.dataset.revealKey];
      if (!value) {
        addLog("system", "Kein gespeicherter Schlüssel vorhanden");
        return;
      }
      input.type = "text";
      input.value = value;
      button.textContent = "Wieder verbergen";
    } catch (error) {
      addLog("error", `Schlüssel nicht abrufbar: ${error.message}`);
    }
  });
}

connectionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = connectionForm.querySelector("button[type='submit']");
  button.disabled = true;
  setMessage(connectionMessage, "Wird übernommen …");
  try {
    const body = {
      mode: connectionForm.elements.mode.value,
      tiktok_username: connectionForm.elements.tiktok_username.value,
      tts_engine: connectionForm.elements.tts_engine.value,
    };
    const key = connectionForm.elements.deepgram_api_key.value.trim();
    if (key) {
      body.deepgram_api_key = key;
    }
    const externalKey = connectionForm.elements.external_tts_api_key.value.trim();
    if (externalKey) {
      body.external_tts_api_key = externalKey;
    }
    const baseUrl = connectionForm.elements.external_tts_base_url.value.trim();
    if (baseUrl) {
      body.external_tts_base_url = baseUrl;
    }
    const model = connectionForm.elements.external_tts_model.value.trim();
    if (model) {
      body.external_tts_model = model;
    }
    const voiceByEngine = {
      edge: connectionForm.elements.tts_voice_edge.value.trim(),
      sapi: connectionForm.elements.tts_voice_sapi.value.trim(),
      external: connectionForm.elements.tts_voice.value.trim(),
      deepgram: connectionForm.elements.tts_voice.value.trim(),
    };
    const voice = voiceByEngine[body.tts_engine] || "";
    if (voice) {
      body.tts_voice = voice;
    }
    await api("/connection", { method: "POST", body: JSON.stringify(body) });
    connectionForm.elements.deepgram_api_key.value = "";
    connectionForm.elements.external_tts_api_key.value = "";
    setMessage(connectionMessage, "Übernommen — gilt sofort", "success");
    addLog("system", `Verbindung umgestellt: Modus ${body.mode}`);
    await loadConnection();
    await pollStatus();
  } catch (error) {
    setMessage(connectionMessage, `Übernehmen fehlgeschlagen: ${error.message}`, "error");
  } finally {
    button.disabled = false;
  }
});

// Kurzer heller/schneller KITT-Durchlauf als sichtbares Feedback, dass eine
// Chat-Nachricht eingetroffen ist.
let kittSilenceTimer = null;
function pulseKitt() {
  const kitt = document.querySelector("#kitt");
  if (!kitt) {
    return;
  }
  kitt.classList.add("is-active");
  if (kittSilenceTimer !== null) {
    window.clearTimeout(kittSilenceTimer);
  }
  kittSilenceTimer = window.setTimeout(() => {
    kitt.classList.remove("is-active");
    kittSilenceTimer = null;
  }, 1600);
}

loadConnection();
loadConfiguration();
pollStatus();
window.setInterval(pollStatus, STATUS_INTERVAL_MS);
connectWebSocket();

// Ein länger im Hintergrund liegender oder vergessener zweiter Tab zeigt
// sonst einen veralteten Stand (z. B. TTS-Schalter), der beim nächsten
// Speichern versehentlich den echten, zwischenzeitlich geänderten Stand
// überschreibt. Beim Zurückwechseln aktiv neu laden, nicht nur beim Start.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    loadConnection();
    loadConfiguration();
  }
});

document.querySelector("#clear-chat").addEventListener("click", () => {
  const list = document.querySelector("#chat-list");
  for (const entry of [...list.querySelectorAll(".chat-entry")]) {
    entry.remove();
  }
  if (elements.chatEmpty && !elements.chatEmpty.isConnected) {
    list.append(elements.chatEmpty);
  }
  addLog("system", "Chat-Anzeige geleert");
});
