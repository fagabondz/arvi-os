function hitungApiBase() {
  try {
    if (
      window.location &&
      window.location.protocol.indexOf("http") === 0 &&
      window.location.host
    ) {
      return window.location.origin;
    }
  } catch (err) {

  }
  return "http://localhost:8080";
}
const API_BASE = hitungApiBase();
const WS_URL = API_BASE.replace(/^http/, "ws") + "/ws/hud";
let ws = null;
let reconnectTimer = null;


let voiceSynthesisEnabled = true;
let isSpeaking = false;
let lastArviSpokenText = "";
let lastArviSpokenAt = 0;
let hentiMicDisengaja = false;
let transkripSuaraBerikutnya = false;
let micGagalJaringan = 0;
let pttServerAktif = false;


function hentikanMicDisengaja() {
  if (!recognition) return;
  hentiMicDisengaja = true;
  try {
    recognition.stop();
  } catch (err) {

  }
}
let lastInteractionWithArviAt = 0;
let isListening = false;


let handsFreeMode = false;


let ARVI_ELEVEN_VOICE_ID = "";
let ARVI_ELEVEN_MODEL_ID = "eleven_v4";
let ARVI_SPEECH_RATE = 1.0;
let currentArviAudio = null;

function hentikanSuaraArvi() {
  if (currentArviAudio) {
    try {
      currentArviAudio.pause();
    } catch (err) {

    }
    try {
      currentArviAudio.removeAttribute("src");
      currentArviAudio.load();
    } catch (err) {

    }
    currentArviAudio = null;
  }

  try {
    document.querySelectorAll("audio").forEach((el) => {
      try {
        el.pause();
      } catch (err) {

      }
    });
  } catch (err) {

  }
  if (window.speechSynthesis) window.speechSynthesis.cancel();


  isSpeaking = false;
  lastArviSpokenAt = Date.now();
  setBaymaxState(isListening ? "listening" : "idle");
  document.getElementById("core-state").textContent = "ARVI LISTENING";
}


let arviToken = null;
let isAuthenticated = false;
let pingTimer = null;
let statsTimer = null;
let lastPingSentAt = 0;


let visionAutoCloseTimer = null;
let workspaceAutoCloseTimer = null;

function bukaPanelVision(otomatisTutupMs) {
  const panel = document.getElementById("panel-vision");
  if (!panel) return;
  const sudahBuka = panel.classList.contains("open");
  panel.classList.add("open");
  panel.setAttribute("aria-hidden", "false");
  if (visionAutoCloseTimer) {
    clearTimeout(visionAutoCloseTimer);
    visionAutoCloseTimer = null;
  }
  if (otomatisTutupMs && otomatisTutupMs > 0) {
    visionAutoCloseTimer = setTimeout(() => {
      tutupPanelVision();
    }, otomatisTutupMs);
  }


  if (!sudahBuka && typeof mulaiPreviewKamera === "function") {
    mulaiPreviewKamera();
  }
}

function tutupPanelVision() {
  const panel = document.getElementById("panel-vision");
  if (!panel) return;
  panel.classList.remove("open");
  panel.setAttribute("aria-hidden", "true");
  if (visionAutoCloseTimer) {
    clearTimeout(visionAutoCloseTimer);
    visionAutoCloseTimer = null;
  }

  if (typeof hentikanKamera === "function") hentikanKamera();
}

function bukaPanelWorkspace(otomatisTutupMs) {
  const panel = document.getElementById("panel-workspace");
  if (!panel) return;
  const badge = document.getElementById("workspace-badge");
  if (badge) badge.classList.add("hidden");
  panel.classList.add("open");
  panel.setAttribute("aria-hidden", "false");
  if (workspaceAutoCloseTimer) {
    clearTimeout(workspaceAutoCloseTimer);
    workspaceAutoCloseTimer = null;
  }
  if (otomatisTutupMs && otomatisTutupMs > 0) {
    workspaceAutoCloseTimer = setTimeout(() => {
      tutupPanelWorkspace();
    }, otomatisTutupMs);
  }
}

function tutupPanelWorkspace() {
  const panel = document.getElementById("panel-workspace");
  if (!panel) return;
  panel.classList.remove("open");
  panel.setAttribute("aria-hidden", "true");
  if (workspaceAutoCloseTimer) {
    clearTimeout(workspaceAutoCloseTimer);
    workspaceAutoCloseTimer = null;
  }
}


function elBaru(tag, className, teks) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (teks !== undefined && teks !== null) node.textContent = String(teks);
  return node;
}

function tampilkanToast(pesan) {
  const wrap = document.getElementById("toast-wrap");
  if (!wrap) return;
  const teks = String(pesan || "").trim().slice(0, 140);
  if (!teks) return;
  while (wrap.children.length >= 3) wrap.removeChild(wrap.firstChild);
  const item = elBaru("div", "toast", teks);
  wrap.appendChild(item);
  setTimeout(() => {
    if (item.parentNode === wrap) wrap.removeChild(item);
  }, 3000);
}

function tandaiAktivitasWorkspace(label) {
  const panel = document.getElementById("panel-workspace");
  if (panel && panel.classList.contains("open")) return;
  const badge = document.getElementById("workspace-badge");
  if (badge) badge.classList.remove("hidden");
  tampilkanToast(label);
}

function bukaModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.add("open");
  m.setAttribute("aria-hidden", "false");
}

function tutupModal(id) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.remove("open");
  m.setAttribute("aria-hidden", "true");
}

function tutupSemuaModal() {
  ["modal-cyber", "modal-appsec", "modal-news"].forEach(tutupModal);
}

function _isiStat(wrap, nilai, label) {
  const chip = elBaru("div", "stat-chip");
  chip.appendChild(elBaru("div", "stat-val mono", nilai));
  chip.appendChild(elBaru("div", "stat-label", label));
  wrap.appendChild(chip);
}

