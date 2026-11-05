# ARVI OS CAPABILITIES — Full Skill & Command List

> Compiled 100% from actually reading all code in this repository
> (`server/*.py`, `security/*.py`, `nodes/*.py`, `hud/*`).
> Every item below points to the module that really implements it.
> How to run: the user in their own terminal (`python server/main.py` +
> `python nodes/laptop_node.py`, then open the HUD in the browser).

## 1-minute architecture summary

ARVI is a bilingual (EN/ID) Windows operator driven through a browser HUD
or a phone. Text/voice commands arrive via WebSocket/REST → the FastAPI
server (`server/main.py`, port 8080) runs **deterministic fast-paths**
(regex, no LLM: lockdown → autonomous agent → system/media → calibration →
forensics → QR → AppSec → clipboard → threat-hunt → screen → in-app → OS →
input → proactive → news) → when nothing matches, they go to the **Meta
engines** (Baseten `muse-spark-open-1026`, Meta `muse-spark-1.3` fallback)
→ answers are read aloud via ElevenLabs TTS (browser-voice fallback).
Audit-grade results open as dashboard modals; chat stays one short sentence.
Laptop telemetry is sent by the edge node (`nodes/laptop_node.py`) every
~5 seconds and enters LLM context only when the user asks about the device.

| Process | Command | Role |
|---|---|---|
| Core server | `python server/main.py` | HTTP + WS + AI + execution (required) |
| Edge node | `python nodes/laptop_node.py` | CPU/RAM/battery telemetry + ping (optional, recommended) |
| Laptop HUD | browser → `http://127.0.0.1:8080/` | Main UI (redirects to `/hud/index.html`) |
| Mobile Lens | phone Chrome → QR URL | Camera + voice/text commands from the phone |

---

## 1. AI chat brain (Muse Spark)

**Module:** `server/ai_engine.py` → `query_arvi_cognitive()`

- **Two engines, automatic fallback.** Primary: Baseten `meta-models/muse-spark-open-1026`
  (2048 max tokens, 45 s timeout). On failure/missing key: Meta
  `muse-spark-1.3` via `https://api.meta.ai/v1/responses` (30 s timeout).
  Without either key → a clear `[CONFIG ERROR]` message.
- **Persona.** ARVI = a warm bilingual friend, English priority: answers
  English for English/mixed users, may use casual Indonesian + English tech
  terms for full-Indonesian users. Never calls the user "Operator";
  greets by name once known (`"namaku X"` / `"my name is X"`).
- **Device-aware (only when asked).** When the message contains words like
  cpu/ram/process/ping/network/laptop/node/etc, the LLM gets a
  `[LIVE HARDWARE TELEMETRY]` block (node status + 5 heaviest processes + ping
  results). Otherwise the LLM is **forbidden** from mentioning CPU/RAM/node numbers.
- **Conversation-partner detection (mic always on).** When the input is clearly
  aimed at someone else in the room (calling another name, asking to fetch a
  physical object, contextless mumbling), the LLM must reply exactly
  `[ABAIKAN_OBROLAN_LAIN]` → ARVI stays silent and that turn is **dropped**
  from session memory.
- Examples: `explain why my laptop is slow`, `how is my network today?`,
  `keep me company for a bit`, `my name is Fagabond`.

## 2. Memory: session (STM) + permanent (LTM)

**Module:** `server/memory.py` (+ `server/arvi_memory.json`, git-ignored)

- **STM:** last 20 messages (10 turns), sent as chat context
  (20 to Baseten, 10 to Meta). Always persisted + interaction counter.
- **LTM (survives restarts):** `profil_user {nama, preferensi, gaya_kerja}`,
  `fakta_penting[]` (max 100, 500 chars/fact), `ringkasan_terakhir`,
  `interaksi`, plus reminder & briefing data (§15).
- **Explicit remember commands** → stored + warmly confirmed by the LLM:
  `ingat ya, aku lagi kerjakan proyek ARVI` · `catat bahwa deadline hari Jumat`
  · `tolong ingat ...` · `jangan lupa kalau ...` ·
  `remember that ...` / `note that ...` / `don't forget ...`.
- **Automatic background extraction:** every 10 interactions, a background
  thread asks the LLM to extract ≤2 facts + 1 summary (JSON `{fakta, ringkasan}`)
  from the last 10 messages. Fails silently when the API is down.
- Facts + profile + summary are injected into every system prompt as
  `[PERMANENT MEMORY ABOUT THE USER]`.

## 3. Input normalization: the "Arvi" name + command typos

**Module:** `server/memory.py`, mirrored in `hud/app.js` + `hud/mobile-lens.html`

- **STT mishearings → "Arvi":** `arfi/arbi/alfi/arvy/harfi/arvie/rv/arvee/arpi/arwi/harvi`
  always fixed; `arti` only as a greeting (`hai arti`, `arti, ...`) so
  `apa arti kata ini` never breaks. The server re-normalizes every input.
- **Double-letter typos on 25 command verbs:** `bukaa/buuka→buka`,
  `tutuup→tutup`, `arahkann→arahkan`, `carii→cari`, `ketikkan`, `tampilkan`,
  etc. Whole-word known verbs only — `scroll`, `google`, `bukan`, `dibuka`
  are never damaged.
