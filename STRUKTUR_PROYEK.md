# Project Structure `arvi-os-dev`

This document maps every folder and file in the ARVI OS project.
Last updated: 4 November 2026 (REVISI UI/UX: physical CMD audit, dashboard
modals, news gallery, silent workspace).
Per-module technical detail: see `DOKUMEN_TEKNIS.md`.

## Directory Tree

```text
arvi-os-dev/
├── .env                        # Local API keys + secrets (NEVER commit)
├── .gitignore                  # .env, runtime JSONs, reports, caches
├── DOKUMEN_TEKNIS.md           # Full technical reference (architecture, API, protocol)
├── hud/                        # Browser HUD UI (served by the server, English UI)
│   ├── app.js                  # HUD brain: WS, bilingual STT/TTS, anti-echo, PTT, camera, QR,
│   │                           # dashboard modals, toasts
│   ├── index.html              # Main page: Baymax + panels + lockscreen + QR + modals
│   └── mobile-lens.html        # Phone PWA: walkie-talkie + dual-mode camera scan
├── KEMAMPUAN_ARVI.md           # Full skill, command & example list
├── nodes/
│   └── laptop_node.py          # Edge node: telemetry + INSPECT_CPU/PING (ws/node)
├── README.md                   # Description + quickstart
├── requirements.txt            # Python dependencies (pip install -r requirements.txt)
├── security/                   # Login gate + phone/node tokens
│   ├── __init__.py
│   ├── arvi_auth.py            # HMAC v1 session tokens (8-hour expiry)
│   ├── arvi_mobile.json        # Phone access token (sensitive, git-ignored)
│   ├── arvi_mobile.py          # Create/verify/revoke phone tokens (QR)
│   ├── arvi_node.json          # Edge-node PSK (sensitive, git-ignored)
│   ├── arvi_node.py            # Node PSK → /ws/node auth
│   ├── arvi_users.json         # Account hashes (sensitive, git-ignored)
│   └── arvi_users.py           # Owner setup + PBKDF2 login (200k iterations)
├── server/                     # Modular Meta Core (FastAPI :8080)
│   ├── __init__.py             # server.* package marker
│   ├── ai_engine.py            # Muse 1.3 + Baseten Open 1026, LLM tag parsers, autonomous agent
│   ├── arvi_kalibrasi_kursor.json # Stored cursor calibration (git-ignored)
│   ├── arvi_memory.json        # Permanent LTM memory (git-ignored)
│   ├── berita.py               # Daily news: RSS fetch, dedupe, clustering, Meta summary, gallery
│   ├── config.py               # Env/keys/URLs/SDK flags/runtime state + HUD broadcast
│   ├── kalibrasi_kursor.py      # Cursor calibration: detect, store, self-calibrate
│   ├── main.py                 # Slim router: REST endpoints + WS + re-export facade
│   ├── memory.py               # STM/LTM, background fact extraction, name/command normalization
│   ├── mobile_file.py          # Phone attachments: images/PDF/text decode + analysis
│   ├── os_control.py           # Windows control: apps/windows/in-app/input/media (EN/ID)
│   ├── proactive.py            # Reminders, morning briefing, CPU watch (EN/ID)
│   ├── sam31_cloud.py          # Meta SAM 3.1 segmentation client (octagons + cyan annotations)
│   ├── vision_engine.py        # Baseten Vision, screenshots, screen read/click, cyber-agent
│   └── voice_engine.py         # ElevenLabs TTS + global Ctrl+Alt PTT monitor
└── STRUKTUR_PROYEK.md          # This document
```

Note: metadata folders (`.git/`, `.hg/`, `.sl/`, `.eden/`, `.muse/`,
`.agents/`) are not drawn (VCS/agent tooling, not ARVI code).

## Notes per Section

### Project root
| File | Content |
|---|---|
| `.env` | API keys (Meta, Baseten, ElevenLabs) + `ARVI_MASTER_SECRET`. Not committed. |
| `.gitignore` | Keeps secrets, reports, and caches out of git. |
| `requirements.txt` | Pinned-by-name Python dependencies. |
| `DOKUMEN_TEKNIS.md` | Architecture, module breakdown, WS protocol, REST API, command flows, security, operations, troubleshooting. |
| `README.md` | Description + quickstart. |

### `hud/` — Browser user interface (English)
| File | Content |
|---|---|
| `index.html` | Login lockscreen, status header + Mobile QR, animated Baymax head (idle/speaking/listening/blink), fixed-height `dialogue-box`, command form + mic/AUTO/PTT, bottom-left LATENCY/ENGINE chips, Vision drawer (live feed + grounding + dynamic SAM model) & Workspace drawer, QR popover, cyber/AppSec/news dashboard modals, toast container. |
| `app.js` | WS + auth + ping/RTT, "Arvi" name normalization, ElevenLabs TTS + bilingual browser fallback (id-ID/en-US), hands-free STT + PTT + barge-in + echo filter, tactical voice (short confirmations read aloud), live camera preview + scan + grounding, engine badge, bilingual OS-intent mirror, dashboard renderers, toast + badge notifications. |
| `mobile-lens.html` | Dark phone PWA: text input + Send (photo→scan / text→command), walkie-talkie, 2-step scan, dual-mode camera (WebRTC → native fallback, downscaled), bilingual answer readout, `chrome://flags` hint. |