function tampilkanPanelCyber(data) {
  const ping = data.ping || {};
  const tracert = Array.isArray(data.tracert) ? data.tracert : [];
  const kon = data.koneksi || {};
  const baris = Array.isArray(kon.baris) ? kon.baris : [];
  const stats = document.getElementById("cyber-stats");
  if (stats) {
    stats.textContent = "";
    const avg =
      ping.rata_ms === null || ping.rata_ms === undefined
        ? "—"
        : ping.rata_ms + " ms";
    const loss =
      ping.persen_hilang === null || ping.persen_hilang === undefined
        ? "—"
        : ping.persen_hilang + "%";
    _isiStat(stats, avg, "PING AVG (8.8.8.8)");
    _isiStat(stats, loss, "PACKET LOSS");
    _isiStat(stats, String(tracert.length), "TRACERT HOPS");
    _isiStat(stats, String(kon.total || 0), "CONNECTIONS");
  }
  const judulPing = document.getElementById("cyber-ping-title");
  if (judulPing)
    judulPing.textContent = "PING 8.8.8.8" + (data.demo ? " (live CMD demo)" : "");
  const prePing = document.getElementById("cyber-ping");
  if (prePing) {
    const mentah = Array.isArray(ping.mentah) ? ping.mentah : [];
    prePing.textContent = mentah.length
      ? mentah.join("\n")
      : "(no ping output captured)";
  }
  const preTrace = document.getElementById("cyber-tracert");
  if (preTrace) {
    preTrace.textContent = tracert.length
      ? tracert.map((h) => h.mentah || "hop " + h.hop).join("\n")
      : "(no tracert output captured)";
  }
  const tbody = document.getElementById("cyber-conn-body");
  if (tbody) {
    tbody.textContent = "";
    baris.forEach((b) => {
      const tr = elBaru("tr");
      [b.proto, b.lokal, b.remote, b.status, b.pid, b.proses].forEach((v) => {
        tr.appendChild(elBaru("td", "", v === null || v === undefined ? "" : v));
      });
      const tdTanda = elBaru("td");
      (Array.isArray(b.tanda) ? b.tanda : []).forEach((t) => {
        tdTanda.appendChild(elBaru("span", "cyber-tag", t));
      });
      tr.appendChild(tdTanda);
      tbody.appendChild(tr);
    });
    if (!baris.length) {
      const tr = elBaru("tr");
      const td = elBaru("td", "", "(tidak ada koneksi eksternal aktif)");
      td.setAttribute("colspan", "7");
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
  }
  const note = document.getElementById("cyber-conn-note");
  if (note) {
    const sumber = kon.sumber ? " via " + kon.sumber : "";
    note.textContent =
      kon.total + " koneksi eksternal" + sumber + " • " + (kon.tersaring || 0) + " loopback disaring";
  }
  const vonis = document.getElementById("cyber-vonis");
  if (vonis) {
    const galat = data.galat ? data.galat + "\n\n" : "";
    vonis.textContent = galat + (data.vonis || "Threat hunt done.");
  }
  appendTerminal("[NETSCAN] Cyber dashboard opened.");
  bukaModal("modal-cyber");
}

function tampilkanPanelAppsec(data) {
  const img = document.getElementById("appsec-img");
  if (img) {
    const src = data.image || "";
    if (/^(data:image\/|https?:\/\/)/i.test(src)) img.setAttribute("src", src);
    else img.removeAttribute("src");
  }
  const status = document.getElementById("appsec-status");
  if (status) {
    const nilai = data.status || "INFO";
    status.textContent =
      nilai === "VULNERABLE"
        ? "■ VULNERABLE"
        : nilai === "SAFE"
          ? "■ SAFE"
          : "■ " + nilai;
    status.style.color =
      nilai === "VULNERABLE" ? "#b4232a" : nilai === "SAFE" ? "#067647" : "#7d8ca3";
  }
  const detail = document.getElementById("appsec-detail");
  if (detail) detail.textContent = data.detail || "(no detail)";
  appendTerminal("[APPSEC] Audit dashboard opened.");
  bukaModal("modal-appsec");
}

function tampilkanGaleriBerita(data) {
  const daftar = Array.isArray(data.artikel) ? data.artikel : [];
  const judul = document.getElementById("news-title");
  if (judul) {
    judul.textContent =
      data.cakupan === "indonesia" ? "News // Indonesia Hari Ini" : "News // World Headlines";
  }
  const grid = document.getElementById("news-grid");
  if (grid) {
    grid.textContent = "";
    daftar.forEach((a) => {
      const kartu = elBaru("article", "news-card");
      const gbr = a.gambar || "";
      if (/^(data:image\/|https?:\/\/)/i.test(gbr)) {
        const foto = elBaru("img");
        foto.setAttribute("src", gbr);
        foto.setAttribute("alt", "");
        foto.setAttribute("loading", "lazy");
        kartu.appendChild(foto);
      } else {
        kartu.appendChild(elBaru("div", "news-ph mono", a.sumber || "ARVI NEWS"));
      }
      const badan = elBaru("div", "p-2.5 flex flex-col gap-1");
      badan.appendChild(
        elBaru("div", "text-[13px] font-semibold text-slate-700 leading-snug", a.judul || "(tanpa judul)"),
      );
      if (a.ringkasan)
        badan.appendChild(elBaru("div", "text-[11px] text-slate-500 leading-relaxed", a.ringkasan));
      const kaki = elBaru("div", "flex justify-between items-center mt-1");
      kaki.appendChild(elBaru("span", "text-[10px] text-slate-400 mono", a.sumber || ""));
      const tautan = a.tautan || "";
      if (/^https?:\/\//i.test(tautan)) {
        const link = elBaru("a", "text-[11px] font-semibold text-slate-600 hover:text-slate-900", "Buka sumber");
        link.setAttribute("href", tautan);
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener");
        kaki.appendChild(link);
      }
      badan.appendChild(kaki);
      kartu.appendChild(badan);
      grid.appendChild(kartu);
    });
  }
  appendTerminal(`[NEWS] Gallery opened (${daftar.length} cards).`);
  bukaModal("modal-news");
}


function setBaymaxState(state) {
  const head = document.getElementById("baymax-head");
  if (!head) return;
  head.classList.remove("speaking", "listening");
  if (state === "speaking") head.classList.add("speaking");
  else if (state === "listening") head.classList.add("listening");
}


let promptVisionTertunda = null;
let visiSuaraTertunda = false;

function tampilkanPilihanKamera() {
  const el = document.getElementById("vision-choice");
  if (el) el.style.display = "flex";
}

function sembunyikanPilihanKamera() {
  const el = document.getElementById("vision-choice");
  if (el) el.style.display = "none";
  promptVisionTertunda = null;
  visiSuaraTertunda = false;
}

function mintaKonfirmasiKamera(promptAsli, dariSuara = false) {
  promptVisionTertunda = promptAsli || "";
  visiSuaraTertunda = !!dariSuara;
  const tanya = "Should I use the Laptop or Mobile camera?";
  appendDialogue("ARVI CORE // MUSE SPARK", tanya, "arvi");
  speakArvi(tanya);
  tampilkanPilihanKamera();
}

function pilihKameraLaptop() {
  const prompt =
    promptVisionTertunda || "Scan the object in front of the laptop camera.";
  const dariSuara = visiSuaraTertunda;
  sembunyikanPilihanKamera();
  appendTerminal("[VISION] Device: LAPTOP. Opening the Vision panel...");
  bukaPanelVision();
  triggerOpticalScan(prompt, dariSuara);
}

async function pilihKameraHp() {
  sembunyikanPilihanKamera();
  appendTerminal("[VISION] Perangkat: HP. Menyiapkan Mobile Lens...");
  await tampilkanQrMobileLens();
}


let qrMobileAktif = false;

async function tampilkanQrMobileLens(denganPanel = true) {
  if (denganPanel) bukaPanelWorkspace();
  appendTerminal("[MOBILE LENS] Menyiapkan QR Code...");
  let url = null;
  try {
    const data = await apiJson("/api/mobile-url");
    url = data && data.url ? data.url : null;
  } catch (err) {
    appendTerminal(
      `[MOBILE LENS] Endpoint failed (${err.message}), using the local URL.`,
    );
  }
  if (!url) {

    try {
      url = window.location.origin + "/mobile-lens";
    } catch (err) {
      url = null;
    }
  }
  if (!url) {
    appendTerminal(
      "[MOBILE LENS FAILED] Cannot determine the Mobile Lens URL.",
    );
    return;
  }
  const box = document.getElementById("mobile-qr-box");
  const slot = document.getElementById("mobile-qr-code");
  const urlEl = document.getElementById("mobile-qr-url");
  box.style.display = "flex";
  urlEl.textContent = url;
  slot.innerHTML = "";
  if (typeof QRCode !== "undefined") {
    try {
      new QRCode(slot, {
        text: url,
        width: 180,
        height: 180,
        correctLevel: QRCode.CorrectLevel.M,
      });
    } catch (err) {

    }
  }


  if (!slot.querySelector("canvas, img")) {
    appendTerminal(
      "[MOBILE LENS] QR render failed — use the URL text below the box.",
    );
  }
  qrMobileAktif = true;
  appendTerminal(`[MOBILE LENS] QR siap: ${url}`);
  if (denganPanel) {
    const info =
      "Please scan the on-screen QR code with your phone camera, then press Send to ARVI on the phone.";
    appendDialogue("ARVI CORE // MUSE SPARK", info, "arvi");
    speakArvi(info);
  }
}

function toggleQrMobileLens() {
  if (qrMobileAktif) {
    bersihkanQrMobile();
  } else {
    tampilkanQrMobileLens(false);
  }
}

function bersihkanQrMobile() {
  qrMobileAktif = false;
  const box = document.getElementById("mobile-qr-box");
  const slot = document.getElementById("mobile-qr-code");
  const urlEl = document.getElementById("mobile-qr-url");
  if (box) box.style.display = "none";
  if (slot) slot.innerHTML = "";
  if (urlEl) urlEl.textContent = "";
}


function connectWebSocket() {
  if (!arviToken) {

    tampilkanLockscreen("Authenticate first to open the HUD.");
    return;
  }
  try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }

      try {
        ws.send(JSON.stringify({ type: "auth", token: arviToken }));
      } catch (err) {
        console.warn("Failed to send the auth token:", err);
      }
      const el = document.getElementById("ws-status");
      el.className = "text-slate-500 mono text-[11px] hidden md:inline";
      el.textContent = "AUTHENTICATING";
      appendTerminal("[SYNC] WebSocket terbuka, mengirim token sesi...");
    };

    ws.onmessage = (event) => {
      try {
        handleServerMessage(JSON.parse(event.data));
      } catch (err) {
        console.warn("Non-JSON WebSocket payload:", event.data);
      }
    };

    ws.onerror = () => {
      try {
        ws.close();
      } catch (err) {

      }
    };

    ws.onclose = () => {
      hentikanTelemetriLive();
      setLabelLatency("-- // LOCAL ONLY", false);
      const el = document.getElementById("ws-status");
      el.className = "text-slate-500 mono text-[11px] hidden md:inline";
      el.textContent = "STANDBY // LOCAL ONLY";
      if (isAuthenticated && arviToken) {
        scheduleReconnect();
      } else {
        tampilkanLockscreen("Connection lost. Re-authenticate to continue.");
      }
    };
  } catch (err) {
    console.log("Running in offline standalone mode.");
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (!arviToken) return;
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectWebSocket();
    }, 4000);
  }
}

let groundingTimer = null;