- **Voice gate:** spoken finals must start with "Arvi" (start-only aliases
  `avi/awi/ari` accepted) or they are dropped before any intent/routing/
  execution on every voice path (HUD WS, mobile command/scan/file). Interim
  results never execute. "Arvi" + empty/filler remainder → asked to repeat.
- Examples: `Bukaa explorer`, `tutuup spotify`, `hai arfi, apa kabar`.

## 4. Multi-step autonomous agent (Muse Agent)

**Module:** `server/ai_engine.py` → `deteksi_dan_jalankan_agen_otonom()`
(HUD `/ws/hud` path only, checked before all other fast-paths)

- **Triggers:** the sentence contains a conjunction (`lalu, kemudian, setelah itu,
  terus, habis itu, then, after that, and then, and type/open/click/...`) **and**
  an action word (`buka/tutup/klik/ketik/cari/open/type/click/...`).
- **How it works:** Muse splits the command into a JSON array of ≤8 steps, run
  in order with real-time `[MUSE AGENT STEP i/N]` logs to the HUD, then
  `Finished running X/Y autonomous steps.`
- **11 valid actions:** `buka_app`, `buka_url` (web DB → bookmark → raw URL),
  `tab_baru`, `ketik_teks`, `tekan_tombol` (+`kombinasi` e.g. `ctrl+s`),
  `klik_layar` (Vision), `baca_layar`, `inspect_cpu` (via node),
  `kontrol_sistem`, `tunggu` (0.2–10 s).
- **Smart exceptions:** YouTube-composite/site-close/contextual-search commands
  yield to the deterministic in-app handler (no LLM).
- Examples: `buka notepad lalu ketik rencana kerja hari ini` ·
  `open chrome then search for jakarta weather` ·
  `cek cpu lalu tunggu 2 detik lalu baca layar`.

## 5. Execution tags from LLM output + tactical replies

**Module:** `server/ai_engine.py`

- When fast-paths miss, the LLM may embed execution tags that the server runs
  immediately then **strips** from the answer text (max 5 actions/response):
  - `[EXEC_KEY: play_pause | next_track | prev_track | vol_up | vol_down | mute | win_d]`
  - Structured block ```` ```tool {"aksi": ["play_pause", ...]} ``` ````
    (strict schema: dict + `aksi` key with a list; foreign names skipped, broken
    blocks ignored without execution).
  - `[EXEC_ACTION: {"type": "open_app"|"close_app"|"close_site"|"move_monitor"|"search_active", "target": "..."}]`
    — guarded: close commands cannot leak into search typing.
- **Anti-runaway & anti-hallucination:** risky actions (screen lock, typing,
  clicking) **cannot** fire from LLM output — only from direct user commands.
  Real execution results are written back into the last assistant message in
  STM, so subsequent answers rest on real success/failure, not claims.
- **Tactical replies:** success → 1 random elite-assistant sentence with no
  back-to-back repeat (`Alright, sir.` / `Very well, Fagabond.` / `Copy that, sir.` /
  `On it, sir.` / ...); failure → the original message verbatim (honest).

## 6. Windows app control (whitelist)

**Module:** `server/os_control.py` → `APP_DATABASE`, `deteksi_intent_os()`,
`execute_os_command()` (+ a light mirror in `hud/app.js`)

- **18 registered apps** (adding an app = adding 1 entry, nothing else):

| Canonical | Aliases (ID/EN) | Open | Close |
|---|---|---|---|
| resource monitor | resource monitor, resmon, monitor sumber daya | `resmon.exe` | taskkill |
| spotify | spotify | local exe → `spotify:` protocol | taskkill 3 exes |
| notepad | notepad, note pad, catatan | `notepad.exe` | taskkill |
| kalkulator | kalkulator, calculator, calc, kalkulasi | `calc.exe` | taskkill |
| chrome | chrome, google chrome, browser | `start chrome` | taskkill |
| edge | edge, microsoft edge | `start msedge` | taskkill |
| explorer | explorer, file explorer, eksplorer, folder, file manager | always a new window | **forbidden** (system shell) |
| cmd | cmd, command prompt, terminal, konsol | `cmd.exe` | taskkill |
| powershell | powershell, power shell | `powershell.exe` | taskkill |
| task manager performance | task manager performance, performa task manager, tab performance, grafik cpu, performance monitor | reg + `taskmgr.exe` on the Performance tab | taskkill |
| task manager | task manager, taskmanager, manajer tugas | `taskmgr.exe` | taskkill |
| pengaturan | pengaturan, settings, setting | `ms-settings:` | **forbidden** |
| paint | paint, mspaint | `mspaint.exe` | taskkill |
| snipping | snipping, snipping tool, screenshot, tangkapan layar | `snippingtool.exe` | taskkill |
| vscode | vscode, vs code, visual studio code, code, editor | `start code` | taskkill |
| word | word, microsoft word, ms word | `start winword` | taskkill |
| excel | excel, microsoft excel, ms excel | `start excel` | taskkill |
| powerpoint | powerpoint, power point, ppt, presentasi, ms powerpoint | `start powerpnt` | taskkill |

- **Smart & safe:** when the process already runs → **focus its window** (Win32
  `EnumWindows` + PowerShell `AppActivate` fallback, with Chrome-specific
  avoidance of the "Who's using Chrome?" window), never a duplicate. Close =
  taskkill `/F /T` + psutil verification + 1 retry + honest report when still
  alive (save dialogs/admin rights). Aliases match **whole-word** (`barcode`
  never opens vscode; `bukan` never reads as `buka`). Raw input is never
  composed into shell commands (`shell=False`, anti command-injection).