### `server/` — Modular FastAPI backend (100% Meta)
| File | Content |
|---|---|
| `main.py` | Slim router: FastAPI + CORS, REST (auth/HUD/stats/TTS/mobile), `/ws/hud` WS (pipeline: lockdown → agent → system/media → calibration → cyber → clipboard → threat-hunt → screen → in-app → OS → input → proactive → news → visual-follow-up → Muse) + `/ws/node`, proactive scheduler, `__main__` block. Re-exports every module symbol so `server.main.*` stays compatible (TestClient + mocks). Binds `0.0.0.0:8080`. |
| `config.py` | Import root: `.env`, API keys, engine URLs, defensive SDK flags, runtime registries (`hud_clients`, `node_clients`, `system_context`), `_siar_ke_hud()` helper. Imports no other server.* module (anti circular import). |
| `memory.py` | STM (20 messages) + JSON LTM, explicit facts (EN/ID: "my name is …"/"namaku …"), persona block, conversation-partner detection, background fact extraction every 10 interactions, Arvi-name + command-typo normalization, "Arvi" voice-prefix gate. |
| `ai_engine.py` | `query_arvi_cognitive` (Baseten Open 1026 → Muse 1.3 fallback), `[EXEC_KEY]`/```tool/`[EXEC_ACTION]` parsers, tactical replies, multi-step autonomous agent (lazy imports, no cycles). |
| `vision_engine.py` | `query_arvi_vision` (Baseten Vision), Meta SAM 3.1 cloud segmentation + single Baseten-BBox fallback (honest `model` field), screenshots, screen read/click, bilingual screen intents, follow-up visual questions, photo forensics + QR SOC + AppSec auditor. |
| `os_control.py` | `APP_DATABASE` whitelist (18 apps), focus-or-open, tab/browser/site/bookmark actions, mouse/keyboard, Win32 media keys, screenshots, physical CMD network audit demo, HUD window focus, bilingual EN/ID command parsers. |
| `voice_engine.py` | ElevenLabs synthesis (SDK + REST fallback), global Ctrl+Alt PTT monitor + paired speaker mute. Server STT disabled (HUD uses browser STT). |
| `proactive.py` | Scheduled reminders, morning briefing, telemetry CPU watch + 30-second background scheduler (EN/ID triggers). |
| `sam31_cloud.py` | Meta SAM 3.1 client (`/v1/responses`, model `sam-3.1`): concept/box prompts, token parser, 8-point octagon polygons + cyan annotations, always a valid dict. |
| `berita.py` | RSS fetch (10 sources, 2 scopes), exact+near dedupe, topic clustering, memory-free Meta summary, 45-minute cache, gallery card array (title/summary/source/link/thumbnail). |
| `kalibrasi_kursor.py` | Cursor calibration intents (auto/reset/manual offset), persistent store, guided self-calibration. |
| `mobile_file.py` | Phone attachment validation (images/PDF/text/code, 6 MB cap) + Vision/cognitive analysis. |
| `arvi_memory.json` | LTM: `profil_user {nama, preferensi, gaya_kerja}`, `fakta_penting[]` (max 100), `ringkasan_terakhir`, `interaksi`, reminders, briefing. Auto-created while the server runs. |
| `arvi_kalibrasi_kursor.json` | Stored cursor offset/scale. Auto-created on first calibration. |

### `security/` — Login gate + device tokens
| File | Content |
|---|---|
| `arvi_auth.py` | Create/verify `v1.<payload>.<hmac>` tokens from `ARVI_MASTER_SECRET` (claims sub/metode/peran/iat/exp). |
| `arvi_users.py` | First-account setup (owner, one-time) + PBKDF2 login (16 B salt, 6–200 char passwords, ≤40 char usernames). |
| `arvi_users.json` | Account data + password hashes. Sensitive, not committed. |
| `arvi_mobile.py` | Phone access tokens: create/verify/revoke; embedded in QR (`?t=`), sent via Bearer header. |
| `arvi_mobile.json` | Active phone token. Sensitive, not committed. |
| `arvi_node.py` | Edge-node PSK (auto-created); verified at the `/ws/node` gate. |
| `arvi_node.json` | Node PSK. Sensitive, not committed. |

### `nodes/` — Laptop edge node
| File | Content |
|---|---|
| `laptop_node.py` | WS client to `/ws/node`: sends `telemetry`, serves `INSPECT_CPU` (5 heaviest processes, 2-stage sampling) and `PING_NETWORK`. Run separately (optional, recommended). |

## Removed Files (Nov 2026)
- `baseten_test.py`, `test-gemini.py` — one-shot manual key-check scripts, unreferenced by any code/docs (key validation now lives in server startup logs).
- The ±4200-line `server/main.py` monolith was split into 12 modules + a slim router (Nov 2026 REVISI).
- Visual-identity prototype (`server/identity_engine.py`, `tests/test_identitas_visual.py`, `server/arvi_faces.json`, `server/faces/`) — rolled back; no face recognition in this repo.
- Non-Meta local segmentation (MobileSAM/FastSAM) — removed from runtime; segmentation is 100% Meta (SAM 3.1 Cloud → Muse Spark Open 1026 bbox).
- Public-push cleanup: the `tests/` suite (24 files) + `run_all_tests.py` +
  `test_report.txt`, internal session docs (`REVISI.md`, `HASIL_5_SPEK.md`,
  `HASIL_BERITA_SUARA_HANDSFREE.md`, `LAPORAN_REVISI_UI.md`,
  `DOKUMEN_UJI_ARVI.md`), and the `demo 1.txt` AppSec demo target.