function tampilkanGroundingPreview(data) {
  const img = document.getElementById("grounding-img");
  if (!img || !data.image) return;
  bukaPanelVision(6000);
  img.src = data.image;
  img.classList.remove("hidden");
  const sumber = data.sumber || "klik";
  if (sumber === "klik" && data.x != null && data.y != null) {
    document.getElementById("detected-tag").textContent =
      `TARGET LOCK: ${(data.target || "?").toUpperCase()} (${data.x}, ${data.y})`;
    appendTerminal(
      `[GROUNDING] Aim '${data.target}' at (${data.x}, ${data.y}).`,
    );
  } else {
    const label = (data.target || sumber || "?").toUpperCase();
    document.getElementById("detected-tag").textContent = `PREVIEW: ${label}`;
    appendTerminal(`[PREVIEW] ${label} image shown in the Vision panel.`);
  }
  if (groundingTimer) clearTimeout(groundingTimer);
  groundingTimer = setTimeout(() => {
    img.classList.add("hidden");
    img.removeAttribute("src");
    groundingTimer = null;
  }, 6000);
}


function setEngineBadge(engine) {
  const wadah = document.getElementById("engine-badge");
  if (!wadah) return;
  const span = wadah.querySelector("span") || wadah;
  const nama = (engine || "—").toUpperCase();
  span.textContent = `ENGINE: ${nama}`;
  let warna = "bg-slate-200 text-slate-500";
  if (nama.includes("VISION")) warna = "bg-emerald-100 text-emerald-700";
  else if (nama.includes("PROACTIVE")) warna = "bg-teal-100 text-teal-700";
  else if (nama.includes("MUSE")) warna = "bg-sky-100 text-sky-700";
  span.className = `inline-block px-1.5 py-0.5 rounded-md text-[10px] mono ${warna}`;
}

function handleServerMessage(data) {
  if (data.type === "ptt_start") {

    if (recognition && isAuthenticated) {
      appendTerminal("[PTT] Global PTT pressed — listening...");
      hentikanSuaraArvi(true);
      pttServerAktif = true;
      try {
        recognition.start();
      } catch (err) {

      }
    }
    return;
  } else if (data.type === "ptt_stop") {
    pttServerAktif = false;
    appendTerminal("[PTT] Global PTT released — sending.");
    hentikanMicDisengaja();
    return;
  } else if (data.type === "auth_ok") {
    isAuthenticated = true;
    const el = document.getElementById("ws-status");
    el.className = "text-slate-600 mono text-[11px] hidden md:inline";
    el.textContent = "CONNECTED";
    appendTerminal(
      `[AUTH] Session accepted for ${data.pemilik || "?"} via ${data.metode || "?"}.`,
    );
    sembunyikanLockscreen();
    mulaiTelemetriLive();

    if (handsFreeMode && recognition) {
      try {
        recognition.start();
      } catch (err) {

      }
    }
    return;
  } else if (data.type === "auth_failed" || data.type === "auth_required") {
    kunciHud("Token sesi ditolak server. Otentikasi ulang.");
    return;
  } else if (data.type === "pong") {
    if (lastPingSentAt > 0) {
      const rtt = Math.max(0, Math.round(performance.now() - lastPingSentAt));
      setLabelLatency(`${rtt}ms `, true);
    }
    return;
  } else if (data.type === "arvi_response") {
    lastInteractionWithArviAt = Date.now();
    if (data.engine) setEngineBadge(data.engine);
    appendDialogue("ARVI CORE // MUSE SPARK", data.text, "arvi");


    if (data.text && data.text.length > 400) {
      appendTerminal(`[ARVI] ${data.text}`);
      tandaiAktivitasWorkspace("Respons panjang — buka Output untuk membaca utuh.");
    }
    speakArvi(data.text);
  } else if (data.type === "vision_response") {
    lastInteractionWithArviAt = Date.now();
    if (data.engine) setEngineBadge(data.engine);
    const textOut =
      data.text && data.text.trim()
        ? data.text
        : "[WARN] Empty visual response from the endpoint.";
    appendDialogue("OPTICAL CORTEX // SAM 3.1 + MUSE OPEN", textOut, "arvi");

    if (data.sam) {
      activeSamData = data.sam;
      const buktiSam = document.getElementById("grounding-img");
      if (buktiSam && data.sam.annotated_image) {
        buktiSam.src = data.sam.annotated_image;
        buktiSam.classList.remove("hidden");
        if (groundingTimer) clearTimeout(groundingTimer);
        groundingTimer = setTimeout(() => {
          buktiSam.classList.add("hidden");
          buktiSam.removeAttribute("src");
          groundingTimer = null;
        }, 12000);
      }
      const maskEl = document.getElementById("mask-status");
      if (maskEl && data.sam.sam_aktif) {
        const namaModelSam = data.sam.model || "Meta Vision";
        maskEl.textContent = `${data.sam.mask_count} Masks (${data.sam.vertices_count} Vertices // ${data.sam.confidence}% // ${namaModelSam})`;
      }
      const targetEl = document.getElementById("target-component");
      if (targetEl) {
        const ringkas = textOut
          .split(/[.!?\n]/)[0]
          .trim()
          .slice(0, 48);
        targetEl.textContent = ringkas || "Visual Target Identified";
      }
      document.getElementById("detected-tag").textContent = data.sam.sam_aktif
        ? "META SAM // SEGMENTED"
        : "VISION ANALYSIS COMPLETE";
      bukaPanelVision(12000);
      appendTerminal(
        `[META SAM] ${data.sam.mask_count} mask, ${data.sam.vertices_count} vertices.`,
      );
    }
    if (data.sumber === "mobile") {

      bersihkanQrMobile();
      appendTerminal(
        "[MOBILE LENS] Result received. Closing the Output panel.",
      );
      tutupPanelWorkspace();
    } else if (data.sumber === "laptop") {

      if (!data.sam) {
        document.getElementById("detected-tag").textContent =
          "VISION ANALYSIS COMPLETE";
        document.getElementById("target-component").textContent =
          "Visual Target Identified";
        document.getElementById("mask-status").textContent =
          "Segmentation unavailable";
      }

      bukaPanelVision(12000);
    }

    speakArvi(textOut);
  } else if (data.type === "mobile_user_echo") {
    lastInteractionWithArviAt = Date.now();
    appendDialogue("PHONE // USER", data.text || "", "user");
    appendTerminal(`[MOBILE ECHO] "${(data.text || "").slice(0, 120)}"`);
  } else if (data.type === "grounding_preview") {
    lastInteractionWithArviAt = Date.now();
    tampilkanGroundingPreview(data);
  } else if (data.type === "system_response") {
    lastInteractionWithArviAt = Date.now();
    const pesan = data.message || "[SYSTEM] OS command done.";
    appendDialogue("ARVI", pesan, "arvi");
    appendTerminal(`[OS] ${pesan}`);
    tandaiAktivitasWorkspace(pesan);


    if (
      pesan.length <= 45 &&
      !/^\s*\[/.test(pesan) &&
      !/error|fail|invalid|unknown|empty|too long|failsafe|not allowed|not registered|pip install/i.test(
        pesan,
      )
    ) {
      speakArvi(pesan);
    }
  } else if (data.type === "agent_log") {
    appendTerminal(data.message);

    if (
      /INFERENCE|CLOSED-LOOP|OPTICAL|AUTH|CORE|WARN|ERROR|EXCEPTION/i.test(
        data.message || "",
      )
    ) {
      tandaiAktivitasWorkspace(data.message);
    }
  } else if (data.type === "netscan_panel") {
    lastInteractionWithArviAt = Date.now();
    if (data.engine) setEngineBadge(data.engine);
    tampilkanPanelCyber(data);
  } else if (data.type === "appsec_panel") {
    lastInteractionWithArviAt = Date.now();
    if (data.engine) setEngineBadge(data.engine);
    tampilkanPanelAppsec(data);
  } else if (data.type === "news_gallery") {
    lastInteractionWithArviAt = Date.now();
    if (data.engine) setEngineBadge(data.engine);
    tampilkanGaleriBerita(data);
  }
}


document.getElementById("command-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (!isAuthenticated || !arviToken) {
    appendTerminal("[LOCKED] HUD is locked. Log in first.");
    tampilkanLockscreen("HUD is locked. Authenticate first.");
    return;
  }
  const input = document.getElementById("cmd-input");
  const val = input.value.trim();
  if (!val) return;


  const dariSuara = transkripSuaraBerikutnya;
  transkripSuaraBerikutnya = false;
  const penandaSuara = dariSuara ? { sumber: "suara", final: true } : {};


  if (terapkanPerintahKecepatan(val)) {
    appendDialogue("YOU", val, "slate");
    input.value = "";
    return;
  }

  appendDialogue("YOU", val, "slate");
  appendTerminal(`$ dispatching command: "${val}"`);

  const lowerVal = val.toLowerCase();


  if (promptVisionTertunda !== null) {
    const pilihLaptop = lowerVal.includes("laptop");
    const pilihHp =
      /\bhp\b/.test(lowerVal) ||
      lowerVal.includes("handphone") ||
      lowerVal.includes("ponsel") ||
      lowerVal.includes("mobile") ||
      lowerVal.includes("phone");
    if (pilihLaptop && !pilihHp) {
      input.value = "";
      pilihKameraLaptop();
      return;
    }
    if (pilihHp && !pilihLaptop) {
      input.value = "";
      pilihKameraHp();
      return;
    }

    sembunyikanPilihanKamera();
  }


  const osIntent = deteksiPerintahOS(val);

  const isVisionCmd =
    lowerVal.includes("kamera") ||
    lowerVal.includes("camera") ||
    lowerVal.includes("scan objek") ||
    lowerVal.includes("scan object") ||
    lowerVal.includes("lihat ini") ||
    lowerVal.includes("look at this");

  if (ws && ws.readyState === WebSocket.OPEN) {
    if (osIntent) {
      appendTerminal(
        `[OS] dispatching os_command: ${osIntent.aksi} "${osIntent.target}"`,
      );
      ws.send(
        JSON.stringify({
          type: "os_command",
          target: osIntent.target,
          aksi: osIntent.aksi,
          raw: val,
          ...penandaSuara,
        }),
      );
    } else if (isVisionCmd) {

      mintaKonfirmasiKamera(val, dariSuara);
    } else {
      ws.send(
        JSON.stringify({ type: "user_command", command: val, ...penandaSuara }),
      );
    }
  } else {
    if (osIntent) tandaiAktivitasWorkspace("Mode offline — perintah OS disimulasikan.");
    else if (isVisionCmd) bukaPanelVision(8000);
    setTimeout(() => {
      const simMsg = osIntent
        ? `Simulated response: OS command '${osIntent.aksi} ${osIntent.target}' queued. Start server/main.py for live Windows control.`
        : isVisionCmd
          ? `Simulated response: Vision analysis unavailable offline. Start server/main.py and connect for live camera analysis.`
          : `Simulated response: Processing command '${val}'. Start server/main.py for live Meta API synthesis.`;
      appendDialogue("ARVI CORE // STANDBY", simMsg, "arvi");
      speakArvi(simMsg);
    }, 600);
  }

  input.value = "";
});

