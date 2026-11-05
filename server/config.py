import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Set, Dict, Any
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def _bersihkan_kunci(nilai):

    return (nilai or "").strip().strip("'").strip('"').strip()


META_API_KEY = _bersihkan_kunci(os.getenv("META_API_KEY"))
BASETEN_API_KEY = _bersihkan_kunci(os.getenv("BASETEN_API_KEY", ""))
ELEVENLABS_API_KEY = _bersihkan_kunci(os.getenv("ELEVENLABS_API_KEY", ""))
ELEVENLABS_VOICE_ID = _bersihkan_kunci(os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"))
ELEVENLABS_MODEL_ID = _bersihkan_kunci(os.getenv("ELEVENLABS_MODEL_ID", "eleven_v4"))


if META_API_KEY:
    if META_API_KEY.startswith("LLM|") and META_API_KEY.count("|") >= 2:
        print(f"[+] META_API_KEY loaded ({len(META_API_KEY)} chars, LLM|id|secret format OK).")
    else:
        print("[!] WARNING: suspicious META_API_KEY format "
              "(expected LLM|id|secret with pipe separators). The Muse engine may refuse the connection.")
else:
    print("[!] META_API_KEY is empty — Muse Spark 1.3 engine disabled.")
if BASETEN_API_KEY:
    print(f"[+] BASETEN_API_KEY loaded ({len(BASETEN_API_KEY)} chars).")
else:
    print("[!] BASETEN_API_KEY is empty — Vision + Baseten fallback disabled.")
if ELEVENLABS_API_KEY:
    print(f"[+] ELEVENLABS_API_KEY loaded ({len(ELEVENLABS_API_KEY)} chars).")
else:
    print("[!] ELEVENLABS_API_KEY is empty — ElevenLabs TTS disabled, HUD uses the browser voice.")
if ELEVENLABS_VOICE_ID:
    print(f"[+] ELEVENLABS_VOICE_ID loaded ({ELEVENLABS_VOICE_ID}).")
else:
    print("[!] ELEVENLABS_VOICE_ID is empty — set it in .env or keep the default.")

META_URL = "https://api.meta.ai/v1/responses"
BASETEN_URL = "https://inference.baseten.co/v1/chat/completions"

try:
    from elevenlabs.client import ElevenLabs
    _ELEVEN_SDK_TERSEDIA = True
except Exception:
    ElevenLabs = None
    _ELEVEN_SDK_TERSEDIA = False

try:
    import keyboard as _keyboard
    _KEYBOARD_TERSEDIA = True
except Exception:
    _keyboard = None
    _KEYBOARD_TERSEDIA = False


try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None


def aktifkan_dpi_awareness():

    try:
        import ctypes
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return False
        try:
            windll.shcore.SetProcessDpiAwareness(2)
            return True
        except Exception:
            try:
                windll.user32.SetProcessDPIAware()
                return True
            except Exception:
                return False
    except Exception:
        return False


DPI_AWARENESS_AKTIF = aktifkan_dpi_awareness()
if DPI_AWARENESS_AKTIF:
    print("[+] DPI awareness enabled (screenshot pixels match cursor pixels).")
else:
    print("[!] DPI awareness unavailable — screen/cursor sizes may differ "
          "under display scaling.")


hud_clients: Set = set()
node_clients: Set = set()


system_context: Dict[str, Any] = {
    "latest_telemetry": "Waiting for node sync...",
    "top_processes": "No process inspection data yet.",
    "last_ping": "Not tested yet."
}


async def _siar_ke_hud(pesan: dict) -> None:

    mentah = json.dumps(pesan)
    for hud in list(hud_clients):
        try:
            await hud.send_text(mentah)
        except Exception:
            continue