- Open verbs: `buka/bukakan/dibuka/jalankan/open/launch/start/nyalakan/run`.
  Close verbs (prioritized): `tutup/tutupi/ditutup/close/matikan/kill/hentikan/exit/quit`.
- Examples: `buka notepad` · `tolong bukakan kalkulator` · `launch vscode` ·
  `tutup chrome` · `matikan spotify`.

## 7. Browser, sites & contextual YouTube

**Module:** `server/os_control.py` (in-app + session context)

- **Tab/window actions:** `buka tab baru di chrome/edge` · `tutup tab` /
  `close tab` · `jendela baru` / `new window` · `refresh` / `muat ulang`.
- **Google search:** `cari di google X` · `googling X` · `search google for X` ·
  `search for X on google` · `X di google` · `search for X` / `search X`
  → new tab + type + enter.
- **11 sites + Chrome bookmarks:** facebook, linkedin, instagram, gmail, youtube,
  github, whatsapp, drive, chatgpt, gemini web, elevenlabs. `buka gmail` /
  `open the arvi bookmark` → match web DB → Chrome bookmarks
  (`Default` + every `Profile *`) → open in a new active-Chrome tab + record context.
- **Domain-truthful site close** (`tutup youtube` / `close reddit tab`):
  read the active tab's address-bar URL (non-intrusive UI Automation → omnibox
  `ctrl+l/ctrl+c` fallback + clipboard restored), match hostname
  (subdomains OK, `youtu.be` = youtube), sweep tab order (max 10, stop
  when back at the starting URL), re-verify before `ctrl+w`. No match →
  **abort + honest report**, never closes the wrong tab. The close intent is
  locked so it never leaks into search typing.
- **Contextual YouTube (stateful, 5-minute TTL):**
  - Composite: `buka youtube cari lagu eminem lalu putar` → search → wait
    1.8 s → play the top video (Vision-guided click → deterministic fallback).
  - Follow-up: `putar itu` / `play it` / `putar video pertama` (21 ID/EN phrases)
    reuse the last query + status (`youtube_open/search_results/playing`),
    fused with live window detection.
- **Contextual search on the active screen:** YouTube (`/` in the active tab or
  the `results?search_query=` URL), Spotify desktop (`ctrl+L`), other apps (Vision
  click on "search box" → universal `ctrl+F` fallback).
- Examples: `buka tab baru` · `cari di google resep rendang` · `buka gmail` ·
  `tutup tab youtube` · `carikan lagu coldplay di spotify` ·
  `ketik laporan di kolom pencarian`.

## 8. Mouse & keyboard

**Module:** `server/os_control.py` → `execute_input_command()` (6 commands) +
bilingual `deteksi_intent_input()`

| Command | Safety limits | Example sentences |
|---|---|---|
| `type_text` | 500-char max, 0.03 s interval | `ketik hello world` · `type the report draft` |
| `press_key` | allowlist: enter/tab/esc/space/backspace/delete/arrows/home/end/pgup/pgdn/F1–F12/etc + aliases (`panah atas`, `spasi`, `hapus`) | `tekan enter` · `press escape` |
| `hotkey` | 2–3 keys, ctrl/alt/shift/win modifier required | `tekan ctrl+c` · combo `win+d` |
| `move_mouse` | coordinates clamped to screen size | `geser mouse ke 500 300` |
| `click_mouse` | left/right/middle/double | `klik kanan` · `double click` · `klik` |
| `scroll` | clamped ±2000; +up/−down | `scroll ke bawah` · `scroll up` |

- Long phrases win (`klik kanan` never becomes `klik`). Plain clicks belong
  to the input module (not Vision). **pyautogui failsafe on:** slide the cursor
  to the top-left corner to force-cancel; 0.25 s pause between actions.
- Callable explicitly from the HUD via WS `{type:"input_command", command, params}`.

## 9. Global media, volume, windows, screenshots

**Module:** `server/os_control.py` → `deteksi_dan_eksekusi_kontrol_sistem()`
(checked before screen/OS so `hentikan musik` ≠ close Spotify)

- **Spotify media (Win32 virtual keys, works minimized):**
  SMTC state-aware — `pause spotify`/`jeda`/`stop` only presses when not
  paused yet; `play`/`putar spotify`/`lanjutkan` only when not playing yet.
  `next song`/`skip`/`lagu selanjutnya`, `previous song`/`lagu sebelumnya`.
- **Pure-phrase guard:** only pure music commands pass; multi-action sentences
  (`... and play it`), non-Spotify platforms (youtube/chrome),
  and contextual references (`play it`, `putar itu`) are **rejected** → routed
  to the correct handler.
- **Volume:** `kecilkan/besarkan volume` (±5 taps), `mute`/`bisukan`/`unmute`
  (unless the sentence contains `tab`).
- **Windows:** `tampilkan desktop`/`show desktop` (`win+d`) ·
  `minimize/maximize jendela` (`win+down/up`) · `beralih jendela`/`switch window`
  (`alt+tab`) · move monitor (`pindahkan chrome ke monitor kanan/kiri`,
  `move ... to the other monitor` via `win+shift+←/→` + app focus when named).