function appendDialogue(sender, text, tone) {
  const box = document.getElementById("dialogue-box");
  const item = document.createElement("div");
  const isArvi = tone === "arvi" || tone === "cyan";
  item.className = `p-2 rounded-lg ${isArvi ? "bg-white border border-slate-100 text-slate-700" : "bg-slate-100/70 text-slate-600"}`;
  const senderEl = document.createElement("span");
  senderEl.className = "text-[10px] text-slate-400 block mono font-semibold";
  senderEl.textContent = sender;
  const textEl = document.createElement("div");
  textEl.className = "mt-0.5 leading-relaxed";
  textEl.textContent = text;
  item.appendChild(senderEl);
  item.appendChild(textEl);

  box.appendChild(item);
  box.scrollTop = box.scrollHeight;
}

function appendTerminal(msg) {
  const term = document.getElementById("terminal-output");
  const span = document.createElement("span");
  span.textContent = msg;
  term.appendChild(span);
  term.scrollTop = term.scrollHeight;
}


function dinginkanMicPascaBicara() {
  isSpeaking = false;
  lastArviSpokenAt = Date.now();
}


function isEchoFromArvi(transcript) {
  if (!lastArviSpokenText) return false;
  if (Date.now() - lastArviSpokenAt > 15000) return false;
  const normal = (s) =>
    (s || "")
      .toLowerCase()
      .replace(/[^a-z0-9 ]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  const trans = normal(transcript);
  const ucap = normal(lastArviSpokenText);
  if (!trans || !ucap) return false;
  if (trans.length >= 4 && ucap.includes(trans)) return true;
  const kataTrans = trans.split(" ").filter(Boolean);
  if (kataTrans.length < 2) return false;
  const kataUcap = new Set(ucap.split(" ").filter(Boolean));
  const cocok = kataTrans.filter((k) => kataUcap.has(k)).length;
  return cocok / kataTrans.length >= 0.5;
}


function cleanTextForSpeech(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/`{1,3}.*?`{1,3}/gs, "")
    .replace(/[#>\-_]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}


function ambilIntiUcapan(teks) {
  if (!teks || teks.length <= 350) return teks;
  const paragraf = teks
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
  const terakhir = paragraf[paragraf.length - 1] || teks;
  if (terakhir.length <= 350) return terakhir;

  const kalimat = terakhir.split(/(?<=[.!?])\s+/).filter(Boolean);
  return kalimat.slice(-2).join(" ") || terakhir.slice(-350);
}

async function speakArvi(rawText) {
  if (!voiceSynthesisEnabled) return;

  hentikanSuaraArvi();
  const cleanText = cleanTextForSpeech(rawText);
  if (!cleanText) return;
  const teksUcap = ambilIntiUcapan(cleanText);


  lastArviSpokenText = teksUcap;
  lastArviSpokenAt = Date.now();
  isSpeaking = true;


  try {
    const kepalaTts = { "Content-Type": "application/json" };
    if (arviToken) kepalaTts.Authorization = `Bearer ${arviToken}`;
    const res = await fetch(API_BASE + "/api/tts", {
      method: "POST",
      headers: kepalaTts,
      body: JSON.stringify({
        text: teksUcap,
        voice_id: ARVI_ELEVEN_VOICE_ID,
        model_id: ARVI_ELEVEN_MODEL_ID,
      }),
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.playbackRate = ARVI_SPEECH_RATE;
      audio.preservesPitch = true;
      currentArviAudio = audio;

      audio.onplay = () => {
        isSpeaking = true;
        setBaymaxState("speaking");
        document.getElementById("core-state").textContent = "ARVI VOCALIZING";

      };

      const selesaiAudio = () => {
        try {
          URL.revokeObjectURL(url);
        } catch (err) {

        }
        if (currentArviAudio === audio) currentArviAudio = null;
        dinginkanMicPascaBicara();
        lastInteractionWithArviAt = Date.now();
        if (!isListening) {
          setBaymaxState("idle");
          document.getElementById("core-state").textContent = "ARVI LISTENING";
        } else {
          setBaymaxState("listening");
        }
      };
      audio.onended = selesaiAudio;
      audio.onerror = () => {
        appendTerminal(
          "[AUDIO WARN] ElevenLabs audio error, falling back to the browser voice.",
        );
        selesaiAudio();
        bicaraFallbackBrowser(teksUcap);
      };

      await audio.play();
      return;
    }
    appendTerminal(
      `[AUDIO] /api/tts HTTP ${res.status}, falling back to the browser voice.`,
    );
  } catch (err) {
    appendTerminal(
      `[AUDIO] ElevenLabs failed (${err.message}), falling back to the browser voice.`,
    );
  }


  bicaraFallbackBrowser(teksUcap);
}


function teksBerbahasaIndonesia(teks) {
  const rendah = ` ${String(teks || "").toLowerCase()} `;
  const umum = [
    " yang ",
    " dan ",
    " di ",
    " ke ",
    " dari ",
    " untuk ",
    " dengan ",
    " ini ",
    " itu ",
    " ada ",
    " apa ",
    " saya ",
    " aku ",
    " kamu ",
    " tolong ",
    " coba ",
    " lihat ",
    " buka ",
    " tutup ",
    " cari ",
    " ketik ",
    " tekan ",
    " tidak ",
    " sudah ",
    " belum ",
    " bisa ",
    " mau ",
    " terima kasih ",
    " halo ",
    " hai ",
    " selamat ",
  ];
  return umum.some((kata) => rendah.includes(kata));
}

function bicaraFallbackBrowser(cleanText) {
  if (!voiceSynthesisEnabled || !window.speechSynthesis || !cleanText) {

    isSpeaking = false;
    return;
  }
  const utterance = new SpeechSynthesisUtterance(cleanText);
  utterance.rate = ARVI_SPEECH_RATE;
  utterance.pitch = 1.0;


  const voices = window.speechSynthesis.getVoices();
  const isIndonesian = teksBerbahasaIndonesia(cleanText);
  let chosenVoice = null;
  if (isIndonesian) {
    chosenVoice =
      voices.find((v) => (v.lang || "").toLowerCase().startsWith("id")) ||
      voices.find((v) => /indonesia/i.test(v.name));
  } else {
    chosenVoice =
      voices.find((v) => v.lang === "en-US") ||
      voices.find((v) => v.lang === "en-GB") ||
      voices.find((v) => (v.lang || "").toLowerCase().startsWith("en"));
  }
  if (chosenVoice) {
    utterance.voice = chosenVoice;
    utterance.lang = chosenVoice.lang;
  } else {
    utterance.lang = isIndonesian ? "id-ID" : "en-US";
  }

  utterance.onstart = () => {
    isSpeaking = true;


    setBaymaxState("speaking");
    document.getElementById("core-state").textContent = "ARVI VOCALIZING";
  };

  const selesaiUcap = () => {
    dinginkanMicPascaBicara();
    lastInteractionWithArviAt = Date.now();
    if (!isListening) {
      setBaymaxState("idle");
      document.getElementById("core-state").textContent = "ARVI LISTENING";
    } else {
      setBaymaxState("listening");
    }
  };
  utterance.onend = selesaiUcap;
  utterance.onerror = selesaiUcap;

  window.speechSynthesis.speak(utterance);
}


if (window.speechSynthesis) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}


document.getElementById("btn-toggle-voice").addEventListener("click", () => {
  voiceSynthesisEnabled = !voiceSynthesisEnabled;
  const dot = document.getElementById("voice-dot");
  const lbl = document.getElementById("voice-label");
  if (voiceSynthesisEnabled) {
    dot.className = "w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block";
    lbl.textContent = "AUDIO: ON";
    appendTerminal("[AUDIO] Voice synthesizer enabled.");
  } else {
    hentikanSuaraArvi();
    dot.className = "w-1.5 h-1.5 rounded-full bg-slate-300 inline-block";
    lbl.textContent = "AUDIO: MUTED";
    appendTerminal("[AUDIO] Voice synthesizer muted.");
  }
});


function terapkanPerintahKecepatan(val) {
  const rendah = (val || "").toLowerCase();
  let target = null;
  if (
    rendah.includes("bicara lebih cepat") ||
    rendah.includes("speak faster") ||
    rendah.includes("talk faster")
  ) {
    target = Math.min(1.8, ARVI_SPEECH_RATE + 0.15);
  } else if (
    rendah.includes("bicara lebih pelan") ||
    rendah.includes("bicara lebih lambat") ||
    rendah.includes("speak slower") ||
    rendah.includes("talk slower")
  ) {
    target = Math.max(0.6, ARVI_SPEECH_RATE - 0.15);
  } else if (
    rendah.includes("normalkan kecepatan suara") ||
    rendah.includes("normalkan kecepatan") ||
    rendah.includes("normal speech rate") ||
    rendah.includes("reset speech rate")
  ) {
    target = 1.0;
  }
  if (target === null) return false;
  ARVI_SPEECH_RATE = Math.round(target * 100) / 100;
  if (currentArviAudio) {
    try {
      currentArviAudio.playbackRate = ARVI_SPEECH_RATE;
    } catch (err) {

    }
  }
  appendTerminal(`[AUDIO] Speech rate → ${ARVI_SPEECH_RATE.toFixed(2)}.`);
  const pakaiInggris = /speak|talk|faster|slower|normal|reset|rate/i.test(val);
  speakArvi(
    pakaiInggris
      ? `Okay, my speech rate is now ${ARVI_SPEECH_RATE.toFixed(2)}.`
      : `Siap, kecepatan bicaraku sekarang ${ARVI_SPEECH_RATE.toFixed(2)}.`,
  );
  return true;
}


const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;


function normalisasiNamaArvi(teks) {
  if (!teks) return teks;
  let hasil = String(teks);

  hasil = hasil.replace(
    /\b(hai|halo|hei|hello|oi|tolong|coba)\s+arti\b/gi,
    "$1 Arvi",
  );

  hasil = hasil.replace(/(^|[.!?]\s+)(arti)(?=[,\s]|$)/gim, "$1Arvi");

  return hasil.replace(
    /\b(arfi|arbi|alfi|arvy|harfi|arvie|rv|arvee|arpi|arwi|harvi)\b/gi,
    "Arvi",
  );
}


const PESAN_ULANGI_ARVI =
  "Maaf, perintahnya belum tertangkap. Ulangi dengan awalan Arvi.";
const ALIAS_AWALAN_SUARA = ["avi", "awi", "ari"];
const ISI_TAK_JELAS_SUARA = ["eh", "anu", "hmm", "mmm", "ehm", "heh"];

function kataPertamaSuara(rendah) {
  const cocok = String(rendah || "").match(/[a-z]+/);
  return cocok ? cocok[0] : "";
}

function saringTranskripSuara(transkrip, final = true) {
  if (!final) return null;
  const mentah = String(transkrip || "").trim();
  if (!mentah) return null;
  const normal = normalisasiNamaArvi(mentah);
  let sisa;
  if (kataPertamaSuara(normal.toLowerCase()) === "arvi") {
    sisa = normal.replace(/^[^a-zA-Z]*arvi\b/i, "");
  } else if (ALIAS_AWALAN_SUARA.includes(kataPertamaSuara(mentah.toLowerCase()))) {
    sisa = mentah.replace(/^[^a-zA-Z]*[a-zA-Z]+/, "");
  } else {
    return null;
  }
  sisa = sisa.trim().replace(/^[,.:;!?\-–— ]+/, "").trim();
  if (!/[a-zA-Z0-9]/.test(sisa)) return { takJelas: true };
  if (ISI_TAK_JELAS_SUARA.includes(sisa.toLowerCase())) return { takJelas: true };
  return { perintah: mentah, sisa };
}


function kirimTranskripKeForm(transcript) {
  transcript = normalisasiNamaArvi(transcript);
  if (isEchoFromArvi(transcript)) {
    appendTerminal("[ECHO IGNORED] Ignoring ARVI's own voice echo.");
    return;
  }
  const putusan = saringTranskripSuara(transcript, true);
  if (!putusan) {
    appendTerminal("[VOICE IGNORED] Transcript without Arvi prefix — dropped.");
    return;
  }
  if (putusan.takJelas) {
    appendDialogue("ARVI CORE // MUSE SPARK", PESAN_ULANGI_ARVI, "arvi");
    speakArvi(PESAN_ULANGI_ARVI);
    return;
  }
  appendTerminal(`[STT CAPTURED] "${transcript}"`);
  transkripSuaraBerikutnya = true;
  const input = document.getElementById("cmd-input");
  input.value = transcript;
  document
    .getElementById("command-form")
    .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "id-ID";


  recognition.continuous = true;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isListening = true;
    setBaymaxState("listening");
    const micBtn = document.getElementById("btn-mic");
    micBtn.className =
      "w-9 h-9 flex-shrink-0 rounded-full bg-rose-500 text-white text-sm transition flex items-center justify-center animate-pulse";
    document.getElementById("mic-label").textContent = "...";
    document.getElementById("core-state").textContent = "VOICE INPUT CAPTURE";
    appendTerminal("[AUDIO] Microphone open. Speak command to ARVI...");
  };

  recognition.onresult = (event) => {
    let finalText = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const res = event.results[i];
      if (res.isFinal) finalText += res[0].transcript;
    }
    if (!finalText.trim()) return;
    micGagalJaringan = 0;
    const teks = finalText.trim();


    if (isSpeaking) {
      if (isEchoFromArvi(normalisasiNamaArvi(teks))) return;
      const putusan = saringTranskripSuara(teks, true);
      if (!putusan || putusan.takJelas) return;
      if (/^(stop|berhenti|cukup|diam|tahan)\b/i.test(putusan.sisa)) {
        appendTerminal(`[BARGE-IN] Interrupt: "${teks}"`);
        hentikanSuaraArvi(true);
      }
      return;
    }
    kirimTranskripKeForm(teks);
  };

  recognition.onerror = (event) => {


    if (event.error === "no-speech" || event.error === "aborted") return;

    if (
      event.error === "network" &&
      handsFreeMode &&
      isAuthenticated &&
      recognition &&
      micGagalJaringan < 5
    ) {
      micGagalJaringan += 1;
      appendTerminal(
        `[AUDIO WARN] Mic network error — silent retry ${micGagalJaringan}/5...`,
      );
      setTimeout(() => {


        if (handsFreeMode && isAuthenticated && !isListening) {
          try {
            recognition.start();
          } catch (e) {

          }
        }
      }, 5000);
      return;
    }
    console.warn("Speech recognition error:", event.error);
    appendTerminal(`[AUDIO ERROR] Voice capture: ${event.error}`);
    resetMicUI();
  };

  recognition.onend = () => {
    resetMicUI();

    if (hentiMicDisengaja) {
      hentiMicDisengaja = false;
      return;
    }


    if (isAuthenticated && recognition) {
      setTimeout(() => {
        const pttTertahan =
          pttBrowserAktif || micTekanMulai > 0 || pttServerAktif;
        if (
          (handsFreeMode || pttTertahan) &&
          isAuthenticated &&
          !isListening
        ) {
          try {
            recognition.start();
          } catch (e) {

          }
        }
      }, 150);
    }
  };
} else {
  appendTerminal(
    "[AUDIO WARN] Web Speech Recognition not supported in this browser.",
  );
}

function resetMicUI() {
  isListening = false;
  const micBtn = document.getElementById("btn-mic");
  micBtn.className =
    "w-9 h-9 flex-shrink-0 rounded-full bg-slate-700 hover:bg-slate-600 text-white text-sm transition flex items-center justify-center";
  document.getElementById("mic-label").textContent = handsFreeMode
    ? "🎙"
    : "🔇";
  if (!isSpeaking) {
    setBaymaxState("idle");
    document.getElementById("core-state").textContent = handsFreeMode
      ? "ARVI LISTENING"
      : "ARVI STANDBY";
  } else {
    setBaymaxState("speaking");
  }
}


let micTekanMulai = 0;
let abaikanKlikMic = false;
let terakhirSentuhMic = 0;


function perbaruiTampilanModeMic() {
  const modeBtn = document.getElementById("btn-mic-mode");
  const pttBtn = document.getElementById("btn-ptt");
  if (modeBtn) {
    modeBtn.textContent = handsFreeMode ? "AUTO: ON" : "AUTO: OFF";
    modeBtn.className = handsFreeMode
      ? "flex-shrink-0 px-2.5 py-1 bg-emerald-500 hover:bg-emerald-600 text-white text-[11px] font-semibold rounded-full transition mono"
      : "flex-shrink-0 px-2.5 py-1 bg-slate-300 hover:bg-slate-400 text-slate-600 text-[11px] font-semibold rounded-full transition mono";
  }
  if (pttBtn) {
    if (handsFreeMode) pttBtn.classList.add("hidden");
    else pttBtn.classList.remove("hidden");
  }
  document.getElementById("mic-label").textContent = handsFreeMode
    ? "🎙"
    : "🔇";
}

function setHandsFreeMode(aktif) {
  handsFreeMode = aktif;
  perbaruiTampilanModeMic();
  if (handsFreeMode) {
    appendTerminal(
      "[AUDIO] Hands-free ON. Microphone always-on — start commands with Arvi.",
    );


    if (isAuthenticated && !isListening && recognition) {
      try {
        recognition.start();
      } catch (err) {
        appendTerminal(`[AUDIO WARN] Failed to start the mic: ${err.message}`);
      }
    }
  } else {
    appendTerminal("[AUDIO] Hands-free OFF. Microphone standby.");
    hentikanMicDisengaja();
  }
}


document.getElementById("btn-mic").addEventListener("click", () => {
  if (abaikanKlikMic) {
    abaikanKlikMic = false;
    return;
  }
  if (!recognition) {
    alert(
      "Your browser does not support Web Speech Recognition yet. Use Google Chrome or Microsoft Edge.",
    );
    return;
  }

  setHandsFreeMode(!handsFreeMode);
});

document.getElementById("btn-mic-mode").addEventListener("click", () => {
  if (!recognition) {
    alert(
      "Your browser does not support Web Speech Recognition yet. Use Google Chrome or Microsoft Edge.",
    );
    return;
  }
  setHandsFreeMode(!handsFreeMode);
});


(function pasangPushToTalk() {
  const tombolMic = document.getElementById("btn-mic");
  const tombolPtt = document.getElementById("btn-ptt");
  const tombolAktif = [tombolMic, tombolPtt].filter(Boolean);
  if (!tombolAktif.length) return;
  const tekanMulai = (e) => {
    if (handsFreeMode || !recognition || !isAuthenticated) return;
    if (e && e.type === "mousedown" && Date.now() - terakhirSentuhMic < 800) {
      return;
    }
    if (e && e.type === "touchstart") terakhirSentuhMic = Date.now();
    micTekanMulai = Date.now();
    abaikanKlikMic = false;
    appendTerminal("[PTT] Mic held — listening...");
    try {
      recognition.start();
    } catch (err) {

    }
  };
  const tekanSelesai = (e) => {
    if (handsFreeMode || !recognition) return;
    if (e && e.type === "mouseup" && Date.now() - terakhirSentuhMic < 800) {
      return;
    }
    hentikanMicDisengaja();
    appendTerminal("[PTT] Mic released — sending.");
    if (micTekanMulai > 0 && Date.now() - micTekanMulai >= 250) {
      abaikanKlikMic = true;
    }
    micTekanMulai = 0;
  };
  tombolAktif.forEach((tombol) => {
    tombol.addEventListener("mousedown", tekanMulai);
    tombol.addEventListener("mouseup", tekanSelesai);
    tombol.addEventListener("touchstart", tekanMulai, { passive: true });
    tombol.addEventListener("touchend", tekanSelesai);
  });
})();


let pttBrowserAktif = false;
window.addEventListener("keydown", (e) => {
  if (!e.ctrlKey || !e.altKey) return;
  if (e.repeat || pttBrowserAktif) return;
  if (!recognition || !isAuthenticated) return;
  pttBrowserAktif = true;
  appendTerminal("[PTT] Ctrl+Alt (browser) — listening...");
  hentikanSuaraArvi(true);
  try {
    recognition.start();
  } catch (err) {

  }
});
window.addEventListener("keyup", (e) => {
  if (!pttBrowserAktif) return;
  if (e.ctrlKey && e.altKey) return;
  pttBrowserAktif = false;
  appendTerminal("[PTT] Ctrl+Alt released — sending.");
  hentikanMicDisengaja();
});


const video = document.getElementById("webcam-feed");
const spatialCanvas = document.getElementById("spatial-canvas");
const sCtx = spatialCanvas.getContext("2d");
let scanY = 0;
let scanDirection = 1;

let activeSamData = null;


async function mulaiPreviewKamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    appendTerminal(
      "[OPTICAL WARN] Live preview needs HTTPS or http://localhost/127.0.0.1.",
    );
    return false;
  }
  if (video.srcObject) {
    try {
      await video.play();
    } catch (err) {

    }
    return true;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false,
    });
    video.muted = true;
    video.srcObject = stream;
    try {
      await video.play();
    } catch (err) {

    }
    return true;
  } catch (err) {
    appendTerminal(
      `[OPTICAL WARN] Live preview failed: ${(err && err.name) || "Denied"}`,
    );
    return false;
  }
}

