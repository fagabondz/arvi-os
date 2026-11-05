# ARVI OS TECHNICAL DOCUMENT — A Rather Virtual Intelligence

> Status: actively developed · English UI, bilingual EN/ID commands · Platform: Windows + browser · 100% Meta stack
> This document is the complete technical reference: architecture, modules,
> protocols, APIs, data flows, security, and operations. See also
> `STRUKTUR_PROYEK.md` (file map) and `README.md` (quickstart).

---

## 1. System Summary

ARVI OS is a voice + text Windows operator driven through a browser HUD.
The user speaks/types commands → the HUD sends them to the FastAPI server
→ the server executes via deterministic fast-paths (app control, media,
windows, mouse/keyboard, screen read/click) or forwards them to the Meta
engines (Muse Spark 1.3, Baseten Muse Spark Open 1026) → responses are
read aloud via ElevenLabs TTS and shown in the HUD. Audit-grade results
(network, AppSec, news) render in overlay dashboard modals; chat stays short.

Core capabilities:

- **Full Windows OS control**: open/close apps (whitelist), play/pause /
  next/prev Spotify & media, volume, mute, minimize/maximize, screen lock,
  screenshots — from the laptop or the phone.
- **Mouse & keyboard**: type text, press keys, hotkeys, move/click/scroll mouse.
- **Screen Vision + auto-click**: read the monitor and click on-screen
  elements via Baseten Vision (percent → pixel coordinates).
- **Camera**: scan objects via the laptop webcam or the phone camera (Mobile
  Lens); follow-up visual questions reuse the last frame (25 seconds).
- **Memory**: 20-message STM + permanent LTM (`profil_user`, facts, summary).
- **Autonomous agent**: multi-action commands ("open notepad then type X")
  split by Muse into execution steps.
- **Voice**: Web Speech STT (hands-free/PTT), ElevenLabs TTS + browser
  fallback, transcript-level echo filter, prefixed barge-in "Arvi stop".
- **Security**: username + password Login Gate → 8-hour HMAC session token;
  mobile/TTS endpoints need a session or phone QR token; `/ws/node`
  needs a PSK; telemetry is sanitized before entering LLM context.
- **Proactive**: scheduled reminders ("remind me … in 30 minutes"),
  automatic morning briefing, and a CPU monitor (alerts above 80% for
  10 minutes).
- **Cyber-agent**: visible CMD network audit (ping/tracert/netstat) +
  live-connection SOC audit, AppSec screen audit, AI-vs-real photo
  forensics, QR SOC check, clipboard audit, emergency lockdown.
- **News**: today's headlines (world/Indonesia) from public RSS with a
  Meta summary + a HUD card gallery.
- **Bilingual EN/ID**: English UI and logs; every command parser
  (OS, media, browser, screen, reminders) understands English and Indonesian.

---

## 2. Architecture

```text
┌──────────────┐  WebSocket /ws/hud   ┌─────────────────────────────┐
│  Laptop HUD  │◄────────────────────►│   server/* (modular)      │
│ index.html   │  + REST /api/*       │   main.py = slim router   │
│ app.js       │                      │   FastAPI :8080             │
└──────────────┘                      │  ┌───────────────────────┐  │
┌──────────────┐  REST (photo/text)   │  │ Deterministic fast-   │  │
│ Mobile Lens  │─────────────────────►│  │ paths: lockdown,      │  │
│ phone (QR)   │◄── voice (TTS mp3)   │  │ agent, system/media,  │  │
└──────────────┘                      │  │ calibration, cyber,   │  │
┌──────────────┐  WebSocket /ws/node  │  │ screen, in-app, OS,   │  │
│ laptop_node  │◄────────────────────►│  │ input, proactive,     │  │
│ (telemetry)  │  telemetry/action    │  │ news, visual, Muse    │  │
└──────────────┘                      │  └───────────┬───────────┘  │
                                      │  ┌───────────▼───────────┐  │
                                      │  │ Meta: Muse 1.3 +      │  │
                                      │  │ Baseten Open 1026     │  │
                                      │  └───────────┬───────────┘  │
                                      └──────────────┼──────────────┘
                                                     │ HTTPS API
                                      ┌──────────────▼──────────────┐
                                      │ api.meta.ai · Baseten ·     │
                                      │ Meta SAM 3.1 · ElevenLabs   │
                                      └─────────────────────────────┘
```

Server modules: `config` (env/state) → `memory` (STM/LTM + voice gate) →
`ai_engine` (Muse/Baseten + tags + agent) → `vision_engine`
(Vision/SAM/screen/cyber) → `os_control` (Windows + physical audit) →
`voice_engine` (TTS/PTT) → `proactive` (reminders/briefing/CPU) →
`berita` (news) → `kalibrasi_kursor` (calibration) → `mobile_file`
(phone attachments) → `sam31_cloud` (SAM 3.1). `main.py` is only a
REST/WS router + re-export facade so `server.main.*` stays a stable API.

Running processes:

| Process | Command (by the user) | Role |
|---|---|---|
| Core server | `python server/main.py` | HTTP + WS + AI + execution (required) |
| Edge node | `python nodes/laptop_node.py` | CPU/ping telemetry (optional, recommended) |
| HUD | browser → `http://127.0.0.1:8080/` | Main UI (redirects to `/hud/index.html`) |
| Mobile Lens | phone Chrome → QR URL | Camera + commands from the phone |

The server binds `0.0.0.0:8080` (so same-WiFi phones can reach it), reload on.

---