- **Screen lock:** `kunci layar` / `lock the screen` (`LockWorkStation`).
- **Screenshot:** `ambil screenshot` / `take a screenshot` → save PNG
  `Pictures/arvi_screenshot_<time>.png` + JPEG preview (≤1280px) to the Vision panel.

## 10. Clipboard audit, network threat hunt & lockdown (local cyber-agent)

**Module:** `server/os_control.py` (+ `server/ai_engine.py` for the SOC verdicts)

- **Clipboard audit** (`audit clipboard` / `cek clipboard` / `periksa clipboard` /
  `audit my clipboard`): read clipboard via pyperclip → scored by the memory-free
  SOC evaluator (detects malware, reverse shells, SQLi, XSS, malicious URLs,
  leaked secrets) → ≤25-word `SAFE`/`DANGEROUS` verdict + reason. Empty clipboard
  / missing pyperclip → clear message + install command.
- **Emergency lockdown** (`initiate lockdown` / `emergency lockdown` /
  `lockdown laptop` / `isolasi sistem`) — checked **first** on both HUD and
  phone paths so it is never delayed: drop the network (`ipconfig /release` +
  `netsh wlan disconnect`) → mute speaker → lock workstation → taskkill
  chrome/edge/powershell/cmd with their trees. Every step best-effort.
- **Network threat hunt** (`cek keamanan jaringan` / `audit koneksi jaringan` /
  `cek koneksi mencurigakan` / `apakah ada backdoor di jaringanku` /
  `network threat hunt` / `scan active connections`): opens a REAL visible
  `cmd.exe` window that types `ping 8.8.8.8 -n 4`, `tracert -d -h 10 8.8.8.8`,
  `netstat -ano` with demo pauses, then auto-closes; meanwhile the same outputs
  are captured in parallel + live TCP/UDP connections collected via psutil
  (`netstat -ano` + `tasklist` fallback) → PID/process-name map → pure loopback
  filtered (risky listening ports still recorded) → heuristic flags
  (shell→outbound: powershell/cmd/python/nc/bash; exploit ports
  4444/1337/6667/3389/445; SYN-SENT) → structured JSON to the HUD **cyber
  dashboard** (stat chips, ping, tracert, connection table, SOC verdict) +
  one spoken sentence. No external connections → instant `AMAN`/`SAFE`, no API call.
- Examples: `cek clipboard saya` · `cek keamanan jaringan` · `initiate lockdown`.

## 11. Vision: laptop + phone cameras + SAM segmentation

**Modules:** `server/vision_engine.py`, `server/sam31_cloud.py`,
`hud/app.js` (scan), `hud/mobile-lens.html` (phone scan)

- **Image analysis** (`query_arvi_vision`): Baseten Open 1026 Vision —
  answers VERY briefly (1–2 sentences), follows the asker's language; guesses
  age when asked; needs `BASETEN_API_KEY`.
- **Laptop camera scan:** HUD `vision_scan` (1 frame 320×240) → Vision +
  SAM segmentation run **in parallel** → `vision_response` + SAM data
  (real polygons drawn as a HUD canvas overlay + mask/vertices/confidence
  + model name). The last frame is stored for follow-up questions.
- **Phone camera scan:** `POST /api/mobile-scan` (640px photo + prompt) → same
  pipeline + `grounding_preview` broadcast to the laptop HUD.
- **Pure-2-layer Meta segmentation (the `model` field always honest,
  no non-Meta local models):**
  1. **Layer 1 — Meta SAM 3.1 cloud** (`sam-3.1` via api.meta.ai, concept
     prompt `"object"`): box + confidence + mask token parser; 8-point
     octagon polygons when the official decoder package is absent; cyan
     annotations + `#id - NN%` labels. Never raises — always a valid dict.
     Success path = ZERO Baseten calls.
  2. **Layer 2 — Muse Spark Open 1026 bbox** (exactly 1 call per scan,
     only when Layer 1 fails — no redundant double API).
- **Follow-up visual questions** (frame valid **25 seconds**): triggered by
  direct visual words (`umur/warna/tulisan/terlihat/memegang/...`,
  `age/color/text/holding/...`) OR explicit reference phrases + question words
  (`apa isi gambar ini?`, `who is the person in the photo?`). Bare pronouns
  (`apa maksudnya itu?`) → normal chat, not Vision. The last visual answer's
  context (≤800 chars) + frame are reused without re-capturing.
- Examples: `scan objek` (→ pick Laptop/Phone) · `lihat ini` / `look at this` ·
  then `warnanya apa?` / `how old is he?`.

## 12. Screen Vision: read & click the monitor

**Module:** `server/vision_engine.py` (multi-monitor screenshots + clicks)

- **Screen read** (`lihat/baca/tampilkan ... layar/monitorku/desktop`):
  screenshot (all monitors, JPEG ≤1280px) → ask Baseten Vision →
  1–2 sentence answer + preview to the Vision panel. Camera commands
  (`kamera/foto/scan objek`) never land here.
- **Screen click** (`pilih/klik ... [di layar]`, `select the X account`):
  screenshot → Vision finds the element center → **percent → native-pixel**
  coordinates (+ stored calibration) → move + click → **targeting evidence**
  (red crosshair + coordinates) to the HUD.
  Keyboard keys (`press enter`), plain mouse clicks (`klik kanan`), and camera
  phrases belong to other modules — not Vision.
- **Open-and-click composite** (`buka chrome dan pilih akun Fagabond`):
  open app → wait 2 s → click target.