function hentikanKamera() {
  try {
    const stream = video.srcObject;
    if (stream) {
      stream.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch (err) {

        }
      });
    }
  } catch (err) {

  }
  video.srcObject = null;
}

function tungguVideoSiap(batasMs) {
  return new Promise((resolve, reject) => {
    if (video.readyState >= 2 && video.videoWidth > 0) {
      resolve();
      return;
    }
    const timer = setTimeout(() => {
      video.removeEventListener("canplay", saatSiap);
      reject(new Error("timeout waiting for the camera frame"));
    }, batasMs || 4000);
    function saatSiap() {
      clearTimeout(timer);
      resolve();
    }
    video.addEventListener("canplay", saatSiap, { once: true });
  });
}


async function ambilFrameSekaliPakai() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    appendTerminal(
      "[OPTICAL WARN] Camera requires HTTPS or http://localhost/127.0.0.1 origin.",
    );
    return null;
  }
  const pakaiPratinjau = !!(video.srcObject && video.videoWidth > 0);
  let stream = null;
  try {
    if (pakaiPratinjau) {
      await tungguVideoSiap(1500);
    } else {
      hentikanKamera();
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      video.muted = true;
      video.srcObject = stream;
      try {
        await video.play();
      } catch (err) {

      }
      await tungguVideoSiap(4000);
    }
    const captureCanvas = document.createElement("canvas");
    captureCanvas.width = 320;
    captureCanvas.height = 240;
    const ctx = captureCanvas.getContext("2d");
    ctx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
    const dataUrl = captureCanvas.toDataURL("image/jpeg", 0.7);

    const bukti = document.getElementById("grounding-img");
    if (bukti) {
      bukti.src = dataUrl;
      bukti.classList.remove("hidden");
    }
    return dataUrl;
  } catch (err) {
    console.warn("Webcam access error:", err);
    appendTerminal(
      `[OPTICAL WARN] Camera access: ${(err && err.name) || "Denied"}`,
    );
    return null;
  } finally {

    if (!pakaiPratinjau) {
      try {
        if (stream) {
          stream.getTracks().forEach((track) => {
            try {
              track.stop();
            } catch (err) {

            }
          });
        }
      } catch (err) {

      }
      if (video.srcObject === stream) video.srcObject = null;
    }
  }
}

