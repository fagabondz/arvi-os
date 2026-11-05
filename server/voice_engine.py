import asyncio
import re

import requests

from server.config import (_ELEVEN_SDK_TERSEDIA, _KEYBOARD_TERSEDIA,
                           _keyboard, _siar_ke_hud, ELEVENLABS_API_KEY,
                           ELEVENLABS_MODEL_ID, ELEVENLABS_VOICE_ID,
                           ElevenLabs)


def sintesis_suara_elevenlabs(teks: str, voice_id: str = "", model_id: str = "") -> bytes:

    bersih = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", teks or "")
    bersih = re.sub(r"`{1,3}(.*?)`{1,3}", "", bersih, flags=re.DOTALL)
    bersih = re.sub(r"[#>\-_]", " ", bersih)
    bersih = re.sub(r"\s+", " ", bersih).strip()
    if not bersih:
        raise RuntimeError("TTS text is empty after cleanup.")
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is not set in .env.")
    target_voice = (voice_id or ELEVENLABS_VOICE_ID).strip()
    target_model = (model_id or ELEVENLABS_MODEL_ID).strip()
    if not target_voice:
        raise RuntimeError("ELEVENLABS_VOICE_ID is empty.")
    if _ELEVEN_SDK_TERSEDIA and ElevenLabs is not None:
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        try:
            audio_gen = client.text_to_speech.convert(
                text=bersih[:2000], voice_id=target_voice,
                model_id=target_model, output_format="mp3_44100_128")
            audio_bytes = b"".join(chunk for chunk in audio_gen if chunk)
        except Exception as galat:

            if target_model != "eleven_multilingual_v2":
                try:
                    audio_gen = client.text_to_speech.convert(
                        text=bersih[:2000], voice_id=target_voice,
                        model_id="eleven_multilingual_v2",
                        output_format="mp3_44100_128")
                    audio_bytes = b"".join(chunk for chunk in audio_gen if chunk)
                except Exception as galat2:
                    raise RuntimeError(f"ElevenLabs SDK failed: {galat2}")
            else:
                raise RuntimeError(f"ElevenLabs SDK failed: {galat}")
        if not audio_bytes:
            raise RuntimeError("ElevenLabs SDK returned empty audio.")
        return audio_bytes

    try:
        res = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice}?output_format=mp3_44100_128",
            headers={"xi-api-key": ELEVENLABS_API_KEY,
                     "Content-Type": "application/json"},
            json={"text": bersih[:2000], "model_id": target_model}, timeout=30)
    except Exception as galat:
        raise RuntimeError(f"ElevenLabs REST failed: {galat}")
    if res.status_code != 200:
        raise RuntimeError(f"ElevenLabs REST status {res.status_code}.")
    if not res.content:
        raise RuntimeError("ElevenLabs REST returned empty audio.")
    return res.content


_ptt_loop = None
_ptt_terpasang = False
_ptt_tertahan = False
_ptt_sumber = None
_speaker_diredam_ptt = False


def _set_mute_speaker_windows(redam: bool) -> None:

    global _speaker_diredam_ptt
    if redam == _speaker_diredam_ptt:
        return
    try:
        import ctypes
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return
        windll.user32.keybd_event(0xAD, 0, 0, 0)
        windll.user32.keybd_event(0xAD, 0, 2, 0)
        _speaker_diredam_ptt = redam
    except Exception:
        pass


def _siar_ptt_threadsafe(tipe):

    global _ptt_tertahan
    if tipe == "ptt_start":
        if _ptt_tertahan:
            return
        _ptt_tertahan = True
    else:
        if not _ptt_tertahan:
            return
        _ptt_tertahan = False
    loop = _ptt_loop
    if loop is None:
        return
    try:
        loop.call_soon_threadsafe(_jadwal_siar_ptt, tipe)
    except Exception:
        pass


def _jadwal_siar_ptt(tipe):
    try:
        asyncio.ensure_future(_siar_ke_hud({"type": tipe}))
    except Exception:
        pass


def _ptt_ditekan(sumber):

    global _ptt_sumber
    if _ptt_tertahan:
        return
    _ptt_sumber = sumber
    _set_mute_speaker_windows(True)
    _siar_ptt_threadsafe("ptt_start")


def _ptt_dilepas(sumber):

    global _ptt_sumber
    if not _ptt_tertahan or _ptt_sumber != sumber:
        return
    _ptt_sumber = None
    _set_mute_speaker_windows(False)
    _siar_ptt_threadsafe("ptt_stop")


def _ctrl_alt_aktif():

    if _keyboard is None:
        return False
    try:
        ctrl = (_keyboard.is_pressed("ctrl")
                or _keyboard.is_pressed("left ctrl")
                or _keyboard.is_pressed("right ctrl"))
        alt = (_keyboard.is_pressed("alt")
               or _keyboard.is_pressed("left alt")
               or _keyboard.is_pressed("right alt"))
        return bool(ctrl and alt)
    except Exception:
        return False


def _mulai_monitor_ptt():

    global _ptt_terpasang, _ptt_loop
    if _ptt_terpasang or not _KEYBOARD_TERSEDIA or _keyboard is None:
        return
    try:
        _ptt_loop = asyncio.get_event_loop()

        def _ctrl_alt_turun(_e):
            if _ctrl_alt_aktif() and not _ptt_tertahan:
                _ptt_ditekan("ctrl_alt")

        def _ctrl_alt_naik(_e):
            if _ptt_tertahan and not _ctrl_alt_aktif():
                _ptt_dilepas("ctrl_alt")

        _keyboard.on_press_key("ctrl", _ctrl_alt_turun)
        _keyboard.on_press_key("alt", _ctrl_alt_turun)
        _keyboard.on_release_key("ctrl", _ctrl_alt_naik)
        _keyboard.on_release_key("alt", _ctrl_alt_naik)
        _ptt_terpasang = True
        print("[+] Global PTT shortcut active: Ctrl+Alt (hold to talk).")
    except Exception as galat:
        print(f"[!] Failed to install the PTT shortcut: {galat}")