- The ARVI assistant's own UI (Mic button, HUD, terminal) is explicitly
  excluded by the prompt so it never clicks itself.
- Examples: `baca layarku` · `what is on my screen?` · `klik tombol Save di layar` ·
  `pilih akun Fagabond` · `open chrome and select the Fagabond account`.

## 13. Autonomous cyber-agent: photo forensics + QR SOC + AppSec auditor

**Modules:** `server/vision_engine.py` + `server/ai_engine.py`
(evaluated BEFORE the plain screen path)

- **AI-vs-real photo forensics** (`cek foto ini` / `buatan ai atau asli?` /
  `forensik gambar` / `is this image ai` / `ai or real?` / ...):
  screenshot → Vision localizes the main photo (bbox) → auto-crop → the Meta
  forensics expert scores texture/lighting/diffusion anomalies → 1–2 sentence
  verdict + confidence% + crop preview. No photo → language-appropriate reply.
- **On-screen QR/barcode scan** (`baca/scan/cek QR/barcode ...` + EN variants,
  English priority): 1920px screenshot → local multi-scale decode
  (trial-verified pyzbar → OpenCV `QRCodeDetector`) → QR text is **never
  opened**, only SOC-evaluated (detects phishing/typosquatting/unsafe HTTP)
  → format `{verdict}\n\n[QR] {text}` + screen preview. No decoder →
  `pip install opencv-python (atau pyzbar)`.
- **Evaluation security:** QR/clipboard go through **memory-free** evaluators
  (no LTM/history) so malicious payloads (`remember that: ...`) cannot poison
  permanent memory; LLM reasoning output is deterministically trimmed to the
  final verdict only.
- **AppSec Screen Auditor** (`audit kode di layar` / `cek kerentanan kode ini` /
  `periksa keamanan layar` / `audit terminal` / `audit code on screen` /
  `check this code for vulnerabilities` / `find security bugs on my screen`):
  sharp 1920px screenshot → Baseten Vision with the dedicated
  **Principal Application Security Auditor** system prompt (ignores ARVI's own
  HUD UI) → detects hardcoded secrets, SQLi, XSS, command injection, insecure
  deserialization, fatal logic, terminal-error causes → brief verdict
  (`SAFE`/`VULNERABLE` + finding/line + instant fix suggestion, reasoning
  trimmed) that opens the split-screen dashboard (screenshot + status card)
  while chat/voice stay at "Audit selesai." The HUD browser is auto-refocused
  after the screenshot.
- Examples: `cek foto ini di layar` · `is this ai or real?` ·
  `baca qr di layar` · `scan the qr` · `audit kode di layar` · `audit terminal`.

## 14. Voice: TTS, STT, PTT & anti-echo

**Modules:** `server/voice_engine.py`, `hud/app.js`, `hud/mobile-lens.html`

- **ElevenLabs TTS** (`POST /api/tts`, needs HUD/phone token): SDK → `eleven_multilingual_v2`
  model retry → REST fallback → MP3. Text stripped of markdown
  (2000-char max); voice/model defaults from `.env` (`eleven_v4`).
  Failure → HTTP 503 → HUD/phone use the **bilingual browser voice** (Indonesian
  words sniffed → `id-ID`, else `en-US/en-GB`). Answers >350 chars read only
  the conclusion/last paragraph; tactical confirmations ≤45 chars are read,
  system reports/errors stay visual.
- **Browser STT** (Web Speech `id-ID`, continuous, finals only): hands-free
  toggle (tap mic = toggle, hold ≥250 ms = talk); PTT button + browser
  `Ctrl+Alt` while the HUD is focused. The app itself NEVER stops the mic
  (only intentional stops); browser-ended sessions auto-restart.
  **Echo handling:** ARVI's own speech is discarded per-transcript
  (≥50% word overlap, 15 s window) without muting. **Barge-in:** only a
  prefixed `Arvi stop/berhenti/cukup/diam/tahan` cuts ARVI off (silence only).
- **Server global PTT** (`Ctrl+Alt` across Windows, via the `keyboard` lib):
  hold → `ptt_start` + paired physical-speaker mute; release → `ptt_stop` +
  unmute; thread-safe, double-proof (ignores auto-repeat), installed once when
  the first HUD authenticates. Without the keyboard lib → the server still runs
  (browser PTT).
- **Local speech-rate commands** (no server): `bicara lebih cepat/pelan`
  / `speak faster/slower` (±0.15, range 0.6–1.8, live) ·
  `normalkan kecepatan suara` / `reset speech rate` (=1.0).
- **Server STT DELIBERATELY DISABLED:** `POST /api/stt` always `501 STT_DISABLED` —
  transcription belongs to the browser/phone.
- Examples: hold mic then `pause spotify` · `bicara lebih cepat` ·
  `Arvi stop` (while ARVI speaks).

## 15. Proactive: reminders, briefing & CPU watch

**Module:** `server/proactive.py` (background scheduler every 30 s, starts at startup)

- **Reminders** (LTM-persistent, max 50): `ingatkan aku minum dalam 30 menit` ·
  `remind me about the meeting in 2 hours` / `at 9 am` ·
  `ingatkan saya rapat jam 9 pagi` (patterns: `dalam N detik/menit/jam`,
  `in N seconds/minutes/hours`, `jam H[:MM] [pagi/siang/sore/malam]`,
  `at H[:MM] [am/pm]`; past hours → tomorrow). `show reminders` /
  saying `reminder/pengingat` = list; `hapus reminder 2` / `hapus semua
  pengingat` / `delete all reminders` = delete. Due → pushed
  `⏰ Reminder: ...` (engine `ARVI PROACTIVE`) + recorded to STM.