function resizeSpatialCanvas() {
  if (spatialCanvas.parentElement) {
    spatialCanvas.width = spatialCanvas.parentElement.clientWidth;
    spatialCanvas.height = spatialCanvas.parentElement.clientHeight;
  }
}
window.addEventListener("resize", resizeSpatialCanvas);
resizeSpatialCanvas();
setTimeout(resizeSpatialCanvas, 200);

function renderSpatialOverlay() {
  if (spatialCanvas.width === 0 || spatialCanvas.height === 0) {
    requestAnimationFrame(renderSpatialOverlay);
    return;
  }
  sCtx.clearRect(0, 0, spatialCanvas.width, spatialCanvas.height);
  const w = spatialCanvas.width;
  const h = spatialCanvas.height;


  sCtx.strokeStyle = "rgba(14, 165, 233, 0.4)";
  sCtx.lineWidth = 1;
  sCtx.beginPath();
  sCtx.moveTo(w / 2 - 15, h / 2);
  sCtx.lineTo(w / 2 + 15, h / 2);
  sCtx.moveTo(w / 2, h / 2 - 15);
  sCtx.lineTo(w / 2, h / 2 + 15);
  sCtx.stroke();


  const boxW = w * 0.6;
  const boxH = h * 0.6;
  const boxX = (w - boxW) / 2;
  const boxY = (h - boxH) / 2;

  sCtx.strokeStyle = "#00f0ff";
  sCtx.lineWidth = 2;
  const cl = 12;

  sCtx.beginPath();
  sCtx.moveTo(boxX, boxY + cl);
  sCtx.lineTo(boxX, boxY);
  sCtx.lineTo(boxX + cl, boxY);
  sCtx.stroke();
  sCtx.beginPath();
  sCtx.moveTo(boxX + boxW - cl, boxY);
  sCtx.lineTo(boxX + boxW, boxY);
  sCtx.lineTo(boxX + boxW, boxY + cl);
  sCtx.stroke();
  sCtx.beginPath();
  sCtx.moveTo(boxX, boxY + boxH - cl);
  sCtx.lineTo(boxX, boxY + boxH);
  sCtx.lineTo(boxX + cl, boxY + boxH);
  sCtx.stroke();
  sCtx.beginPath();
  sCtx.moveTo(boxX + boxW - cl, boxY + boxH);
  sCtx.lineTo(boxX + boxW, boxY + boxH);
  sCtx.lineTo(boxX + boxW, boxY + boxH - cl);
  sCtx.stroke();


  sCtx.strokeStyle = "rgba(0, 240, 255, 0.8)";
  sCtx.lineWidth = 1.5;
  sCtx.beginPath();
  sCtx.moveTo(boxX, boxY + scanY);
  sCtx.lineTo(boxX + boxW, boxY + scanY);
  sCtx.stroke();

  scanY += 1.8 * scanDirection;
  if (scanY > boxH || scanY < 0) scanDirection *= -1;


  if (
    activeSamData &&
    activeSamData.polygons &&
    activeSamData.polygons.length > 0
  ) {
    sCtx.fillStyle = "rgba(0, 240, 255, 0.18)";
    sCtx.strokeStyle = "#00f0ff";
    sCtx.lineWidth = 1.5;
    for (const poli of activeSamData.polygons) {
      if (!poli || poli.length < 3) continue;
      sCtx.beginPath();
      sCtx.moveTo(poli[0][0] * w, poli[0][1] * h);
      for (let i = 1; i < poli.length; i++) {
        sCtx.lineTo(poli[i][0] * w, poli[i][1] * h);
      }
      sCtx.closePath();
      sCtx.fill();
      sCtx.stroke();
    }
  }

  sCtx.fillStyle = "#38bdf8";
  sCtx.font = "9px monospace";
  sCtx.fillText(
    "SAM 3.1 // ZERO-SHOT TARGETING",
    boxX + 4,
    Math.max(boxY - 6, 10),
  );

  requestAnimationFrame(renderSpatialOverlay);
}