## 3. Technology Stack & Dependencies

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic, `requests` |
| AI | Meta Muse Spark 1.3 (REST), Baseten `meta-models/muse-spark-open-1026` (OpenAI-compat), Meta SAM 3.1 (cloud segmentation) |
| TTS | ElevenLabs SDK (`elevenlabs`) + REST fallback, browser-voice fallback |
| Windows control | `ctypes` Win32 (`keybd_event`, `LockWorkStation`, AppActivate), `pyautogui`, `keyboard`, `psutil`, `PIL` |
| Frontend | Classic HTML + JS (no framework), Tailwind CDN (HUD), Web Speech API, native WebSocket |
| Auth | HMAC-SHA256 (`hashlib`/`hmac`), PBKDF2-SHA256 200,000 iterations |
| Test | `unittest` suite during development (removed for the public push) |

All optional imports are **defensive** (`try/except` + `_X_TERSEDIA` flags):
the server stays alive with the related feature disabled when a library
is missing (`pyautogui`, `psutil`, `keyboard`, ElevenLabs, `PIL.ImageGrab`,
`pyzbar`/`cv2`, `pypdf`).

---

## 4. `server/*` Module Breakdown (12 modules + router)

### 4.1 Global configuration & state (`config.py` + `main.py`)

- `_bersihkan_kunci()`: strips hidden whitespace/quotes from `.env` values.
- Keys: `META_API_KEY`, `BASETEN_API_KEY`, `ELEVENLABS_API_KEY`,
  `ELEVENLABS_VOICE_ID` (default `JBFqnCBsd6RMkjVDRZzb`), `ELEVENLABS_MODEL_ID`
  (default `eleven_v4`). Startup logs print key status + length only
  (never the content).
- Shared state (`config.py`): `hud_clients`, `node_clients`,
  `system_context` (`latest_telemetry`, `top_processes`, `last_ping`),
  `_siar_ke_hud()` broadcast helper.
- Router state (`main.py`): `sesi_ws` (token claims per socket), the `app`
  FastAPI instance, REST + WS endpoints, proactive scheduler, `__main__` block.
- Memory state (`memory.py`): `conversation_history` (STM), `memori_ltm`,
  `last_vision_frame`.

### 4.2 Memory (STM + LTM) — `memory.py`

- **STM**: `conversation_history`, last 20 messages, format
  `{"role": "user"|"assistant", "content": ...}`. Recorded via `_rekam_riwayat()`.
- **LTM** (`server/arvi_memory.json`, git-ignored):
  `profil_user {nama, preferensi, gaya_kerja}`, `fakta_penting[]` (max 100),
  `ringkasan_terakhir`, `interaksi` (counter), reminders, briefing.
- **Explicit remember** (`_simpan_fakta_eksplisit`): triggers "ingat ya…",
  "catat bahwa…", "jangan lupa…", "remember this…", "note that…", plus the
  "namaku X" / "my name is X" pattern → `profil_user.nama`.
- **Background extraction** (`_ekstrak_fakta_latar`): every 10 turns the LLM
  distills facts from history into LTM.
- The persona injects `_blok_memori_untuk_persona()` + `_instruksi_lawan_bicara()`;
  telemetry is injected only when `_butuh_telemetri()` (user asks about the laptop).
- **Voice gate** (`saring_transkrip_suara`): spoken finals must start with
  "Arvi" (or start-only aliases `avi/awi/ari`) or they are dropped before any
  intent/routing/execution; interim results are never executed; "Arvi" + empty
  or filler remainder asks for a repeat. The client `sumber:"suara"` flag is
  UX accident prevention only — the WS session token is the security boundary.

### 4.3 The two Meta engines (`ai_engine.py` + `vision_engine.py`)

| Function | Engine | Model | Used for |
|---|---|---|---|
| `query_arvi_cognitive()` | Baseten → Meta fallback | `muse-spark-open-1026` / `muse-spark-1.3` | Chat + general commands |
| `query_arvi_vision()` | Baseten Vision | `muse-spark-open-1026` | Camera/phone/screen scans, grounding coordinates |
| `extract_baseten_message()` | — | — | Parse Baseten chat-completions responses |
| `segmentasi_sam31()` | Meta SAM 3.1 cloud | `sam-3.1` | Polygon segmentation (priority) + bbox fallback |

Persona: warm like a close friend (not a military robot), never calls the
user "Operator". **LANGUAGE RULE (bilingual, English priority)**: English by
default; fully fluent in English + Indonesian; adapts to Rifan's context
(mixed → natural English/code-switching; full casual Indonesian → Indonesian
+ English tech terms). The persona carries rules for the ARVI name (tolerant
of STT mishearings) and **forbids claiming no access**, plus the
`[EXEC_KEY: …]` tag format (see §4.6).

### 4.4 "Arvi" name normalization (`memory.py`)