- **Morning briefing:** `briefing` = serve now; `aktifkan briefing jam 7` /
  `turn on briefing at 7` = schedule daily; `matikan briefing` = off.
  The scheduler sends 1x/day after the target hour (default 07:00): name greeting +
  date + node/telemetry status + top 3 processes + today's reminders +
  fact count. Persistent (`aktif/jam/terakhir`).
- **CPU watch:** every `CPU: NN%` telemetry is recorded (240-sample history);
  >80% for ≥10 minutes (≥5 samples covering the window start) → notification +
  `INSPECT_CPU` to the node + help offer, 1-hour cooldown.
- The scheduler stays silent with no HUD connected; every proactive push enters STM.

## 16. Auth & security

**Modules:** `security/arvi_auth.py`, `security/arvi_users.py`,
`security/arvi_mobile.py`, `security/arvi_node.py`, `server/main.py`

- **One-time setup:** `POST /auth/setup/password` is only open while no account
  exists → creates the FIRST account (role `pemilik`) → immediately issues a
  token. A second setup → `403 SETUP_TERTUTUP`.
- **Password login:** `POST /auth/login` → PBKDF2-SHA256 verification (200,000
  iterations, 16-byte salt; 1–40 char case-insensitive usernames, 6–200 char
  passwords, anti-enumeration timing) → HMAC session token
  `v1.<payload>.<hmac>` (sub/metode/peran/iat/exp claims, 8-hour life,
  keyed from `ARVI_MASTER_SECRET`). Wrong → `401` with one generic message.
- **HUD WS gate:** the first message must be `{type:"auth", token}` within 10 s →
  `auth_ok` (socket registered + session claims) or `auth_failed` + close.
  Failed handshakes never leak into the socket sets. `ping`/`pong` for RTT.
- **Phone tokens (QR):** `GET /api/mobile-url` (HUD session required) → LAN URL
  `/mobile-lens?t=<token>`; the phone sends it as `Authorization: Bearer` on
  `/api/mobile-scan`, `/api/mobile-command`, `/api/mobile-file`, `/api/tts`.
  `POST /auth/mobile/putar` (HUD session required) rotates the token — the old QR
  dies instantly (for leaked QRs / lost phones).
- **Node PSK:** `security/arvi_node.json` (auto-created at startup);
  `/ws/node` closes connections without a valid `{type:"auth", token}` PSK within 10 s.
- **Sanitation & allowlists:** node telemetry cleaned (control chars stripped,
  2000/4000 char caps) before LLM context; memory-free SOC evaluators;
  LLM actions bound to allowlists (§5); mouse coordinates clamped; key/hotkey
  allowlists; `shell=False` + binary whitelist; HUD camera auto-off when its
  panel closes; QR URLs (carrying tokens) never sent to external QR services.

## 17. REST API & WebSocket protocols

**Module:** `server/main.py` (slim router; all logic in `server.*`)

| Endpoint | Auth | Function |
|---|---|---|
| `GET /` | — | redirect → `/hud/index.html` |
| `GET /hud/index.html`, `/hud/app.js` | — | serve the laptop HUD |
| `GET /mobile-lens` | — (token in `?t=`) | phone camera page |
| `GET /api/mobile-url` | HUD session | LAN QR URL + phone token |
| `POST /api/mobile-scan` | HUD/phone | phone photo → parallel Vision + SAM → broadcast to HUD |
| `POST /api/mobile-command` | HUD/phone | phone command → full pipeline (lockdown → system → calibration → forensics → QR → AppSec → clipboard → threat-hunt → screen → in-app → OS → input → proactive → news → visual → Muse + CPU/ping prefetch) → answer text to be read on the phone |
| `POST /api/mobile-file` | HUD/phone | phone attachment → Vision + SAM (images) / cognitive (PDF/text ≤8000 chars, PDF ≤20 pages, file ≤6 MB) → broadcast to HUD + text to phone |
| `POST /api/tts` | HUD/phone | text → ElevenLabs MP3 (failure → 503) |
| `POST /api/stt` | HUD/phone | always `501 STT_DISABLED` (deliberate) |
| `GET /api/stats` | — | `{node_aktif, hud_terhubung, waktu_server, uptime_detik}` |
| `GET /auth/status` | — | `{butuh_setup, operator[]}` |
| `POST /auth/setup/password` | — (one-time) | create the owner account → token |
| `POST /auth/login` | — | login → token |
| `POST /auth/mobile/putar` | HUD session | rotate the phone token → new QR URL |
| `WS /ws/hud` | token within 10 s | commands + vision + OS/input (below) |
| `WS /ws/node` | PSK within 10 s | node telemetry + action results |

- **WS `/ws/hud` in:** `user_command` (16-stage pipeline + CPU/ping prefetch +
  LLM tags), `vision_scan`, `os_command`, `input_command`,
  legacy `{action:"open_software"}`, `ping`.
- **WS `/ws/hud` out:** `agent_log`, `arvi_response`, `vision_response`,
  `system_response`, `grounding_preview` (targeting evidence/previews),
  `mobile_user_echo`, `netscan_panel`, `appsec_panel`, `news_gallery`,
  `auth_ok/failed/required`, `pong`, `ptt_start/stop`.