async function triggerOpticalScan(
  customPrompt = "Identify the object, face, or hardware in front of this camera technically and briefly.",
  dariSuara = false,
) {
  activeSamData = null;
  document.getElementById("detected-tag").textContent = "OPENING CAMERA...";
  document.getElementById("mask-status").textContent = "Waiting for frame...";


  const base64Image = await ambilFrameSekaliPakai();
  if (!base64Image) {
    document.getElementById("detected-tag").textContent = "CAMERA OFF";
    document.getElementById("mask-status").textContent = "Capture cancelled.";
    appendTerminal("[OPTICAL] Capture cancelled; camera off.");
    tutupPanelVision(5000);
    return;
  }

  appendTerminal(
    "[SAM 3.1] Optical frame captured (320x240). Dispatching to Baseten Vision...",
  );
  document.getElementById("detected-tag").textContent = "ANALYZING FRAME...";
  document.getElementById("mask-status").textContent =
    "Processing Vision Tokens...";

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        type: "vision_scan",
        image: base64Image,
        prompt: customPrompt,
        ...(dariSuara ? { sumber: "suara", final: true } : {}),
      }),
    );
  } else {
    appendTerminal("[WARN] Server is not connected for Vision analysis.");
    tutupPanelVision(5000);
  }
}

document.getElementById("btn-scan").addEventListener("click", () => {
  bukaPanelVision();
  triggerOpticalScan();
});


function initPanelButtons() {
  const wiring = [
    ["btn-open-vision", () => bukaPanelVision()],
    ["btn-close-vision", () => tutupPanelVision()],
    ["btn-open-workspace", () => bukaPanelWorkspace()],
    ["btn-close-workspace", () => tutupPanelWorkspace()],
    ["btn-vision-laptop", () => pilihKameraLaptop()],
    ["btn-vision-hp", () => pilihKameraHp()],
    ["btn-close-qr", () => bersihkanQrMobile()],
    ["btn-header-qr", () => toggleQrMobileLens()],
    ["btn-close-cyber", () => tutupModal("modal-cyber")],
    ["btn-close-appsec", () => tutupModal("modal-appsec")],
    ["btn-close-news", () => tutupModal("modal-news")],
  ];
  wiring.forEach(([id, fn]) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("click", fn);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") tutupSemuaModal();
  });
}


function setLockMsg(teks, tone) {
  const el = document.getElementById("lockscreen-msg");
  el.textContent = teks;
  el.className =
    "text-xs min-h-8 text-center " +
    (tone === "ok"
      ? "text-emerald-600"
      : tone === "err"
        ? "text-rose-600"
        : "text-slate-500");
}

function setLockscreenStatus(teks, tone) {
  const el = document.getElementById("lockscreen-status");
  el.textContent = teks;
  el.className =
    "inline-block mt-2 text-[10px] px-2 py-1 rounded-full font-bold border mono " +
    (tone === "ok"
      ? "bg-emerald-50 border-emerald-200 text-emerald-600"
      : tone === "err"
        ? "bg-rose-50 border-rose-200 text-rose-600"
        : tone === "busy"
          ? "bg-slate-100 border-slate-300 text-slate-600"
          : "bg-slate-100 border-slate-200 text-slate-500");
}

function setTombolAuth(nonaktif) {
  ["btn-login", "btn-setup-password"].forEach((id) => {
    const b = document.getElementById(id);
    if (b) b.disabled = nonaktif;
  });
}

function tampilkanLockscreen(pesan) {
  document.getElementById("lockscreen").style.display = "flex";
  if (pesan) setLockMsg(pesan, "");
}

function sembunyikanLockscreen() {
  document.getElementById("lockscreen").style.display = "none";
}

function kunciHud(pesan) {
  isAuthenticated = false;
  arviToken = null;
  try {
    sessionStorage.removeItem("arvi_token");
  } catch (err) {

  }
  hentikanTelemetriLive();

  hentikanMicDisengaja();
  tutupPanelVision();
  tutupPanelWorkspace();
  hentikanKamera();
  sembunyikanPilihanKamera();
  bersihkanQrMobile();
  setBaymaxState("idle");
  setLabelLatency("-- // LOCKED", false);
  setLabelNodes(null);
  try {
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  } catch (err) {

  }
  setTombolAuth(false);
  tampilkanLockscreen(pesan || "HUD is locked.");
}

async function apiJson(path, opsi) {
  const gabung = Object.assign({}, opsi || {});
  if (arviToken) {
    gabung.headers = Object.assign({}, gabung.headers || {}, {
      Authorization: `Bearer ${arviToken}`,
    });
  }
  const res = await fetch(API_BASE + path, gabung);
  let data = null;
  try {
    data = await res.json();
  } catch (err) {
    data = null;
  }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : null;
    const pesan =
      (detail && (detail.pesan || detail.alasan || detail.status)) ||
      (typeof detail === "string" ? detail : null) ||
      `HTTP ${res.status}`;

    const metrik = detail && detail.metrik ? detail.metrik : null;
    if (metrik && typeof metrik === "object") {
      const ringkas = ["skor_min", "gerak_maks_px", "jarak_maks_embed"]
        .filter((k) => metrik[k] !== undefined)
        .map((k) => `${k} ${metrik[k]}`)
        .join(", ");
      throw new Error(ringkas ? `${pesan} (${ringkas})` : pesan);
    }
    throw new Error(pesan);
  }
  return data;
}

async function ambilStatusAuth() {
  setLockscreenStatus("CHECKING...", "busy");
  try {
    const s = await apiJson("/auth/status");
    document.getElementById("lockscreen-operator").textContent = "—";
    if (s.butuh_setup) {
      tampilkanViewAuth("setup");
      setLockscreenStatus("SETUP", "");
      setLockMsg("No account yet. Create the first (owner) account below.", "");
      return;
    }
    tampilkanViewAuth("login");
    setLockscreenStatus("READY", "ok");
    setLockMsg("ARVI Core ready. Enter username + password.", "");
  } catch (err) {
    setLockscreenStatus("OFFLINE", "err");
    setLockMsg(
      `Server unreachable (${err.message}). Run python server/main.py, then REFRESH STATUS.`,
      "err",
    );
  }
}