`normalisasi_nama_arvi()` (JS mirrors `normalisasiNamaArvi`): fixes
arfi/arbi/alfi/arvy/harfi/arvie/rv/arvee/arpi/arwi/harvi → "Arvi" as whole
words; "arti" only as a greeting ("arti,", "arti …", "hai/halo/hei/hello
arti") so "apa arti kata ini" stays untouched. Applied at every entry point:
`user_command`, `os_command`, `/api/mobile-command`, `/api/mobile-scan`,
`vision_scan`, `/api/mobile-file`.

### 4.5 OS & app control (`os_control.py`)

- `APP_DATABASE`: 18 whitelisted apps (resource monitor, spotify, notepad,
  kalkulator, chrome, edge, explorer, cmd, powershell, task manager
  performance, task manager, pengaturan, paint, snipping, vscode, word,
  excel, powerpoint) + aliases + open/close commands. Spotify alias =
  `["spotify"]` only ("musik"/"lagu" → contextual search).
  Explorer & settings may never be killed.
- `deteksi_intent_os()`: bilingual open/close verbs (`buka/tutup/open/
  launch/close/exit/quit`) as whole words ("bukan" never matches "buka") +
  canonical target. Verified close: `taskkill /F` → psutil check → `/T`
  escalation → "Closed" is claimed only when the process is really dead.
- `execute_os_command()`: open via focus-or-open, close via `taskkill /F`.
  **Strict rule**: running process → just focus it, NEVER Popen
  (avoids the "Who's using Chrome?" dialog).
- Window focus: Win32 `EnumWindows` + `AppActivate` (`_fokus_jendela`),
  process checks via `psutil` (`_proses_berjalan`).
- Spotify: `_perintah_buka_spotify()` (local exe → `spotify:` protocol).
- Web/sites: `WEB_DATABASE` + Chrome bookmark scan (`Default` + `Profile*`)
  via `cari_url_bookmark_chrome()`; open URLs in the active Chrome tab
  (`buka_url_di_chrome_aktif`).
- In-app (`deteksi_intent_aplikasi` + `execute_inapp_command`): new tab/close
  tab, new window, refresh, "cari di google X" / googling, open site/bookmark,
  domain-verified site close, deterministic YouTube composite + contextual play.

### 4.6 Windows system & media control (`os_control.py` + parsers in `ai_engine.py`)

`deteksi_dan_eksekusi_kontrol_sistem(teks, pratinjau=None)` → status string or
`None`. Media keys via `_tekan_vk()` (`ctypes.windll.user32.keybd_event`,
down+up) — **works even with Spotify minimized**:

| Action | Triggers (examples) | Mechanism |
|---|---|---|
| Play/pause | "pause spotify", "play", "resume", "stop music", "hentikan musik" | SMTC state-aware (`_putar_media`/`_jeda_media`); 0xB3 toggle only when needed; strict pure-music phrases only |
| Next / prev | "next song/track", "skip", "lagu berikutnya/sebelumnya", "previous track" | 0xB0 / 0xB1 |
| Volume ∓ | "volume up/down", "increase/decrease volume", "besarkan/kecilkan volume" | 0xAE/0xAF × 5 |
| Mute | "mute/unmute", "bisukan laptop" | 0xAD |
| Desktop | "minimize all", "show desktop", "tampilkan desktop" | hotkey `win+d` |
| Min/max window | "minimize/maximize window", "kecilkan/perbesar jendela" | `win+down` / `win+up` |
| Move monitor | "move window to the right/left monitor", "pindahkan ke monitor" | `win+shift+←/→` |
| Lock screen | "lock screen", "kunci layar" | `LockWorkStation()` |
| Screenshot | "take screenshot", "ambil screenshot", "potret layar" | Save PNG to `Pictures/arvi_screenshot_*` + fill `pratinjau["image"]` |

`_terapkan_exec_key(jawaban)` → `(clean_text, log)`: executes the LLM's
`[EXEC_KEY: play_pause | next_track | prev_track | vol_up | vol_down | mute |
win_d]` tag then strips it. Called at 2 points: the Muse response on the HUD
WS and `/api/mobile-command`.

### 4.7 Mouse & keyboard (`os_control.py`)

`execute_input_command(command, params)`: `type_text` (500-char max),
`press_key` (`_TOMBOL_AMAN` whitelist), `hotkey` (`{"keys"}`/`{"combo"}`,
modifier required, 2–3 keys), `move_mouse` (clamped to screen size),
`click_mouse` (left/right/middle/double), `scroll` (±2000). Bilingual aliases
in `_ALIAS_TOMBOL`. `FailSafeException` handled explicitly.
`deteksi_intent_input()` bilingual: "klik kanan / right click", "ketik / type …",
"tekan / press enter / ctrl+c", "geser / move mouse ke X Y", "scroll ke bawah / down".

### 4.8 Screen Vision & auto-click (`vision_engine.py`)

- `_ambil_screenshot_b64()`: `ImageGrab` → `pyautogui` fallback, proportional
  resize (max width 1280), JPEG q70 → `(data_url, (native_w, native_h))`.
- `lihat_dan_klik_layar(target, pratinjau)`: screenshot → Baseten Vision asks
  for JSON `{"ditemukan", "x_persen", "y_persen"}` → `_koordinat_dari_vision()`
  (0–100 validation) → percent→NATIVE pixels (+ stored calibration) →
  `moveTo` + `click` → optional targeting evidence (red crosshair) to `pratinjau`.
- `baca_layar_monitor(pertanyaan, pratinjau)`: screenshot → Vision → 1–2
  sentence answer + fills `pratinjau {image, target, sumber:"layar"}`.
- `deteksi_intent_layar()` bilingual: "baca" (lihat/read/show/describe/… +
  layar/screen/monitor/display, excluding kamera/camera words), "klik"
  ("pilih/click/select X", "akun/account X"), "buka_dan_klik" ("buka chrome
  pilih akun X" + 2 s sleep).
- Cloud-first segmentation: `jalankan_segmentasi_meta()` tries Meta SAM 3.1
  cloud first (needs `META_API_KEY`), then exactly one Baseten bbox call.
  The `model` field is always honest (`sam-3.1` / `Baseten-BBox`) and shown
  dynamically in the HUD. No local non-Meta models at runtime.
- **Cyber-agent**: `deteksi_intent_forensik()` ("cek foto…", "buatan ai…",
  "is this image ai", …) → `jalankan_forensik_foto_layar()` (photo bbox via
  Open 1026 → PIL auto-crop → Meta forensic verdict; the crop is sent as a
  `grounding_preview`); `deteksi_intent_qr()` ("scan qr", "baca barcode",
  "read qr", …) → `jalankan_soc_qr_layar()` (local multi-scale pyzbar/cv2
  decode — defensive imports, URLs are never opened → Meta SOC verdict +
  URL text in the HUD). Multi-scale decode (1x/1.5x/2x, 1920px); without a
  decoder ARVI honestly asks for `pip install opencv-python`. Both are
  checked by the router before Screen.

### 4.9 Global Ctrl+Alt Push-to-Talk (`voice_engine.py`)

`keyboard` hooks (`_mulai_monitor_ptt`, installed once when the first HUD
authenticates): hold Ctrl+Alt → `_ptt_ditekan("ctrl_alt")` → broadcasts
`ptt_start` once (anti auto-repeat); release either → `_ptt_dilepas` →
`ptt_stop` (only when the source matches). Thread-safe broadcast via
`loop.call_soon_threadsafe`. Bonus: `_set_mute_speaker_windows()` mutes the
physical speaker while PTT is held (paired 0xAD toggle via
`_speaker_diredam_ptt`, restored afterwards).

### 4.10 Muse autonomous agent (`ai_engine.py`)

`deteksi_dan_jalankan_agen_otonom()`: fires when a bilingual conjunction
(`lalu`, `kemudian`, `dan buka`, `then`, `and then`, …) + an action word
are present. `_rencana_agen_muse()` asks the
LLM to split the command → validated JSON array of ≤8 steps
(`_AKSI_AGEN_VALID`). `_jalankan_langkah_agen()` executes:
`buka_app`, `buka_url`, `tab_baru`, `ketik_teks`, `tekan_tombol`,
`klik_layar`, `baca_layar`, `inspect_cpu`, `kontrol_sistem`, `tunggu`.
Progress is broadcast as per-step `agent_log` + a final summary.
Deterministic in-app composites (YouTube open+search+play, site close,
contextual search/play) yield to the in-app handler (no LLM round-trip).

### 4.11 ElevenLabs TTS (`voice_engine.py`)

`sintesis_suara_elevenlabs(teks, voice_id, model_id)` → MP3 bytes: SDK
(`mp3_44100_128`, text ≤2000 chars) → `eleven_multilingual_v2` retry when the
primary model is rejected → direct REST fallback. API keys never reach the
browser. Server STT is disabled — HUD/Mobile Lens use browser STT.

### 4.12 Proactive (reminders, briefing, CPU watch) — `proactive.py`

The `_loop_proaktif()` background scheduler (every 30 seconds, started via
the startup event) pushes `arvi_response` (`engine: "ARVI PROACTIVE"`) to the HUD:

- **Reminders**: `atur_pengingat()` parses "dalam N detik/menit/jam",
  "in N seconds/minutes/hours", "jam H[:MM] [pagi/siang/sore/malam]",
  "at H[:MM] [am/pm]" (past times → tomorrow); stored in LTM (max 50,
  persistent). Commands: create, "lihat/show pengingat/reminders",
  "hapus/delete pengingat/reminder N", "hapus/delete semua/all".
- **Morning briefing**: `deteksi_perintah_briefing()` — "aktifkan briefing pagi
  jam 6" / "turn on briefing at 6", "matikan/turn off briefing", or
  "briefing pagi" (serve now). `_susun_briefing()` assembles from system
  status without an LLM (English date, node, processes, reminders, fact count).
- **CPU watch**: `_catat_cpu_telemetri()` records "CPU: NN%" samples per
  telemetry (240-sample deque); `_cpu_tinggi_berkepanjangan()` is true above
  80% sustained 10 minutes → suggestion + fresh CPU inspection, 1-hour cooldown.
- STM recording via executor (LTM extraction every 10 turns is blocking).

### 4.13 Structured LLM tag parsers (`ai_engine.py`)

- `_terapkan_tool_json()`: strict-schema ` ```tool {"aksi": [...]} ``` ` blocks
  (dict + list of valid names, max 5 actions) as the structured successor of
  `[EXEC_KEY]`; both are processed, tags/blocks stripped before reaching the HUD.
- `_terapkan_exec_action()`: `[EXEC_ACTION: {...}]` structured actions
  (open/close app, close site, move monitor, search-active) with close/search
  leak guards; same 5-action cap.
- `_catat_hasil_eksekusi()`: real execution results are appended to the last
  assistant message in STM so the next LLM reply is grounded.

### 4.14 Daily news (`berita.py`)

Public RSS → Meta summary, cached, memory-free. Two scopes (`dunia` with
BBC World/Al Jazeera/DW/Guardian/France24, `indonesia` with CNN Indonesia/
Antara/Republika/BBC Indonesia/Tempo), max 15 items/feed, 30-article sample,
exact + near-dedupe, greedy topic clustering, rewritten summary with source
links, 45-minute cache per (scope, language). Explicit past ranges
("3 bulan lalu", "last month") get an honest unsupported reply; dead sources
are skipped, never fatal. `jalankan_galeri_berita()` additionally returns the
card array `{judul, ringkasan, sumber, tautan, gambar}` for the HUD gallery.
Article content is UNTRUSTED: instructions inside articles are ignored, the
path is text-only, writes no history, and EXEC/tool tags are never applied.

### 4.15 Cursor calibration (`kalibrasi_kursor.py`)

Persistent click correction (`server/arvi_kalibrasi_kursor.json`, git-ignored):
offset ±500 px, scale 0.8–1.2, `final = round(raw * scale + offset)`.
Bilingual intents: guided auto self-calibration (`kalibrasi kursor` /
`calibrate cursor` — high-contrast markers, Vision-guessed percent
coordinates, delta stored), reset, absolute manual offset
(`atur offset kursor X Y`), relative nudge (`geser kalibrasi kursor
kanan 10 bawah 5`). Replies go out verbatim so offset numbers always survive.

### 4.16 Phone attachments (`mobile_file.py`)

Validates + decodes Mobile Lens attachments → `(kind, raw_bytes)`:
images (jpg/jpeg/png/webp) → Vision + SAM pipeline; PDF (≤20 pages,
defensive pypdf → PyPDF2 → regex extraction) and text/code/log extensions
→ Meta cognitive analysis (≤8000 chars + `[...dipotong...]` marker).
6 MB cap; unsupported extensions, broken base64, or empty files → friendly
`ValueError` surfaced as HTTP 422.

### 4.17 Physical network audit + dashboards (`os_control.py` + router + HUD)

When the threat-hunt intent fires, `jalankan_audit_koneksi_fisik()` opens a
real visible `cmd.exe` window and types `ping 8.8.8.8 -n 4`,
`tracert -d -h 10 8.8.8.8`, `netstat -ano` with demo pauses, then auto-closes
with `exit`. The same commands are captured in parallel hidden subprocesses
(ID/EN-tolerant ping/tracert parsers), merged with the standard psutil/netstat
connection table + memory-free SOC verdict, and sent as structured
`netscan_panel` JSON to the HUD cyber dashboard (stat chips, ping, tracert,
connection table, verdict). AppSec results likewise go to a split-screen
`appsec_panel` (screenshot + SAFE/VULNERABLE card) after `fokuskan_jendela_hud()`
brings the HUD browser back to front; news goes to the `news_gallery` card
grid. Chat/voice stays one short sentence per result.

---

## 5. `/ws/hud` WebSocket Protocol

Auth gate: the first message must be `{type:"auth", token}` within 10 seconds,
verified via `arvi_auth`; failure → `auth_failed` + connection close.

### 5.1 HUD → server

| `type` | Payload | Effect |
|---|---|---|
| `auth` | `{token}` | Socket session login |
| `ping` | `{t}` | Answered with `pong` (RTT/latency measure) |
| `user_command` | `{command, sumber?, final?}` | Main command pipeline (see §7); voice needs the "Arvi" prefix |
| `vision_scan` | `{image, prompt, sumber?, final?}` | Laptop camera frame → Vision → `vision_response` + 25 s frame store |
| `os_command` | `{raw/command/target, aksi, sumber?, final?}` | Explicit OS control → `system_response` |
| `action:"open_software"` | `{target}` | Legacy payload compat → open app |
| `input_command` | `{command, params}` | Explicit mouse/keyboard → `system_response` |

### 5.2 Server → HUD

| `type` | Payload | Used by the HUD for |
|---|---|---|
| `auth_ok` / `auth_failed` / `auth_required` | `{pemilik, metode}` | Open/close the lockscreen |
| `pong` | `{t, waktu_server}` | `LATENCY` label |
| `agent_log` | `{message}` | Workspace terminal line (+ toast/badge when important) |
| `arvi_response` | `{text, engine}` | Dialogue + engine badge + TTS |
| `vision_response` | `{text, sumber, engine}` | Optical dialogue; `sumber`: laptop/mobile/layar/lanjutan/network/forensik/qr/appsec/clipboard/kalibrasi |
| `system_response` | `{message}` | "ARVI OS CONTROL" dialogue; tactical ≤45-char confirmations are read aloud |
| `grounding_preview` | `{image, target, sumber, x?, y?}` | Image in the Vision panel; `sumber`: klik/mobile/layar/screenshot/kalibrasi/forensik/qr |
| `mobile_user_echo` | `{text, sumber}` | Phone command echo in the laptop dialogue |
| `netscan_panel` | `{ping, tracert, koneksi, vonis, galat, demo}` | Cyber-security dashboard modal |
| `appsec_panel` | `{image, status, detail}` | AppSec split-screen modal |
| `news_gallery` | `{artikel, cakupan, bahasa}` | News card-gallery modal |
| `ptt_start` / `ptt_stop` | — | Stop voice + listen / send |

## 6. `/ws/node` WebSocket Protocol

PSK auth gate: the first message must be `{type:"auth", token}` within 10 s
(PSK in `security/arvi_node.json`, auto-created, read by node + server);
failure → `auth_failed` + close. The node answers `auth_ok`, then receives
the initial `INSPECT_CPU`. Server → node: `{action:"INSPECT_CPU"}` and
`{action:"PING_NETWORK"}` (a `type` payload is also accepted by the node).
Node → server: `{type:"telemetry", payload}` → `system_context["latest_telemetry"]`
+ CPU-watch recording (HUD broadcast muted — silent UX);
`{type:"action_result", action, output}` → `top_processes` / `last_ping` + HUD
broadcast per line (max 60 lines). All node text is sanitized
(`_bersihkan_telemetri`: strip control chars, cap length) before entering
LLM context — anti prompt injection. `nodes/laptop_node.py`: PSK auth
+ retry, 2-stage `psutil` sampling (0.3 s interval) for the 5 heaviest
processes + `ping -n 2 8.8.8.8`; accepts `action` or `type`.

## 7. `user_command` Pipeline (fast-path order)

```text
name normalization → voice gate → LOCKDOWN → autonomous AGENT → SYSTEM/MEDIA
→ CALIBRATION → CYBER (forensics → QR → AppSec) → CLIPBOARD → THREAT-HUNT
→ SCREEN → IN-APP → OS → INPUT → PROACTIVE → NEWS → CPU/ping prefetch →
follow-up VISUAL → MUSE
```

1. **Lockdown** — checked before everything; never delayed.
2. **Autonomous agent** — multi-action ("…lalu…"), before all other fast-paths
   (HUD path only; deterministic in-app composites yield past it).
3. **System/media control** — before screen/OS because "hentikan musik" ≠ close
   Spotify and "tampilkan desktop" ≠ read screen. Screenshots also send
   `grounding_preview`.
4. **Cursor calibration** — auto/reset/manual-offset; verbatim replies.
5. **Cyber-agent** — photo forensics ("cek foto ini", "is this image ai") →
   bbox → auto-crop → Meta verdict; QR SOC ("scan qr", "read qr") → local
   decode → SAFE/DANGEROUS verdict; AppSec ("audit kode di layar", "audit
   terminal") → auditor verdict + HUD refocus + split panel. Checked before Screen.
6. **Clipboard audit** — SOC verdict on clipboard text.
7. **Network threat-hunt** — visible CMD demo + connection SOC audit → cyber
   dashboard + one-sentence chat.
8. **Screen** — read (→ `vision_response` + preview), click, open-and-click
   (2 s sleep, crosshair preview).
9. **In-app** — before OS so "tutup tab chrome" ≠ close Chrome.
10. **OS** — open/close whitelisted apps.
11. **Input** — mouse/keyboard via executor.
12. **Proactive** — reminders ("ingatkan …", "lihat/hapus pengingat") and
    briefing ("briefing pagi", on/off + hour).
13. **News** — today's headlines → gallery modal + one-sentence chat.
14. **Prefetch** — CPU/process/ping words → ask the node, sleep 0.8–1.2 s.
15. **Follow-up visual** — questions on the last 25 s frame + STM context.
16. **Muse** — default → `MUSE SPARK 1.3` (Baseten Open 1026 first,
    Muse 1.3 fallback).
- Listener filter: replies containing `[ABAIKAN_OBROLAN_LAIN]` → the turn is
  dropped (`_buang_turn_terakhir`), ARVI stays quiet (side conversation).
- `[EXEC_KEY: …]`, ```tool blocks, and `[EXEC_ACTION: …]` are executed
  (max 5 actions, low-risk allowlist) + stripped before reaching the HUD;
  results are appended to STM (`_catat_hasil_eksekusi`).

`/api/mobile-command` uses the identical order (minus the autonomous agent)
and broadcasts results to the HUD + returns `{ok, text}` to be read on the phone.

## 8. REST API Reference

| Method & Path | Body | Response | Notes |
|---|---|---|---|
| `GET /` | — | redirect | → `/hud/index.html` |
| `GET /hud/index.html` | — | HTML | HUD page |
| `GET /hud/app.js` | — | JS | HUD logic |
| `GET /mobile-lens` | — | HTML | Phone page (via QR) |
| `GET /api/mobile-url` 🔒HUD | — | `{ok, url}` | LAN URL `/mobile-lens?t=<phone-token>` for QR (HUD session required) |
| `POST /api/mobile-scan` 🔒 | `{image, prompt, sumber?, final?}` | `{ok, text, sam?}` | Phone photo → Vision; broadcasts `grounding_preview` + `vision_response` to the HUD; stores the 25 s frame |
| `POST /api/mobile-command` 🔒 | `{text, sumber?, final?}` | `{ok, text}` | Phone command = full HUD pipeline; broadcasts to the HUD |
| `POST /api/mobile-file` 🔒 | `{filename, data_b64, prompt?, sumber?, final?}` | `{ok, text, sam?}` | Phone attachment → Vision/SAM (images) or cognitive (PDF/text); broadcasts to the HUD |
| `POST /api/tts` 🔒 | `{text, voice_id?, model_id?}` | MP3 / 503 | ElevenLabs; 503 → HUD uses the browser voice |
| `POST /api/stt` 🔒 | `{audio_b64, mime_type?}` | 501 `STT_DISABLED` | Server STT disabled; HUD + phone must use browser STT |
| `GET /api/stats` | — | `{ok, node_aktif, hud_terhubung, waktu_server, uptime_detik}` | Live HUD telemetry |
| `GET /auth/status` | — | `{ok, butuh_setup, operator[]}` | Lockscreen mode |
| `POST /auth/setup/password` | `{username, password}` | token | The FIRST account = owner (one-time) |
| `POST /auth/login` | `{username, password}` | token | Login → 8-hour HMAC token |
| `POST /auth/mobile/putar` 🔒HUD | — | `{ok, url}` | Rotate the phone token (old QR dies); returns the new QR URL |

🔒 = requires an `Authorization: Bearer` header with a HUD session or phone token.
🔒HUD = HUD session token only. Without a valid token → HTTP 401.
CORS is open (`allow_origins=["*"]`) so same-WiFi phones can connect.

---

## 9. HUD Frontend (`hud/index.html` + `hud/app.js` + `hud/mobile-lens.html`)

All UI strings are English (Sign In, Create Account, Hold to Talk,
Send, Target Lock); TTS/STT are bilingual following the text language.

### 9.1 `index.html` layout

English lockscreen (Sign In / Create Account, username + password) →
status header (ARVI, phone QR, lock, audio, WS, nodes) → center `main`
(animated Baymax head: idle/speaking/listening + blink,
core status, fixed-height scrollable `dialogue-box`, command form + mic/AUTO/
PTT, camera choice, Vision/Output buttons) → bottom-left status chips
(`LATENCY` + `ENGINE`, fixed, outside the layout flow) → left Vision drawer
(live `webcam-feed`, SAM `spatial-canvas` overlay, `grounding-img` evidence,
`detected-tag`, Scan button) → right Workspace drawer (terminal, manual-open
only, red-dot badge) → Mobile Lens QR popover → cyber/AppSec/news dashboard
modals (✕ / Escape) → bottom-right toast stack.

### 9.2 `app.js` — section map

- **Voice out**: `speakArvi()` (utterance core ≤350 chars, ElevenLabs
  `/api/tts` + `playbackRate`, bilingual `speechSynthesis` fallback —
  Indonesian text → `id-ID` voice, else `en-US`),
  `hentikanSuaraArvi()` (all `<audio>` + synth; 900 ms cooldown except PTT).
- **Tactical voice**: short (≤45 chars, tagless) `system_response`
  confirmations are read aloud; system reports/errors stay visual-only.
- **Voice in**: Web Speech `continuous`, finals only (`interimResults=false`),
  hands-free toggle (mic tap = toggle, hold ≥250 ms = talk), browser
  `Ctrl+Alt` PTT while the HUD is focused, 🔇/🎙 icons. The mic is NEVER
  stopped by the app itself (only intentional stops: PTT release, hands-free
  OFF, lock); browser-ended sessions auto-restart.
- **Echo + barge-in**: ARVI's own speech is discarded per-transcript
  (`isEchoFromArvi`, 15 s window) without muting the mic; only a PREFIXED
  "Arvi stop" (`stop/berhenti/cukup/diam/tahan` after the prefix) cuts in —
  silence only, nothing executes.
- **Voice gate mirror**: spoken finals must start with "Arvi" (start-only
  aliases accepted), else dropped client-side with `[VOICE IGNORED]`;
  unclear prefix asks for a repeat. Submissions carry `sumber:"suara"`.
- **Camera**: `mulaiPreviewKamera()` (live only while the panel is open),
  `hentikanKamera()` (fully off on close), `ambilFrameSekaliPakai()`
  (reuses the preview, shows the still in `grounding-img`),
  `tampilkanGroundingPreview()` (`TARGET LOCK` vs `PREVIEW:` labels).
- **WS**: `connectWebSocket()` + token auth + ping/RTT + `setEngineBadge()`
  (per-engine colors) + `setLabelLatency()`.
- **Dashboards**: `tampilkanPanelCyber()` / `tampilkanPanelAppsec()` /
  `tampilkanGaleriBerita()` render server JSON via `textContent` (XSS-safe);
  `tampilkanToast()` (3 s auto-dismiss, max 3) + `tandaiAktivitasWorkspace()`
  (red-dot badge) replace drawer auto-pop.
- **Light intent mirror**: client-side OS open/close detection (the server
  re-validates via whitelist).
- **Live telemetry**: `/api/stats` polling + node label.

### 9.3 Mobile Lens (`hud/mobile-lens.html`, dark PWA)

- Empty text input + **Send** button (Enter supported): photo present →
  `/api/mobile-scan`, else → `/api/mobile-command`; answers are read aloud
  on the phone (ElevenLabs → synth fallback).
- **Dual-mode camera**: WebRTC when `getUserMedia` is available, else native
  `<input capture="environment">` fallback (immune to HTTP blocks) →
  ≤640 px canvas downscale → lock → shown in `#beku` → purple mic /
  type+Send. Tap-to-copy `chrome://flags` hint.
- Walkie-talkie (hold→release→send) + 2-step scan (photo then voice instruction).
- Every phone result is broadcast by the server to the laptop HUD in real time
  (dialogue + Vision panel + grounding); the phone opens no WS itself so the
  Login Gate cannot be bypassed.
- The phone token (`?t=` from the QR) is sent as a Bearer header on every
  request; without a token → 401 + "open from the HUD QR" warning.
- Voice prefix gate + name normalization mirror the HUD; hands-free loop with
  Wake Lock; silent/failure states keep looping; audio + camera + STT shut
  down when the page is left.
- STT without a recording fallback: when the browser blocks Web Speech API
  (`not-allowed` on Android HTTP — `MediaRecorder`/`getUserMedia` audio die
  with it, so record-via-server is a dead end and was removed), the phone
  never attempts recording. An instruction banner shows: (1) type or dictate
  via *Keyboard Voice Typing* (Gboard mic icon), OR (2) permanently allow via
  the `chrome://flags/#unsafely-treat-insecure-origin-as-secure` flag + 1-tap
  origin copy box. Bilingual phone TTS (`id-ID` vs `en-US`) like the HUD.

---

## 10. Security

- **Login Gate**: one-time setup → owner account; PBKDF2-SHA256 login
  (200k iterations + 16 B salt); generic failure message (anti-enumeration).
- **Session tokens**: `v1.<payload_b64url>.<hmac_sha256>`, derived key
  `SHA256(ARVI_MASTER_SECRET + "|arvi-sesi-v1")`, claims
  `{sub, metode, peran, iat, exp}`, 8 hours, `hmac.compare_digest`.
- **Locked WS**: `/ws/hud` must auth within 10 s; sessionless messages rejected.
- **Phone tokens**: mobile + TTS endpoints require a Bearer session/phone token;
  phone tokens are server-made, embedded in the QR, rotatable (`/auth/mobile/putar`).
- **Node PSK**: `/ws/node` requires PSK auth within 10 s; rogue nodes rejected.
- **Telemetry sanitation**: node text is cleaned (control chars + length/
  line caps) before entering LLM context — anti prompt injection.
- **Bounded LLM actions**: `[EXEC_KEY]`/tool-JSON/`[EXEC_ACTION]` cover only
  low-risk allowlisted actions, max 5/response; screen lock/typing/clicking
  only from direct user commands.
- **Anti-injection**: no shell composition from user input
  (`shell=False`, fixed `taskkill` argv); app/key/hotkey whitelists;
  coordinates clamped; typed text ≤500 chars.
- **Secrets**: `.env`, `arvi_users.json`, `arvi_mobile.json`,
  `arvi_node.json`, `arvi_memory.json`, `arvi_kalibrasi_kursor.json`,
  `test_report.txt` in `.gitignore`;
  API keys never reach the browser; logs carry only key status + length.
- **Camera privacy**: Auto-Off — cameras live only while their panel/page
  is open; manual toggles included.
- No biometrics (face/WebAuthn/geofence/vault) anywhere in this repo;
  the active login is username + password.

## 11. `.env` Configuration

```text
ARVI_MASTER_SECRET=...   # REQUIRED: HMAC session key
META_API_KEY=...         # Muse Spark 1.3 (LLM|id|secret format)
BASETEN_API_KEY=...      # Vision + Muse Open 1026
ELEVENLABS_API_KEY=...   # TTS (optional; without it → browser voice)
ELEVENLABS_VOICE_ID=...  # default JBFqnCBsd6RMkjVDRZzb (optional)
ELEVENLABS_MODEL_ID=...  # default eleven_v4 (optional)
```

Python dependencies (`requirements.txt`): `fastapi uvicorn pydantic
python-dotenv websockets requests psutil pillow pyautogui pyperclip keyboard`
+ optional `elevenlabs opencv-python pypdf` (all defensive).

## 12. Operations

- **Run (by the user)**: `python server/main.py`, then optionally
  `python nodes/laptop_node.py` in a second terminal; open
  `http://127.0.0.1:8080/` (redirects to the HUD).
- **Phone**: HUD header → phone QR → scan → phone Chrome opens `/mobile-lens`
  (same WiFi; allow firewall port 8080 if needed; native-camera fallback
  on HTTP origins is automatic).
- **PTT**: hold `Ctrl+Alt` (global, server-side) or the HUD PTT button; the
  physical speaker auto-mutes while held.
- **Agent rule**: the agent NEVER runs servers/tests (anti-deadlock);
  it only writes/edits/saves + static-checks. Tests run manually by the user.

## 13. Testing

During development the repo carried a hermetic `unittest` suite (`tests/` +
`run_all_tests.py`, stubs/mocks — no real server/mouse/camera). It was
removed for the public push; every shipped file is at least syntax-verified
(`python -m py_compile`, `node --check`). To re-verify behavior, restore the
suite from git history and run it manually.

## 14. Quick Troubleshooting

| Symptom | Common cause | Action |
|---|---|---|
| HUD stuck on lockscreen | `.env` lacks `ARVI_MASTER_SECRET` | Fill the secret, restart the server |
| "API Key belum disetel" response | Empty/malformed key | Check startup logs `[+] … termuat` |
| Global PTT dead | `keyboard` not installed / hook failed | `pip install keyboard`, check `[+] Global shortcut` log |
| Click/type fails | `pyautogui` not installed | `pip install pyautogui` (clear `[SYSTEM ERROR]` message) |
| Empty Vision | `BASETEN_API_KEY` empty | Fill the Baseten key |
| Robotic browser voice | ElevenLabs failed/503 | Check `ELEVENLABS_API_KEY`/quota |
| Phone cannot open | Different WiFi / firewall / HTTP origin | Same WiFi, allow port 8080, native fallback is automatic |
| Blank laptop camera | Non-local origin / permission denied | Open via `127.0.0.1`, allow the camera |
| Phone 401 / "token hilang" | Manual URL without QR / rotated token | Re-scan the QR from the HUD header |
| Node "auth ditolak" | Mismatched/corrupt `arvi_node.json` | Delete that file, restart server + node (a new PSK is made) |
| Reminder never fires | No HUD connected when due (reminders persist) | Open the HUD; reminders push while a HUD is present |
| "Engine … tidak dikonfigurasi" response | `META_API_KEY`/`BASETEN_API_KEY` empty | Fill at least one Meta/Baseten key in `.env` |

## 15. File Inventory & Status

See `STRUKTUR_PROYEK.md` for the current file map. Summary: 4 working folders
(`hud/`, `server/`, `security/`, `nodes/`),
4 public docs (`README.md`, `DOKUMEN_TEKNIS.md` — this file,
`KEMAMPUAN_ARVI.md`, `STRUKTUR_PROYEK.md`), 6 local
secrets (`.env` + 5 runtime JSONs), and `requirements.txt`. Old one-shot scripts
(`baseten_test.py`, `test-gemini.py`) were cleaned (Nov 2026). Architecture
refactor (Nov 2026): the `main.py` monolith was split into 12 `server/*`
modules + a slim router + re-export facade; Gemini and auto-routing removed
entirely (100% Meta); English UI + bilingual EN/ID commands. UI/UX revision
(Nov 2026): physical CMD audit, cyber/AppSec/news dashboard modals, news
gallery, toast + badge silent workspace, muted telemetry spam. Deferred: new
AI providers (need API keys), phone control via ADB (needs an Android app),
habit learning (needs longitudinal data).