- **WS `/ws/node`:** `telemetry` → `system_context` + CPU recording (HUD
  broadcast muted); `action_result` (`INSPECT_CPU` → `top_processes`,
  `PING_NETWORK` → `last_ping`, first 60 lines to the HUD).

## 18. Laptop edge node

**Module:** `nodes/laptop_node.py` (separate process)

- **~5 s telemetry:** `CPU: x% | RAM: y% | PWR: z%` (`AC_POWER` when batteryless)
  → `{"type":"telemetry","node_id":"LAPTOP_01",...}`.
- **`INSPECT_CPU`:** 5 heaviest processes via 2-stage psutil sampling
  (`PID ... | name | CPU: ...%`).
- **`PING_NETWORK`:** `ping -n 2 8.8.8.8` → Average/Reply lines.
- Resilient: waits for the PSK (5 s retry), 10 s auth handshake,
  3 s auto-reconnect.

## 19. Laptop HUD (browser interface)

**Modules:** `hud/index.html` + `hud/app.js` (classic JS, works over `file://`)

- **Lockscreen:** login/setup/refresh-status; session restore via sessionStorage
  (still server-verified); **Lock** button (mic dead while locked).
- **Header:** Lock, `AUDIO: ON/MUTED` toggle, `MOBILE QR` (popover), WS status,
  live node count. **Bottom-left:** `LATENCY` chip (5 s ping/pong) +
  `ENGINE` badge (per-engine colors: VISION/PROACTIVE/MUSE).
- **Baymax head** CSS animation: idle (breathing), speaking (pulsing),
  listening, natural blinking, honors `prefers-reduced-motion`.
- **Command form:** local OS detection (server mirror; never intercepts
  tab/media/site words), local speech-rate commands, **Laptop vs Phone**
  camera confirmation (answerable typed/spoken), mic + `AUTO` toggle +
  PTT button, offline simulation mode when the server is down.
- **Vision drawer** (left slide-in, on-demand): live preview only while open
  (**camera fully dead when closed**), Scan button, real SAM polygon overlay +
  reticle + laser line, 6 s grounding, 12 s auto-close, dynamic mask status.
- **Workspace drawer** (right slide-in, manual-open only): terminal log +
  toast (3 s) + red-dot badge for important logs & long answers.
- **Dashboard modals:** cyber audit, AppSec split-screen, and news gallery
  open as overlays (✕ button / Escape closes); chat stays one short sentence.
- **Mobile Lens QR:** local render (qrcodejs) + URL text fallback; the `?t=`
  token never leaves for outside services; phone photo results → QR cleaned +
  panel auto-closed.

## 20. Mobile Lens phone (no APK install)

**Module:** `hud/mobile-lens.html` (opened from the QR, `?t=` token required)

- **Dual-mode camera:** live WebRTC (front/back flip + countdown +
  640px photo lock + retake) → native phone camera fallback (`input capture`,
  downscaled ≤640px) when Chrome-over-HTTP blocks; `chrome://flags` hint.
- **Walkie-talkie:** hold the orb button → `id-ID` STT → `POST /api/mobile-command`
  → the answer read aloud on the phone (server TTS → built-in bilingual voice).
- **2-step scan:** lock photo → hold purple mic / type + Send →
  `POST /api/mobile-scan` (photo + instruction) → answer + photo auto-released.
- **Text send:** Enter/Send (photo present → scan, else → command; anti
  double-send; text restored on failure).
- **HTTP-failure proof:** blocked mic → banner + dictate via the phone keyboard
  mic (auto-send); `ONLINE/OFFLINE` chip; visual states (thinking/speaking/
  error/recording); audio + camera + STT killed when the page is left.
- **Multi-file attach (clip Attach):** images (jpg/jpeg/png/webp) → Vision +
  SAM pipeline + preview to HUD; PDF (defensive pypdf → PyPDF2 →
  regex extraction, ≤20 pages) / `.env.example` documents / data
  (csv/json/xml/yaml/yml/ini) / code & logs (py/js/ts/html/css/sh/ps1/bat/
  sql/log/txt/md) → Meta cognitive (≤8000 chars + truncation marker); files
  ≤6 MB, off-list extensions → 422. Filename chip + ✕; typed/spoken
  instruction then Send (empty = default analysis); voice + file = auto-filled
  then sent (hands-free) or held for Send (manual).
- **Hands-free (ON/OFF):** STT → send → answer → 900 ms anti-echo pause →
  listen again, untouched; Wake Lock + re-lock when the tab is visible; silence/
  failure keeps looping; OFF = back to hold-to-talk (manual mic ignored while ON).
- **Audio toggle (header):** Muted stops TTS + speechSynthesis
  instantly and mutes all following responses (text still shows).
- **Camera toggle (header):** OFF stops every MediaStream track
  (HW indicator dead) + visual placeholder + Scan blocked; ON re-initializes
  WebRTC (locked photo kept).

## 21. What is DELIBERATELY missing / disabled (per the code)

- **Server STT** disabled (501) — transcription belongs to the browser/phone.
- **Biometrics** (face/WebAuthn/geofence/vault): **no code** in this repo
  — the active login = username + password.
- **Non-Meta AI** (Gemini/Claude/ChatGPT/Grok): no AI routing besides Meta
  (Muse Spark 1.3 + Baseten Muse Spark Open 1026 + SAM 3.1); "chatgpt"/"gemini"
  in the code are only website shortcuts.