function tampilkanViewAuth(nama) {
  document.getElementById("view-login").style.display =
    nama === "setup" ? "none" : "flex";
  document.getElementById("view-setup").style.display =
    nama === "setup" ? "flex" : "none";
}

async function loginPassword() {
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  if (!username || !password) {
    setLockMsg("Fill in username and password first.", "err");
    return;
  }
  setTombolAuth(true);
  setLockscreenStatus("LOGIN...", "busy");
  try {
    const data = await apiJson("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    document.getElementById("login-password").value = "";
    otentikasiBerhasil(data.token, data.pemilik, "password");
  } catch (err) {
    setLockscreenStatus("READY", "");
    setLockMsg(`Login failed: ${err.message}`, "err");
    appendTerminal(`[AUTH FAILED] Password login: ${err.message}`);
    setTombolAuth(false);
  }
}

async function setupPassword() {
  const username = document.getElementById("setup-username").value.trim();
  const sandi = document.getElementById("setup-password").value;
  const sandi2 = document.getElementById("setup-password2").value;
  if (!username || !sandi) {
    setLockMsg("Fill in username and password first.", "err");
    return;
  }
  if (sandi !== sandi2) {
    setLockMsg("Repeated password does not match.", "err");
    return;
  }
  setTombolAuth(true);
  setLockscreenStatus("SETUP...", "busy");
  try {
    const data = await apiJson("/auth/setup/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password: sandi }),
    });
    document.getElementById("setup-password").value = "";
    document.getElementById("setup-password2").value = "";
    tampilkanViewAuth("login");
    otentikasiBerhasil(data.token, data.pemilik, "setup-password");
  } catch (err) {
    setLockscreenStatus("SETUP", "");
    setLockMsg(`Setup failed: ${err.message}`, "err");
    appendTerminal(`[SETUP FAILED] ${err.message}`);
    setTombolAuth(false);
  }
}

function otentikasiBerhasil(token, pemilik, metode) {
  arviToken = token;
  try {
    sessionStorage.setItem("arvi_token", token);
  } catch (err) {

  }
  document.getElementById("lockscreen-operator").textContent = pemilik || "—";
  setLockscreenStatus("AUTH OK", "ok");
  setLockMsg(`Passed via ${metode}. Opening the WebSocket channel...`, "ok");
  appendTerminal(`[AUTH] ${metode} token accepted. Opening WebSocket...`);
  connectWebSocket();
}


function setLabelLatency(teks, live) {
  const el = document.getElementById("core-latency");
  el.textContent = `LATENCY: ${teks}`;
  el.className =
    "text-[11px] mono " + (live ? "text-slate-600" : "text-slate-400");
}

function setLabelNodes(nodeAktif) {
  const el = document.getElementById("active-nodes-count");
  if (nodeAktif === null || nodeAktif === undefined) {
    el.textContent = "STANDBY // LOCKED";
    el.className = "text-slate-500 font-semibold mono";
    return;
  }
  el.textContent =
    nodeAktif === 1 ? "1 ONLINE (LAPTOP_01)" : `${nodeAktif} ONLINE`;
  el.className = "text-slate-700 font-semibold mono";
}

function kirimPing() {
  if (!isAuthenticated || !ws || ws.readyState !== WebSocket.OPEN) return;
  try {
    lastPingSentAt = performance.now();
    ws.send(JSON.stringify({ type: "ping", t: Date.now() }));
  } catch (err) {

  }
}

async function muatStats() {
  if (!isAuthenticated) return;
  try {
    const s = await apiJson("/api/stats");
    setLabelNodes(s.node_aktif);
  } catch (err) {

  }
}

function mulaiTelemetriLive() {
  hentikanTelemetriLive();
  kirimPing();
  muatStats();
  pingTimer = setInterval(kirimPing, 5000);
  statsTimer = setInterval(muatStats, 5000);
}

function hentikanTelemetriLive() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
  if (statsTimer) {
    clearInterval(statsTimer);
    statsTimer = null;
  }
  lastPingSentAt = 0;
}

function initLockscreen() {
  document.getElementById("btn-login").addEventListener("click", loginPassword);
  document
    .getElementById("btn-setup-password")
    .addEventListener("click", setupPassword);
  document.getElementById("login-password").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loginPassword();
  });
  document
    .getElementById("setup-password2")
    .addEventListener("keydown", (e) => {
      if (e.key === "Enter") setupPassword();
    });
  document
    .getElementById("btn-lock-refresh")
    .addEventListener("click", ambilStatusAuth);
  document
    .getElementById("btn-lock")
    .addEventListener("click", () => kunciHud("HUD locked by operator."));


  try {
    const tersimpan = sessionStorage.getItem("arvi_token");
    if (tersimpan) {
      arviToken = tersimpan;
      setLockMsg("Restoring saved session...", "");
    }
  } catch (err) {

  }

  ambilStatusAuth();
  if (arviToken) connectWebSocket();
}


hentikanKamera();
renderSpatialOverlay();
initPanelButtons();
perbaruiTampilanModeMic();
initLockscreen();


const OS_KATA_BUKA = [
  "bukakan",
  "dibuka",
  "buka",
  "jalankan",
  "jalani",
  "open",
  "launch",
  "start",
  "nyalakan",
  "run",
];
const OS_KATA_TUTUP = [
  "tutupi",
  "ditutup",
  "tutup",
  "close",
  "matikan",
  "kill",
  "hentikan",
  "exit",
  "quit",
];

const OS_TARGET_ALIAS = [
  ["notepad", "note pad", "catatan"],
  ["kalkulator", "calculator", "kalkulasi", "calc"],
  ["chrome", "google chrome", "browser"],
  ["edge", "microsoft edge"],
  ["explorer", "file explorer", "eksplorer", "file manager", "folder"],
  ["cmd", "command prompt", "terminal", "konsol"],
  ["powershell", "power shell"],
  ["task manager", "taskmanager", "manajer tugas"],
  ["pengaturan", "settings", "setting"],
  ["paint", "mspaint"],
  ["snipping", "snipping tool", "screenshot", "tangkapan layar"],
  ["vscode", "visual studio code", "vs code", "editor", "code"],
  ["word", "microsoft word", "ms word"],
  ["excel", "microsoft excel", "ms excel"],
  ["powerpoint", "power point", "ppt", "presentasi", "ms powerpoint"],
  ["spotify"],
];

function kataUtuhAda(rendah, kata) {

  const polos = kata.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^a-z])${polos}([^a-z]|$)`, "i").test(rendah);
}


const KATA_KERJA_NORMAL = [
  "bukakan",
  "dibuka",
  "buka",
  "tutupi",
  "ditutup",
  "tutup",
  "jalankan",
  "jalani",
  "matikan",
  "hentikan",
  "arahkan",
  "pindahkan",
  "geser",
  "carikan",
  "cari",
  "ketikkan",
  "ketik",
  "tuliskan",
  "tulis",
  "klik",
  "tekan",
  "pencet",
  "baca",
  "lihat",
  "tampilkan",
];

function normalisasiKataPerintah(teks) {
  if (!teks) return teks;
  let hasil = String(teks);
  for (const kata of KATA_KERJA_NORMAL) {
    const pola = new RegExp(
      "(?<![a-z])" + kata.split("").join("+") + "+(?![a-z])",
      "gi",
    );
    hasil = hasil.replace(pola, kata);
  }
  return hasil;
}

function deteksiPerintahOS(teksMentah) {
  const rendah = ` ${normalisasiKataPerintah(teksMentah || "")
    .toLowerCase()
    .trim()} `;
  if (!rendah.trim()) return null;


  if (
    /\b(tab|halaman|page|cari|search|akun|account|profil|profile|youtube|yt|gmail|facebook|instagram|linkedin|github|whatsapp|drive|chatgpt|gemini|elevenlabs|situs|website|web|site)\b/i.test(
      rendah,
    )
  )
    return null;


  if (
    /\b(pause|play|resume|jeda|lanjutkan|next|skip|previous|sebelumnya|selanjutnya|putar|hentikan|stop|volume|mute|unmute|minimize|maximize|lock)\b/i.test(
      rendah,
    )
  )
    return null;
  let aksi = null;
  if (OS_KATA_TUTUP.some((k) => kataUtuhAda(rendah, k))) aksi = "tutup";
  else if (OS_KATA_BUKA.some((k) => kataUtuhAda(rendah, k))) aksi = "buka";
  if (!aksi) return null;
  for (const [kanonis, ...alias] of OS_TARGET_ALIAS) {
    const semua = [kanonis, ...alias].sort((a, b) => b.length - a.length);

    if (semua.some((a) => kataUtuhAda(rendah, a))) {
      return { aksi, target: kanonis };
    }
  }
  return null;
}