- **Phone & IoT control:** the phone is only a remote + camera; no ADB/
  accessibility/IoT code.
- **Local non-Meta segmentation models** (MobileSAM/FastSAM Ultralytics) removed
  from runtime — segmentation is 100% Meta: SAM 3.1 Cloud → Muse Spark Open 1026 bbox.
- **The server binds `0.0.0.0:8080`** (so same-WiFi phones can reach it) with
  CORS `*` — sensitive endpoints are token-gated (§16–17).

## 22. Example command session (ID + EN)

```text
buka notepad lalu ketik rencana kerja hari ini     → 2-step autonomous agent
tolong bukakan kalkulator                          → focus/open app
tutup chrome                                       → taskkill + verification
pause spotify / next song / besarkan volume        → Win32 global media
tampilkan desktop / pindahkan chrome ke monitor kanan → windows
ambil screenshot                                   → PNG + HUD preview
buka gmail / open youtube                          → site/bookmark in a new tab
buka youtube cari lagu eminem lalu putar           → composite search + play
putar itu / play the first video                   → contextual YouTube
tutup tab youtube                                  → domain-truthful close
carikan lagu coldplay di spotify                   → contextual search
ketik hello world / tekan ctrl+c / klik kanan      → mouse/keyboard input
baca layarku / what is on my screen?               → screen vision + preview
pilih akun Fagabond / click the Save button        → click + targeting evidence
scan objek → Laptop                                → camera + Vision + SAM
warnanya apa? / how old is he?                     → follow-up visual question
cek foto ini di layar / is this ai or real?        → photo forensics
baca qr di layar / scan the qr                     → decode + SOC verdict
kalibrasi kursor / calibrate cursor               → self-calibration + stored offset
cek clipboard saya                                 → SOC clipboard audit
cek keamanan jaringan / scan active connections     → visible CMD audit + dashboard
audit kode di layar / audit terminal                → AppSec dashboard
berita hari ini / world news today                  → news gallery
lampiran app.py + "audit keamanan file ini" (HP)    → multi-file analysis
ingatkan aku minum dalam 30 menit                  → scheduled reminder
show reminders / hapus reminder 2                  → list/delete reminders
briefing / aktifkan briefing jam 7                 → morning briefing
cpu laptopku berat kenapa?                         → node prefetch + telemetry answer
initiate lockdown                                  → network isolation + lock
bicara lebih cepat                                 → TTS rate +0.15 (local)
```

## 23. Cursor calibration & grid-assisted screen click

**Modules:** `server/kalibrasi_kursor.py` (+ DPI in `server/config.py`,
geometry in `server/os_control.py`, conversion + grid in
`server/vision_engine.py`)

- **Pixel sync:** per-monitor DPI awareness on at startup; percent→pixel
  conversion uses the OS virtual-screen origin (multi-monitor +
  negative coordinates supported) + stored calibration
  (`final = round(raw * scale + offset)`, virtual-range clamped).
- **Targeting grid:** the Vision screenshot copy is drawn with a 10% grid +
  `10..90` numbers as a precision ruler; the HUD preview stays pristine.
- **Commands (ID/EN):** `kalibrasi kursor` · `kalibrasi mouse` ·
  `perbaiki akurasi klik` · `calibrate cursor` → measure via A/B markers +
  store compensation + demo to screen center
  (`Kalibrasi kursor selesai. Offset dikoreksi (X: …, Y: …).`);
  `reset kalibrasi kursor` / `reset cursor calibration` → zero it;
  `atur offset kursor 10 -5` / `calibrate cursor offset 10 -5` → set directly;
  `geser kalibrasi kursor kanan 10 bawah 5` → relative nudge.
  Persistent in `server/arvi_kalibrasi_kursor.json` (git-ignored).
- Examples: `kalibrasi kursor` · `reset kalibrasi kursor` ·
  `geser kalibrasi kursor kanan 10 bawah 5`.

## 24. Daily news + gallery

**Module:** `server/berita.py` (pipeline) + `hud/app.js` (gallery modal)

- **Triggers:** news signals (`berita/kabar/news/headline/headlines`) with scope
  words (`indonesia` → Indonesia scope; `dunia/world/global/internasional/...` →
  world scope; default follows the language). Past ranges (`3 bulan lalu`,
  `kemarin`, `last month`, `yesterday`, ...) get an honest unsupported reply —
  only today is covered.
- **Pipeline:** 10 public RSS feeds (no keys) → 15 items/feed → 30-article sample
  → exact + near-dedupe → topic clustering → Meta rewrite in ARVI's own words
  with source links → 45-minute cache. Dead sources are skipped, never fatal.
- **Gallery:** the router sends the `{judul, ringkasan, sumber, tautan, gambar}`
  card array (`news_gallery`) to the HUD grid (image top, title/summary below,
  hover lift, default placeholder when a feed carries no image, `rel=noopener`
  source links); chat/voice stay at "Berikut adalah berita terkini."
- **Guardrails:** article content is UNTRUSTED (in-article instructions ignored);
  text-only path, no history writes, EXEC/tool tags never applied; memory-free.
- Examples: `berita hari ini` · `berita indonesia` · `world news today`.

---

*End of document. Every claim above traces to the cited code file;
when code changes, this document must follow the code (not vice versa).*
