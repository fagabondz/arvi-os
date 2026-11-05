import asyncio
import base64
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import requests
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel
import os, sys
_ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if _ROOT_DIR not in sys.path: sys.path.insert(0, _ROOT_DIR)
os.environ["PYTHONPATH"] = _ROOT_DIR
from security import arvi_auth, arvi_mobile, arvi_node, arvi_users

from server import mobile_file as _mod_file
from server import proactive as _mod_proaktif
from server.config import (
    BASETEN_API_KEY, BASETEN_URL, ELEVENLABS_API_KEY, ELEVENLABS_MODEL_ID,
    ELEVENLABS_VOICE_ID, META_API_KEY, META_URL,
    _bersihkan_kunci, _ELEVEN_SDK_TERSEDIA, _KEYBOARD_TERSEDIA, _keyboard,
    _siar_ke_hud, ElevenLabs, hud_clients, ImageGrab,
    node_clients, system_context, aktifkan_dpi_awareness, DPI_AWARENESS_AKTIF,
)
from server.memory import (
    MEMORY_PATH, _blok_memori_untuk_persona, _buang_turn_terakhir,
    _butuh_telemetri, _ekstrak_fakta_latar, _instruksi_lawan_bicara,
    _KATA_KERJA_NORMAL, _memori_bawaan, _muat_memori, _normalisasi_kata_perintah,
    _PEMICU_INGAT, _rekam_riwayat, _simpan_fakta_eksplisit, _simpan_memori,
    _tambah_fakta, _VARIAN_SALAH_ARVI, conversation_history,
    last_vision_frame, memori_ltm, normalisasi_nama_arvi,
    PESAN_ULANGI_ARVI, saring_transkrip_suara,
)
from server.berita import (
    deteksi_intent_berita, jalankan_berita_terbaru, jalankan_galeri_berita,
    jawab_berita_kosong, jawab_rentang_tak_didukung,
)
from server.ai_engine import (
    _AKSI_AGEN_VALID, _ALAT_JSON_VALID, _balasan_taktis, _catat_hasil_eksekusi,
    _EXEC_KEY_MAKS_AKSI, _EXEC_KEY_VK, _FRASA_GAGAL_SISTEM, _inspeksi_cpu_agen,
    _jalankan_aksi_media, _jalankan_langkah_agen, _KATA_AKSI_AGEN,
    _KATA_HUBUNG_AGEN, _rencana_agen_muse, _RESPON_TAKTIS, _taktis_terakhir,
    _terapkan_exec_action, _terapkan_exec_key, _terapkan_tool_json,
    ambil_respon_taktis_singkat, bersihkan_output_soc,
    bersihkan_reasoning_trace, deteksi_dan_jalankan_agen_otonom,
    extract_baseten_message, query_arvi_cognitive, query_soc_evaluator,
    _PROMPT_SOC_ANALYST, _PROMPT_SOC_CLIPBOARD, _PROMPT_SOC_NETWORK,
)
from server.vision_engine import (
    _ambil_screenshot_b64, _bbox_dari_baseten, _bersihkan_target_layar,
    _FRASA_RUJUKAN_VISUAL,
    _KATA_GANTI_VISUAL, _KATA_TANYA, _KATA_VISUAL_LANGSUNG, _konteks_visual_terakhir,
    _koordinat_dari_vision,
    _PENGISI_TARGET_LAYAR, _pil_dari_b64, baca_layar_monitor,
    deteksi_intent_appsec, deteksi_intent_forensik, deteksi_intent_layar,
    deteksi_intent_qr, konversi_persen_ke_piksel, tambah_grid_koordinat,
    deteksi_tanya_visual_lanjutan, jalankan_audit_appsec_layar,
    jalankan_forensik_foto_layar,
    jalankan_segmentasi_meta, jalankan_soc_qr_layar, lihat_dan_klik_layar,
    query_arvi_vision, urai_vonis_appsec,
)
from server.os_control import (
    APP_DATABASE, _ALIAS_TOMBOL, _baca_url_address_bar, _BROWSER_KANONIS,
    _bersihkan_query_cari, _bersihkan_target_web, _browser_target,
    _cocok_web_database, _dapatkan_info_jendela_aktif, _domain_cocok,
    _ekstrak_host_url, _ekstrak_komposit_youtube_putar, _ekstrak_query_cari,
    _fokus_atau_buka, _fokus_jendela, _FRASA_PUTAR_KONTEKSTUAL, _frasa_utuh,
    _kanonis_target, _KATA_BUKA, _KATA_TUTUP, _MODIFIER_AMAN, _normalisasi_tombol,
    _pag, _perintah_buka_spotify, _PESAN_INSTALL_PAG, _PESAN_INSTALL_PYPERCLIP,
    _proses_berjalan, _psutil, _PSUTIL_TERSEDIA, _PYAUTOGUI_TERSEDIA,
    _simpan_screenshot_ke_pictures, _target_situs_ke_domain, _tekan_vk,
    _TOMBOL_AMAN, _user32, _VK_MEDIA, active_context_state, baca_clipboard,
    buka_url_di_chrome_aktif, cari_dan_putar_youtube,
    cari_kontekstual_di_layar_aktif, cari_url_bookmark_chrome,
    dapatkan_konteks_aktif, deteksi_dan_eksekusi_kontrol_sistem,
    deteksi_intent_aplikasi, deteksi_intent_clipboard, deteksi_intent_input,
    deteksi_intent_os, deteksi_intent_threat_hunt, deteksi_perintah_lockdown,
    dapatkan_geometri_layar_virtual, dapatkan_origin_layar_virtual,
    posisi_kursor_saat_ini,
    eksekusi_lockdown_darurat,
    execute_inapp_command, execute_input_command, execute_os_command,
    fokuskan_jendela_hud, jalankan_audit_koneksi_fisik,
    jalankan_threat_hunt_jaringan,
    putar_video_youtube_teratas, reset_konteks_aktif, set_konteks_aktif,
    tutup_tab_berdasarkan_domain, WEB_DATABASE,
)
from server.voice_engine import (
    _ctrl_alt_aktif, _jadwal_siar_ptt, _mulai_monitor_ptt, _ptt_dilepas,
    _ptt_ditekan, _ptt_loop, _ptt_sumber, _ptt_terpasang, _ptt_tertahan,
    _set_mute_speaker_windows, _siar_ptt_threadsafe, _speaker_diredam_ptt,
    sintesis_suara_elevenlabs,
)
from server.proactive import (
    _catat_cpu_telemetri, _CPU_AMBANG_MENIT, _CPU_AMBANG_PERSEN, _CPU_COOLDOWN_JAM,
    _cpu_riwayat, _cpu_tinggi_berkepanjangan, _loop_proaktif, _NAMA_BULAN, _NAMA_HARI,
    _peringatan_cpu_terakhir, _susun_briefing, _TUGAS_PROAKTIF, _urai_waktu_pengingat,
    atur_pengingat, daftar_pengingat, deteksi_perintah_briefing, deteksi_perintah_pengingat,
    hapus_pengingat,
)
from server.kalibrasi_kursor import (
    deteksi_intent_kalibrasi, jalankan_kalibrasi_kursor_otomatis,
    jawab_kalibrasi_gagal, jawab_kalibrasi_offset, jawab_kalibrasi_reset,
    jawab_kalibrasi_selesai, muat_kalibrasi_kursor, reset_kalibrasi_kursor,
    simpan_kalibrasi_kursor, terapkan_kalibrasi_kursor,
)

app = FastAPI(title="ARVI OS Meta Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sesi_ws: Dict[WebSocket, Any] = {}

WAKTU_START = time.time()
HUD_DIR = Path(__file__).resolve().parent.parent / "hud"


class LoginPassword(BaseModel):
    username: str
    password: str


class SetupPassword(BaseModel):
    username: str
    password: str


class MobileScan(BaseModel):
    image: str
    prompt: str = "Analyze the object in front of the camera, technically and briefly."
    sumber: str = ""
    final: bool = True


class MobileCommand(BaseModel):
    text: str = ""
    sumber: str = ""
    final: bool = True


class MobileFile(BaseModel):
    filename: str
    data_b64: str = ""
    prompt: str = ""
    sumber: str = ""
    final: bool = True


class TtsRequest(BaseModel):
    text: str
    voice_id: str = ""
    model_id: str = ""


class SttRequest(BaseModel):
    audio_b64: str
    mime_type: str = "audio/webm"


def _ip_lokal() -> str:

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    return "127.0.0.1"


def _token_bearer(request: Request) -> str:

    try:
        mentah = (request.headers.get("authorization") or "").strip()
    except Exception:
        return ""
    if mentah.lower().startswith("bearer "):
        return mentah[7:].strip()
    return ""


def _klaim_sesi_hud(request: Request):

    token = _token_bearer(request)
    if not token:
        return None
    try:
        return arvi_auth.verifikasi_token(token)
    except arvi_auth.AuthError:
        return None


def _wajib_hud_atau_hp(request: Request) -> str:

    if _klaim_sesi_hud(request) is not None:
        return "hud"
    if arvi_mobile.verifikasi_token_hp(_token_bearer(request)):
        return "hp"
    raise HTTPException(401, "A valid session (HUD) or phone token is required.")


def _wajib_sesi_hud(request: Request):

    klaim = _klaim_sesi_hud(request)
    if klaim is None:
        raise HTTPException(401, "HUD login required.")
    return klaim


def _bersihkan_telemetri(teks, batas=2000):

    bersih = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "",
                    str(teks or ""))
    bersih = "\n".join(line.strip() for line in bersih.splitlines())
    return bersih[:batas]


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/hud/index.html")


@app.get("/hud/index.html", include_in_schema=False)
async def hud_html():
    return FileResponse(HUD_DIR / "index.html", media_type="text/html")


@app.get("/hud/app.js", include_in_schema=False)
async def hud_js():
    return FileResponse(HUD_DIR / "app.js", media_type="application/javascript")


@app.get("/mobile-lens", include_in_schema=False)
async def mobile_lens():

    return FileResponse(HUD_DIR / "mobile-lens.html", media_type="text/html")


@app.get("/api/mobile-url")
async def api_mobile_url(request: Request):

    _wajib_sesi_hud(request)
    port = request.url.port or 8080
    token_hp = arvi_mobile.muat_atau_buat_token_hp()
    return {"ok": True,
            "url": f"http://{_ip_lokal()}:{port}/mobile-lens?t={token_hp}"}


@app.post("/api/mobile-scan")
async def api_mobile_scan(badan: MobileScan, request: Request):

    _wajib_hud_atau_hp(request)
    if not badan.image:
        raise HTTPException(422, "Field 'image' is required.")
    prompt_hp = normalisasi_nama_arvi(badan.prompt or "")

    if (badan.sumber or "") == "suara":
        _putusan_pindai = saring_transkrip_suara(prompt_hp, badan.final)
        if _putusan_pindai is None:
            await _siar_ke_hud({"type": "agent_log",
                                "message": "[VOICE] Transcript without Arvi prefix — dropped."})
            return {"ok": True, "text": ""}
        if _putusan_pindai.get("tak_jelas"):
            await _siar_ke_hud({"type": "arvi_response",
                                "text": PESAN_ULANGI_ARVI,
                                "engine": "MUSE SPARK 1.3"})
            return {"ok": True, "text": PESAN_ULANGI_ARVI}
    await _siar_ke_hud({"type": "mobile_user_echo", "text": prompt_hp,
                        "sumber": "hp"})
    await _siar_ke_hud({"type": "agent_log",
                        "message": "[MOBILE LENS] Photo received from phone. Meta SAM 3.1 + Vision in parallel..."})
    loop = asyncio.get_event_loop()
    hasil, sam_hp = await asyncio.gather(
        loop.run_in_executor(None, query_arvi_vision, badan.image, prompt_hp),
        loop.run_in_executor(None, jalankan_segmentasi_meta,
                             badan.image),
    )
    last_vision_frame["image"] = badan.image
    last_vision_frame["timestamp"] = time.time()
    _rekam_riwayat(f"[PHONE VISUAL SCAN] {prompt_hp}", hasil)
    await _siar_ke_hud({"type": "grounding_preview", "image": badan.image,
                        "target": "mobile lens", "sumber": "mobile"})
    await _siar_ke_hud({"type": "vision_response", "text": hasil, "sumber": "mobile",
                              "engine": "MUSE OPEN 1026 // VISION",
                              "sam": sam_hp})
    return {"ok": True, "text": hasil, "sam": sam_hp}


@app.post("/api/mobile-command")
async def api_mobile_command(badan: MobileCommand, request: Request):

    _wajib_hud_atau_hp(request)
    cmd = normalisasi_nama_arvi((badan.text or "").strip())
    if not cmd:
        raise HTTPException(422, "Field 'text' is required.")
    lower_cmd = cmd.lower()
    loop = asyncio.get_event_loop()

    async def _log(pesan):
        await _siar_ke_hud({"type": "agent_log", "message": pesan})

    async def _final(tipe, muatan, teks_balas):
        await _siar_ke_hud({"type": tipe, **muatan})
        return {"ok": True, "text": teks_balas}


    _suara_tak_jelas = False
    if (badan.sumber or "") == "suara":
        _putusan = saring_transkrip_suara(cmd, badan.final)
        if _putusan is None:
            await _log("[VOICE] Transcript without Arvi prefix — dropped.")
            return {"ok": True, "text": ""}
        _suara_tak_jelas = bool(_putusan.get("tak_jelas"))
    await _log(f"[MOBILE CMD] \"{cmd}\"")
    await _siar_ke_hud({"type": "mobile_user_echo", "text": cmd,
                        "sumber": "hp"})
    if _suara_tak_jelas:
        return await _final("arvi_response",
                            {"text": PESAN_ULANGI_ARVI,
                             "engine": "MUSE SPARK 1.3"},
                            PESAN_ULANGI_ARVI)

    if deteksi_perintah_lockdown(cmd):
        _hasil_lockdown = eksekusi_lockdown_darurat()
        await _log(f"[LOCKDOWN] {_hasil_lockdown}")
        _tampil_lockdown = _balasan_taktis(_hasil_lockdown)
        return await _final("system_response", {"message": _tampil_lockdown},
                            _tampil_lockdown)

    _pratinjau_hp = {}
    _hasil_sistem = deteksi_dan_eksekusi_kontrol_sistem(cmd, _pratinjau_hp)
    if _hasil_sistem is not None:
        await _log(f"[SYSTEM CONTROL] {_hasil_sistem}")
        if _pratinjau_hp.get("image"):
            await _siar_ke_hud({"type": "grounding_preview",
                                "image": _pratinjau_hp["image"],
                                "target": "screenshot",
                                "sumber": "screenshot"})
        _tampil_sistem = _balasan_taktis(_hasil_sistem)
        return await _final("system_response", {"message": _tampil_sistem},
                            _tampil_sistem)


    _intent_kal = deteksi_intent_kalibrasi(cmd)
    if _intent_kal is not None:
        _bahasa_kal = _intent_kal["bahasa"]
        if _intent_kal["jenis"] == "reset":
            reset_kalibrasi_kursor()
            _hasil_kal = jawab_kalibrasi_reset(_bahasa_kal)
            await _log(f"[CALIBRATION] {_hasil_kal}")
            return await _final("system_response", {"message": _hasil_kal},
                                _hasil_kal)
        if _intent_kal["jenis"] == "offset_manual":
            _kal_aktif = muat_kalibrasi_kursor()
            if _intent_kal["mode_set"]:
                _ox_baru, _oy_baru = _intent_kal["dx"], _intent_kal["dy"]
            else:
                _ox_baru = _kal_aktif["offset_x"] + _intent_kal["dx"]
                _oy_baru = _kal_aktif["offset_y"] + _intent_kal["dy"]
            _tersimpan_kal = simpan_kalibrasi_kursor(
                _ox_baru, _oy_baru, _kal_aktif["scale_x"], _kal_aktif["scale_y"])
            if _tersimpan_kal is None:
                _hasil_kal = jawab_kalibrasi_gagal(_bahasa_kal)
            else:
                _hasil_kal = jawab_kalibrasi_offset(
                    _bahasa_kal, _tersimpan_kal["offset_x"],
                    _tersimpan_kal["offset_y"])
            await _log(f"[CALIBRATION] {_hasil_kal}")
            return await _final("system_response", {"message": _hasil_kal},
                                _hasil_kal)
        await _log("[CALIBRATION] Drawing target markers for self-calibration...")
        _pratinjau_kal = {}
        _hasil_kal = await loop.run_in_executor(
            None, jalankan_kalibrasi_kursor_otomatis, _bahasa_kal,
            _pratinjau_kal)
        if _pratinjau_kal.get("image"):
            await _siar_ke_hud({"type": "grounding_preview",
                                "image": _pratinjau_kal["image"],
                                "target": _pratinjau_kal.get("target", ""),
                                "sumber": "kalibrasi"})
        return await _final("vision_response",
                            {"text": _hasil_kal, "sumber": "kalibrasi",
                             "engine": "MUSE OPEN 1026 // VISION"}, _hasil_kal)

    _bahasa_forensik = deteksi_intent_forensik(cmd)
    if _bahasa_forensik is not None:
        await _log("[FORENSICS] Localizing the on-screen photo...")
        _pratinjau_forensik = {}
        hasil = await loop.run_in_executor(
            None, jalankan_forensik_foto_layar, _bahasa_forensik,
            _pratinjau_forensik)
        if _pratinjau_forensik.get("image"):
            await _siar_ke_hud({"type": "grounding_preview",
                                "image": _pratinjau_forensik["image"],
                                "target": "foto terdeteksi",
                                "sumber": "forensik"})
        return await _final("vision_response",
                            {"text": hasil, "sumber": "forensik",
                             "engine": "MUSE OPEN 1026 // VISION"}, hasil)
    _bahasa_qr = deteksi_intent_qr(cmd)
    if _bahasa_qr is not None:
        await _log("[SOC QR] Decoding the on-screen QR code...")
        _pratinjau_qr = {}
        hasil = await loop.run_in_executor(
            None, jalankan_soc_qr_layar, _bahasa_qr, _pratinjau_qr)
        if _pratinjau_qr.get("image"):
            await _siar_ke_hud({"type": "grounding_preview",
                                "image": _pratinjau_qr["image"],
                                "target": _pratinjau_qr.get("target", ""),
                                "sumber": "qr"})
        return await _final("vision_response",
                            {"text": hasil, "sumber": "qr",
                             "engine": "MUSE SPARK 1.3"}, hasil)

    _bahasa_appsec = deteksi_intent_appsec(cmd)
    if _bahasa_appsec is not None:
        await _log("[APPSEC] Auditing code on screen...")
        _pratinjau_appsec = {}
        hasil_appsec = await loop.run_in_executor(
            None, jalankan_audit_appsec_layar, _bahasa_appsec,
            _pratinjau_appsec)
        try:
            fokuskan_jendela_hud()
        except Exception:
            pass
        _vonis_appsec = urai_vonis_appsec(hasil_appsec)
        if _vonis_appsec["status"] == "ERROR":
            return await _final("vision_response",
                                {"text": hasil_appsec, "sumber": "appsec",
                                 "engine": "MUSE OPEN 1026 // VISION"},
                                hasil_appsec)
        await _siar_ke_hud({"type": "appsec_panel",
                            "image": _pratinjau_appsec.get("image") or "",
                            "status": _vonis_appsec["status"],
                            "detail": _vonis_appsec["detail"],
                            "engine": "MUSE OPEN 1026 // VISION"})
        _pendek_appsec = (
            "Audit complete."
            if str(_bahasa_appsec).lower().startswith("en")
            else "Audit selesai.")
        return await _final("vision_response",
                            {"text": _pendek_appsec, "sumber": "appsec",
                             "engine": "MUSE OPEN 1026 // VISION"},
                            _pendek_appsec)

    _bahasa_clipboard = deteksi_intent_clipboard(cmd)
    if _bahasa_clipboard is not None:
        await _log("[CLIPBOARD AUDIT] Reading clipboard...")
        _isi_clipboard = baca_clipboard()
        if _isi_clipboard == _PESAN_INSTALL_PYPERCLIP:
            _hasil_clipboard = _isi_clipboard
        elif not _isi_clipboard.strip():
            _hasil_clipboard = "Clipboard kosong."
        else:
            _hasil_clipboard = await loop.run_in_executor(
                None, query_soc_evaluator, _isi_clipboard,
                _bahasa_clipboard, _PROMPT_SOC_CLIPBOARD)
        return await _final("vision_response",
                            {"text": _hasil_clipboard, "sumber": "clipboard",
                             "engine": "MUSE SPARK 1.3"}, _hasil_clipboard)

    _bahasa_threat = deteksi_intent_threat_hunt(cmd)
    if _bahasa_threat is not None:
        await _log("[NETSCAN] Opening a live CMD audit window "
                   "(ping / tracert / netstat)...")
        hasil_threat = await loop.run_in_executor(
            None, jalankan_audit_koneksi_fisik, _bahasa_threat)
        _kon_threat = hasil_threat.get("koneksi") or {}
        _jml_koneksi = _kon_threat.get("total", 0)
        _jml_tanda = len(hasil_threat.get("temuan") or [])
        await _log(f"[NETSCAN] Audit done: {_jml_koneksi} connections, "
                   f"{_jml_tanda} flagged. Dashboard sent to HUD.")
        await _siar_ke_hud({"type": "netscan_panel",
                            "ping": hasil_threat.get("ping") or {},
                            "tracert": hasil_threat.get("tracert") or [],
                            "koneksi": _kon_threat,
                            "vonis": hasil_threat.get("vonis") or "",
                            "galat": hasil_threat.get("galat") or "",
                            "demo": bool(hasil_threat.get("demo_terlihat")),
                            "engine": "MUSE SPARK 1.3"})
        if str(_bahasa_threat).lower().startswith("en"):
            _vonis = (f"Network audit done. {_jml_koneksi} external "
                      f"connections, {_jml_tanda} flagged. "
                      "Details are on the dashboard.")
        else:
            _vonis = (f"Audit jaringan selesai. {_jml_koneksi} koneksi "
                      f"eksternal, {_jml_tanda} ditandai. "
                      "Detailnya ada di dashboard.")
        return await _final("vision_response",
                            {"text": _vonis, "sumber": "network",
                             "engine": "MUSE SPARK 1.3"}, _vonis)

    intent_layar = deteksi_intent_layar(cmd)
    if intent_layar is not None:
        if intent_layar["jenis"] == "baca":
            await _log("[SCREEN VISION] Capturing the monitor screen...")
            _pratinjau_layar = {}
            hasil = await loop.run_in_executor(
                None, baca_layar_monitor, intent_layar["pertanyaan"],
                _pratinjau_layar)
            if _pratinjau_layar.get("image"):
                await _siar_ke_hud({"type": "grounding_preview",
                                    "image": _pratinjau_layar["image"],
                                    "target": "layar monitor",
                                    "sumber": "layar"})
            return await _final("vision_response",
                                {"text": hasil, "sumber": "layar",
                                 "engine": "MUSE OPEN 1026 // VISION"}, hasil)
        if intent_layar["jenis"] == "buka_dan_klik":
            hasil_buka = execute_os_command(intent_layar["app"], "buka")
            await _log(f"[SCREEN VISION] {hasil_buka} Waiting for the window...")
            await asyncio.sleep(2.0)
            hasil = await loop.run_in_executor(
                None, lihat_dan_klik_layar, intent_layar["target"])
        else:
            await _log(f"[SCREEN VISION] Looking for '{intent_layar['target']}' on screen...")
            hasil = await loop.run_in_executor(
                None, lihat_dan_klik_layar, intent_layar["target"])
        await _log(f"[SCREEN VISION] {hasil}")
        return await _final("system_response", {"message": hasil}, hasil)

    intent_app = deteksi_intent_aplikasi(cmd)
    if intent_app is not None:
        hasil = await loop.run_in_executor(None, execute_inapp_command, intent_app)
        await _log(f"[IN-APP] {hasil}")
        tampil = _balasan_taktis(hasil)
        return await _final("system_response", {"message": tampil}, tampil)

    intent_os = deteksi_intent_os(cmd)
    if intent_os is not None:
        hasil = execute_os_command(intent_os["target"], intent_os["aksi"])
        _tampil_os = _balasan_taktis(hasil)
        await _log(f"[OS CONTROL] {hasil}")
        return await _final("system_response", {"message": _tampil_os},
                            _tampil_os)

    intent_in = deteksi_intent_input(cmd)
    if intent_in is not None:
        hasil = await loop.run_in_executor(None, execute_input_command,
                                           intent_in["command"], intent_in["params"])
        await _log(f"[INPUT CONTROL] {hasil}")
        return await _final("system_response", {"message": hasil}, hasil)

    _hasil_proaktif = (deteksi_perintah_pengingat(cmd)
                       or deteksi_perintah_briefing(cmd))
    if _hasil_proaktif is not None:
        await _log(f"[PROACTIVE] {_hasil_proaktif}")
        return await _final("system_response", {"message": _hasil_proaktif},
                            _hasil_proaktif)

    _intent_berita = deteksi_intent_berita(cmd)
    if _intent_berita is not None:
        if "tak_didukung" in _intent_berita:
            _hasil_berita = jawab_rentang_tak_didukung(_intent_berita["bahasa"])
        else:
            await _log("[NEWS] Fetching today's headlines...")
            _galeri_berita = await loop.run_in_executor(
                None, jalankan_galeri_berita, _intent_berita["cakupan"],
                _intent_berita["bahasa"])
            if _galeri_berita.get("artikel"):
                await _siar_ke_hud({"type": "news_gallery",
                                    "artikel": _galeri_berita["artikel"],
                                    "cakupan": _galeri_berita.get("cakupan",
                                                                  ""),
                                    "bahasa": _galeri_berita.get("bahasa",
                                                                 ""),
                                    "engine": "MUSE SPARK 1.3"})
                if str(_intent_berita["bahasa"]).lower().startswith("en"):
                    _hasil_berita = "Here is the latest news."
                else:
                    _hasil_berita = "Berikut adalah berita terkini."
            else:
                _hasil_berita = _galeri_berita.get("teks") or ""
        return await _final("arvi_response",
                            {"text": _hasil_berita,
                             "engine": "MUSE SPARK 1.3"}, _hasil_berita)

    if deteksi_tanya_visual_lanjutan(cmd):
        _tanya = cmd
        _konteks = _konteks_visual_terakhir()
        _prompt = _tanya + (f"\n\nPrevious identification context: {_konteks}\n"
                            "Answer the question above for that same object."
                            if _konteks else "")
        await _log("[OPTICAL CORTEX] Follow-up question — reusing the last visual frame...")
        hasil = await loop.run_in_executor(None, query_arvi_vision,
                                           last_vision_frame["image"], _prompt)
        _rekam_riwayat(f"[FOLLOW-UP VISUAL] {_tanya}", hasil)
        return await _final("vision_response",
                            {"text": hasil, "sumber": "lanjutan",
                             "engine": "MUSE OPEN 1026 // VISION"}, hasil)

    if any(k in lower_cmd for k in ["cpu", "proses", "process", "berat", "ram",
                                    "hardware", "sistem", "status"]):
        if node_clients:
            for node_ws in list(node_clients):
                try:
                    await node_ws.send_text(json.dumps({"type": "INSPECT_CPU"}))
                except Exception:
                    continue
            await asyncio.sleep(1.2)
            await _log("[CLOSED-LOOP] Fresh CPU sample received from node.")
    if any(k in lower_cmd for k in ["ping", "jaringan", "network", "internet", "koneksi"]):
        if node_clients:
            for node_ws in list(node_clients):
                try:
                    await node_ws.send_text(json.dumps({"type": "PING_NETWORK",
                                                       "host": "8.8.8.8"}))
                except Exception:
                    continue
            await asyncio.sleep(0.8)
    await _log("[INFERENCE] Synthesizing the response with live telemetry...")
    hasil = await loop.run_in_executor(None, query_arvi_cognitive, cmd)
    if "[ABAIKAN_OBROLAN_LAIN]" in (hasil or ""):
        _buang_turn_terakhir(cmd)
        await _log("[LISTENER] Voice detected as a side conversation — ARVI stays quiet.")
        return {"ok": True,
                "text": "ARVI stays quiet — side conversation detected."}
    hasil, _log_exec_hp = _terapkan_exec_key(hasil)
    hasil, _log_alat_hp = _terapkan_tool_json(hasil)
    hasil, _log_tindak_hp = _terapkan_exec_action(hasil)
    for _log_aksi in (_log_exec_hp, _log_alat_hp, _log_tindak_hp):
        if _log_aksi:
            _catat_hasil_eksekusi(_log_aksi)
            await _log(_log_aksi)
    return await _final("arvi_response", {"text": hasil, "engine": "MUSE SPARK 1.3"},
                        hasil)


@app.post("/api/mobile-file")
async def api_mobile_file(badan: MobileFile, request: Request):

    _wajib_hud_atau_hp(request)
    nama = (badan.filename or "").strip()
    instruksi = normalisasi_nama_arvi((badan.prompt or "").strip())


    if (badan.sumber or "") == "suara":
        _putusan_berkas = saring_transkrip_suara(instruksi, badan.final)
        if _putusan_berkas is None:
            await _siar_ke_hud({"type": "agent_log",
                                "message": "[VOICE] Transcript without Arvi prefix — dropped."})
            return {"ok": True, "text": ""}
        if _putusan_berkas.get("tak_jelas"):
            await _siar_ke_hud({"type": "arvi_response",
                                "text": PESAN_ULANGI_ARVI,
                                "engine": "MUSE SPARK 1.3"})
            return {"ok": True, "text": PESAN_ULANGI_ARVI}
    try:
        jenis, raw = _mod_file.decode_file_hp(badan.filename, badan.data_b64)
    except ValueError as galat:
        raise HTTPException(422, str(galat))
    loop = asyncio.get_event_loop()
    await _siar_ke_hud({"type": "mobile_user_echo",
                        "text": f"📎 {nama}"
                        + (f" — {instruksi}" if instruksi else ""),
                        "sumber": "hp"})
    await _siar_ke_hud({"type": "agent_log",
                        "message": f"[MOBILE FILE] {nama} ({jenis}, "
                        f"{len(raw)} bytes). Analyzing..."})
    if jenis == "gambar":
        data_url = _mod_file.data_url_dari_gambar(raw, nama)
        prompt_hp = instruksi or "Analyze this image briefly."
        hasil, sam_hp = await asyncio.gather(
            loop.run_in_executor(None, query_arvi_vision, data_url,
                                 prompt_hp),
            loop.run_in_executor(None, jalankan_segmentasi_meta, data_url),
        )
        last_vision_frame["image"] = data_url
        last_vision_frame["timestamp"] = time.time()
        _rekam_riwayat(f"[PHONE FILE SCAN] {nama}: {prompt_hp}", hasil)
        await _siar_ke_hud({"type": "grounding_preview", "image": data_url,
                            "target": nama[:48], "sumber": "mobile"})
        await _siar_ke_hud({"type": "vision_response", "text": hasil,
                            "sumber": "mobile",
                            "engine": "MUSE OPEN 1026 // VISION",
                            "sam": sam_hp})
        return {"ok": True, "text": hasil, "sam": sam_hp}
    try:
        hasil = await loop.run_in_executor(
            None, _mod_file.proses_dokumen_hp, jenis, nama, raw, instruksi)
    except ValueError as galat:
        raise HTTPException(422, str(galat))
    _rekam_riwayat(f"[PHONE FILE] {nama}: {instruksi or '(analisis)'}",
                   hasil)
    await _siar_ke_hud({"type": "arvi_response", "text": hasil,
                        "engine": "MUSE SPARK 1.3"})
    return {"ok": True, "text": hasil}


@app.post("/api/tts")
async def api_tts(badan: TtsRequest, request: Request):

    _wajib_hud_atau_hp(request)
    loop = asyncio.get_event_loop()
    try:
        audio_bytes = await loop.run_in_executor(
            None, sintesis_suara_elevenlabs, badan.text,
            badan.voice_id, badan.model_id)
    except Exception as galat:
        raise HTTPException(503, {"status": "TTS_GAGAL", "pesan": str(galat)})
    return Response(content=audio_bytes, media_type="audio/mpeg")


@app.post("/api/stt")
async def api_stt(badan: SttRequest, request: Request):

    _wajib_hud_atau_hp(request)
    if not (badan.audio_b64 or "").strip():
        raise HTTPException(422, "Field 'audio_b64' is required.")
    raise HTTPException(501, {
        "status": "STT_DISABLED",
        "message": ("Server transcription is disabled on the Meta-only stack. "
                    "Use the browser speech recognizer instead.")})


@app.get("/api/stats")
async def api_stats():
    from datetime import datetime, timezone
    return {"ok": True, "node_aktif": len(node_clients), "hud_terhubung": len(hud_clients),
            "waktu_server": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "uptime_detik": int(time.time() - WAKTU_START)}


@app.get("/auth/status")
async def auth_status():

    try:
        operator = arvi_users.daftar_pengguna()
    except arvi_users.UsersError:
        operator = []
    return {"ok": True, "butuh_setup": not operator, "operator": operator}


@app.post("/auth/setup/password")
async def setup_password(badan: SetupPassword):

    try:
        rekam = arvi_users.buat_pengguna_pertama(badan.username, badan.password)
    except ValueError as galat:
        raise HTTPException(422, str(galat))
    except FileExistsError:
        raise HTTPException(403, {"status": "SETUP_TERTUTUP",
                                  "pesan": "Account already exists; log in with it."})
    except arvi_users.UsersError as galat:
        raise HTTPException(500, {"status": "AKUN_GALAT", "pesan": str(galat)})
    token = arvi_auth.buat_token(rekam["username"], "password", peran="pemilik")
    return {"ok": True, "token": token, "pemilik": rekam["username"],
            "peran": "pemilik", "metode": "password"}


@app.post("/auth/login")
async def login_password(badan: LoginPassword):

    try:
        rekam = arvi_users.verifikasi(badan.username, badan.password)
    except arvi_users.LoginGagalError:
        raise HTTPException(401, {"status": "OTENTIKASI_GAGAL",
                                  "alasan": "username_atau_sandi_salah"})
    except arvi_users.UsersError as galat:
        raise HTTPException(500, {"status": "AKUN_GALAT", "pesan": str(galat)})
    token = arvi_auth.buat_token(rekam["username"], "password",
                                 peran=rekam["peran"])
    return {"ok": True, "token": token, "pemilik": rekam["username"],
            "peran": rekam["peran"], "metode": "password"}


@app.post("/auth/mobile/putar")
async def putar_token_hp(request: Request):

    _wajib_sesi_hud(request)
    try:
        arvi_mobile.cabut_token_hp()
        token_baru = arvi_mobile.buat_token_hp()
    except arvi_mobile.MobileError as galat:
        raise HTTPException(500, {"status": "TOKEN_HP_GALAT",
                                  "pesan": str(galat)})
    port = request.url.port or 8080
    return {"ok": True,
            "url": f"http://{_ip_lokal()}:{port}/mobile-lens?t={token_baru}"}


@app.websocket("/ws/hud")
async def websocket_hud_endpoint(websocket: WebSocket):
    await websocket.accept()


    print("[+] HUD connected to ARVI Meta Core (auth pending)")

    try:
        await websocket.send_text(json.dumps({
            "type": "agent_log",
            "message": "[CORE] Meta Core online (Muse Spark 1.3 + Baseten Muse Spark Open 1026)."
        }))


        try:
            pertama = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            data_awal = json.loads(pertama)
        except (asyncio.TimeoutError, ValueError):
            data_awal = {}
        klaim = None
        if data_awal.get("type") == "auth":
            try:
                klaim = arvi_auth.verifikasi_token(data_awal.get("token", ""))
            except arvi_auth.AuthError:
                klaim = None
        if klaim is None:
            await websocket.send_text(json.dumps({"type": "auth_failed"}))
            await websocket.close()
            return
        hud_clients.add(websocket)
        sesi_ws[websocket] = klaim
        await websocket.send_text(json.dumps({"type": "auth_ok", "pemilik": klaim["sub"],
                                              "metode": klaim.get("metode", "")}))
        _mulai_monitor_ptt()

        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "t": data.get("t"),
                                                      "waktu_server": time.time()}))
                continue
            if sesi_ws.get(websocket) is None:
                await websocket.send_text(json.dumps({"type": "auth_required"}))
                continue


            if msg_type == "user_command":
                cmd = normalisasi_nama_arvi(data.get("command", ""))
                lower_cmd = cmd.lower()


                if (data.get("sumber") or "") == "suara":
                    putusan_suara = saring_transkrip_suara(
                        cmd, data.get("final", True))
                    if putusan_suara is None:
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": "[VOICE] Transcript without Arvi prefix — dropped."
                        }))
                        continue
                    if putusan_suara.get("tak_jelas"):
                        await websocket.send_text(json.dumps({
                            "type": "arvi_response",
                            "text": PESAN_ULANGI_ARVI,
                            "engine": "MUSE SPARK 1.3"
                        }))
                        continue


                if deteksi_perintah_lockdown(cmd):
                    hasil_lockdown = eksekusi_lockdown_darurat()
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[LOCKDOWN] {hasil_lockdown}"
                    }))
                    await websocket.send_text(json.dumps({
                        "type": "system_response",
                        "message": _balasan_taktis(hasil_lockdown)
                    }))
                    continue


                if await deteksi_dan_jalankan_agen_otonom(cmd, websocket):
                    continue


                pratinjau_sistem = {}
                hasil_sistem = deteksi_dan_eksekusi_kontrol_sistem(
                    cmd, pratinjau_sistem)
                if hasil_sistem is not None:
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[SYSTEM CONTROL] {hasil_sistem}"
                    }))
                    if pratinjau_sistem.get("image"):
                        await websocket.send_text(json.dumps({
                            "type": "grounding_preview",
                            "image": pratinjau_sistem["image"],
                            "target": "screenshot",
                            "sumber": "screenshot"
                        }))
                    await websocket.send_text(json.dumps({
                        "type": "system_response",
                        "message": _balasan_taktis(hasil_sistem)
                    }))
                    continue


                intent_kalibrasi = deteksi_intent_kalibrasi(cmd)
                if intent_kalibrasi is not None:
                    bahasa_kal = intent_kalibrasi["bahasa"]
                    if intent_kalibrasi["jenis"] == "reset":
                        reset_kalibrasi_kursor()
                        hasil_kal = jawab_kalibrasi_reset(bahasa_kal)
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": f"[CALIBRATION] {hasil_kal}"
                        }))
                        await websocket.send_text(json.dumps({
                            "type": "system_response",
                            "message": hasil_kal
                        }))
                        continue
                    if intent_kalibrasi["jenis"] == "offset_manual":
                        kal_aktif = muat_kalibrasi_kursor()
                        if intent_kalibrasi["mode_set"]:
                            ox_baru = intent_kalibrasi["dx"]
                            oy_baru = intent_kalibrasi["dy"]
                        else:
                            ox_baru = kal_aktif["offset_x"] + intent_kalibrasi["dx"]
                            oy_baru = kal_aktif["offset_y"] + intent_kalibrasi["dy"]
                        tersimpan_kal = simpan_kalibrasi_kursor(
                            ox_baru, oy_baru, kal_aktif["scale_x"],
                            kal_aktif["scale_y"])
                        if tersimpan_kal is None:
                            hasil_kal = jawab_kalibrasi_gagal(bahasa_kal)
                        else:
                            hasil_kal = jawab_kalibrasi_offset(
                                bahasa_kal, tersimpan_kal["offset_x"],
                                tersimpan_kal["offset_y"])
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": f"[CALIBRATION] {hasil_kal}"
                        }))
                        await websocket.send_text(json.dumps({
                            "type": "system_response",
                            "message": hasil_kal
                        }))
                        continue
                    loop_kal = asyncio.get_event_loop()
                    pratinjau_kal = {}
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[CALIBRATION] Drawing target markers for self-calibration..."
                    }))
                    hasil_kal = await loop_kal.run_in_executor(
                        None, jalankan_kalibrasi_kursor_otomatis, bahasa_kal,
                        pratinjau_kal)
                    if pratinjau_kal.get("image"):
                        await websocket.send_text(json.dumps({
                            "type": "grounding_preview",
                            "image": pratinjau_kal["image"],
                            "target": pratinjau_kal.get("target", ""),
                            "sumber": "kalibrasi",
                            "x": 0,
                            "y": 0
                        }))
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": hasil_kal,
                        "sumber": "kalibrasi",
                        "engine": "MUSE OPEN 1026 // VISION"
                    }))
                    continue


                bahasa_forensik = deteksi_intent_forensik(cmd)
                if bahasa_forensik is not None:
                    loop_forensik = asyncio.get_event_loop()
                    pratinjau_forensik = {}
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[FORENSICS] Localizing the on-screen photo..."
                    }))
                    hasil_forensik = await loop_forensik.run_in_executor(
                        None, jalankan_forensik_foto_layar, bahasa_forensik,
                        pratinjau_forensik)
                    if pratinjau_forensik.get("image"):
                        await websocket.send_text(json.dumps({
                            "type": "grounding_preview",
                            "image": pratinjau_forensik["image"],
                            "target": pratinjau_forensik.get("target", ""),
                            "sumber": "forensik",
                            "x": 0,
                            "y": 0
                        }))
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": hasil_forensik,
                        "sumber": "forensik",
                        "engine": "MUSE OPEN 1026 // VISION"
                    }))
                    continue
                bahasa_qr = deteksi_intent_qr(cmd)
                if bahasa_qr is not None:
                    loop_qr = asyncio.get_event_loop()
                    pratinjau_qr = {}
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[SOC QR] Decoding the on-screen QR code..."
                    }))
                    hasil_qr = await loop_qr.run_in_executor(
                        None, jalankan_soc_qr_layar, bahasa_qr, pratinjau_qr)
                    if pratinjau_qr.get("image"):
                        await websocket.send_text(json.dumps({
                            "type": "grounding_preview",
                            "image": pratinjau_qr["image"],
                            "target": pratinjau_qr.get("target", ""),
                            "sumber": "qr",
                            "x": 0,
                            "y": 0
                        }))
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": hasil_qr,
                        "sumber": "qr",
                        "engine": "MUSE SPARK 1.3"
                    }))
                    continue
                bahasa_appsec = deteksi_intent_appsec(cmd)
                if bahasa_appsec is not None:
                    loop_appsec = asyncio.get_event_loop()
                    pratinjau_appsec = {}
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[APPSEC] Auditing code on screen..."
                    }))
                    hasil_appsec = await loop_appsec.run_in_executor(
                        None, jalankan_audit_appsec_layar, bahasa_appsec,
                        pratinjau_appsec)


                    try:
                        fokuskan_jendela_hud()
                    except Exception:
                        pass
                    vonis_appsec = urai_vonis_appsec(hasil_appsec)
                    if vonis_appsec["status"] == "ERROR":

                        await websocket.send_text(json.dumps({
                            "type": "vision_response",
                            "text": hasil_appsec,
                            "sumber": "appsec",
                            "engine": "MUSE OPEN 1026 // VISION"
                        }))
                        continue
                    await websocket.send_text(json.dumps({
                        "type": "appsec_panel",
                        "image": pratinjau_appsec.get("image") or "",
                        "status": vonis_appsec["status"],
                        "detail": vonis_appsec["detail"],
                        "engine": "MUSE OPEN 1026 // VISION"
                    }))
                    pendek_appsec = (
                        "Audit complete."
                        if str(bahasa_appsec).lower().startswith("en")
                        else "Audit selesai.")
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": pendek_appsec,
                        "sumber": "appsec",
                        "engine": "MUSE OPEN 1026 // VISION"
                    }))
                    continue


                bahasa_clipboard = deteksi_intent_clipboard(cmd)
                if bahasa_clipboard is not None:
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[CLIPBOARD AUDIT] Reading clipboard..."
                    }))
                    isi_clipboard = baca_clipboard()
                    if isi_clipboard == _PESAN_INSTALL_PYPERCLIP:
                        hasil_clipboard = isi_clipboard
                    elif not isi_clipboard.strip():
                        hasil_clipboard = "Clipboard kosong."
                    else:
                        loop_clipboard = asyncio.get_event_loop()
                        hasil_clipboard = await loop_clipboard.run_in_executor(
                            None, query_soc_evaluator, isi_clipboard,
                            bahasa_clipboard, _PROMPT_SOC_CLIPBOARD)
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": hasil_clipboard,
                        "sumber": "clipboard",
                        "engine": "MUSE SPARK 1.3"
                    }))
                    continue


                bahasa_threat = deteksi_intent_threat_hunt(cmd)
                if bahasa_threat is not None:
                    loop_threat = asyncio.get_event_loop()
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[NETSCAN] Opening a live CMD audit window "
                                   "(ping / tracert / netstat)..."
                    }))
                    hasil_threat = await loop_threat.run_in_executor(
                        None, jalankan_audit_koneksi_fisik, bahasa_threat)
                    kon_threat = hasil_threat.get("koneksi") or {}
                    jml_koneksi = kon_threat.get("total", 0)
                    jml_tanda = len(hasil_threat.get("temuan") or [])
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[NETSCAN] Audit done: {jml_koneksi} "
                                   f"connections, {jml_tanda} flagged. "
                                   "Dashboard sent to HUD."
                    }))
                    await websocket.send_text(json.dumps({
                        "type": "netscan_panel",
                        "ping": hasil_threat.get("ping") or {},
                        "tracert": hasil_threat.get("tracert") or [],
                        "koneksi": kon_threat,
                        "vonis": hasil_threat.get("vonis") or "",
                        "galat": hasil_threat.get("galat") or "",
                        "demo": bool(hasil_threat.get("demo_terlihat")),
                        "engine": "MUSE SPARK 1.3"
                    }))
                    if str(bahasa_threat).lower().startswith("en"):
                        ringkas_threat = (
                            f"Network audit done. {jml_koneksi} external "
                            f"connections, {jml_tanda} flagged. "
                            "Details are on the dashboard.")
                    else:
                        ringkas_threat = (
                            f"Audit jaringan selesai. {jml_koneksi} koneksi "
                            f"eksternal, {jml_tanda} ditandai. "
                            "Detailnya ada di dashboard.")
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": ringkas_threat,
                        "sumber": "network",
                        "engine": "MUSE SPARK 1.3"
                    }))
                    continue


                intent_layar = deteksi_intent_layar(cmd)
                if intent_layar is not None:
                    loop_layar = asyncio.get_event_loop()
                    pratinjau_layar = {}
                    if intent_layar["jenis"] == "baca":
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": "[SCREEN VISION] Capturing the monitor screen..."
                        }))
                        hasil_layar = await loop_layar.run_in_executor(
                            None, baca_layar_monitor, intent_layar["pertanyaan"],
                            pratinjau_layar)
                    elif intent_layar["jenis"] == "buka_dan_klik":
                        hasil_buka = execute_os_command(intent_layar["app"], "buka")
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": f"[SCREEN VISION] {hasil_buka} Waiting for the window..."
                        }))
                        await asyncio.sleep(2.0)
                        hasil_layar = await loop_layar.run_in_executor(
                            None, lihat_dan_klik_layar, intent_layar["target"],
                            pratinjau_layar)
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": f"[SCREEN VISION] Looking for '{intent_layar['target']}' on screen..."
                        }))
                        hasil_layar = await loop_layar.run_in_executor(
                            None, lihat_dan_klik_layar, intent_layar["target"],
                            pratinjau_layar)
                    if pratinjau_layar.get("image"):
                        await websocket.send_text(json.dumps({
                            "type": "grounding_preview",
                            "image": pratinjau_layar["image"],
                            "target": pratinjau_layar.get("target", ""),
                            "sumber": pratinjau_layar.get("sumber", "klik"),
                            "x": pratinjau_layar.get("x", 0),
                            "y": pratinjau_layar.get("y", 0)
                        }))
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[SCREEN VISION] {hasil_layar}"
                    }))
                    if intent_layar["jenis"] == "baca":

                        await websocket.send_text(json.dumps({
                            "type": "vision_response",
                            "text": hasil_layar,
                            "sumber": "layar",
                            "engine": "MUSE OPEN 1026 // VISION"
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "system_response",
                            "message": hasil_layar
                        }))
                    continue


                intent_app = deteksi_intent_aplikasi(cmd)
                if intent_app is not None:
                    loop_app = asyncio.get_event_loop()
                    hasil_app = await loop_app.run_in_executor(
                        None, execute_inapp_command, intent_app)
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[IN-APP] {hasil_app}"
                    }))
                    await websocket.send_text(json.dumps({
                        "type": "system_response",
                        "message": _balasan_taktis(hasil_app)
                    }))
                    continue


                intent_os = deteksi_intent_os(cmd)
                if intent_os is not None:
                    hasil_os = execute_os_command(intent_os["target"], intent_os["aksi"])
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[OS CONTROL] {hasil_os}"
                    }))
                    await websocket.send_text(json.dumps({
                        "type": "system_response",
                        "message": _balasan_taktis(hasil_os)
                    }))
                    continue


                intent_in = deteksi_intent_input(cmd)
                if intent_in is not None:
                    loop_in = asyncio.get_event_loop()
                    hasil_in = await loop_in.run_in_executor(
                        None, execute_input_command,
                        intent_in["command"], intent_in["params"])
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[INPUT CONTROL] {hasil_in}"
                    }))
                    await websocket.send_text(json.dumps({
                        "type": "system_response",
                        "message": hasil_in
                    }))
                    continue


                hasil_proaktif = (deteksi_perintah_pengingat(cmd)
                                  or deteksi_perintah_briefing(cmd))
                if hasil_proaktif is not None:
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": f"[PROACTIVE] {hasil_proaktif}"
                    }))
                    await websocket.send_text(json.dumps({
                        "type": "system_response",
                        "message": hasil_proaktif
                    }))
                    continue


                intent_berita = deteksi_intent_berita(cmd)
                if intent_berita is not None:
                    if "tak_didukung" in intent_berita:
                        hasil_berita = jawab_rentang_tak_didukung(
                            intent_berita["bahasa"])
                    else:
                        loop_berita = asyncio.get_event_loop()
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": "[NEWS] Fetching today's headlines..."
                        }))
                        galeri_berita = await loop_berita.run_in_executor(
                            None, jalankan_galeri_berita,
                            intent_berita["cakupan"], intent_berita["bahasa"])
                        if galeri_berita.get("artikel"):
                            await websocket.send_text(json.dumps({
                                "type": "news_gallery",
                                "artikel": galeri_berita["artikel"],
                                "cakupan": galeri_berita.get("cakupan", ""),
                                "bahasa": galeri_berita.get("bahasa", ""),
                                "engine": "MUSE SPARK 1.3"
                            }))
                            if str(intent_berita["bahasa"]).lower(
                                    ).startswith("en"):
                                hasil_berita = "Here is the latest news."
                            else:
                                hasil_berita = "Berikut adalah berita terkini."
                        else:
                            hasil_berita = galeri_berita.get("teks") or ""
                    await websocket.send_text(json.dumps({
                        "type": "arvi_response",
                        "text": hasil_berita,
                        "engine": "MUSE SPARK 1.3"
                    }))
                    continue


                if any(k in lower_cmd for k in ["cpu", "proses", "process", "berat", "ram", "hardware", "sistem", "status"]):
                    for node in list(node_clients):
                        try:
                            await node.send_text(json.dumps({"action": "INSPECT_CPU"}))
                        except RuntimeError:
                            node_clients.discard(node)
                        except Exception:
                            continue
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[CLOSED-LOOP] Pulling a fresh process sample from LAPTOP_01..."
                    }))

                    await asyncio.sleep(0.8)

                elif any(k in lower_cmd for k in ["ping", "jaringan", "network", "latensi", "internet"]):
                    for node in list(node_clients):
                        try:
                            await node.send_text(json.dumps({"action": "PING_NETWORK"}))
                        except RuntimeError:
                            node_clients.discard(node)
                        except Exception:
                            continue
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[CLOSED-LOOP] Probing network latency on LAPTOP_01..."
                    }))
                    await asyncio.sleep(1.2)


                if deteksi_tanya_visual_lanjutan(cmd):
                    _tanya_bersih = cmd
                    _konteks = _konteks_visual_terakhir()
                    _prompt_lanjut = _tanya_bersih
                    if _konteks:
                        _prompt_lanjut += (f"\n\nPrevious identification context: {_konteks}\n"
                                           "Answer the question above for that same object.")
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[OPTICAL CORTEX] Follow-up question — reusing the last visual frame..."
                    }))
                    _loop_vis = asyncio.get_event_loop()
                    _hasil_lanjut = await _loop_vis.run_in_executor(
                        None, query_arvi_vision,
                        last_vision_frame["image"], _prompt_lanjut)
                    _rekam_riwayat(f"[FOLLOW-UP VISUAL] {_tanya_bersih}", _hasil_lanjut)
                    await websocket.send_text(json.dumps({
                        "type": "vision_response",
                        "text": _hasil_lanjut,
                        "sumber": "lanjutan",
                        "engine": "MUSE OPEN 1026 // VISION"
                    }))
                    continue

                await websocket.send_text(json.dumps({
                    "type": "agent_log",
                    "message": "[INFERENCE] Synthesizing the response with live telemetry..."
                }))

                loop = asyncio.get_event_loop()
                response_text = await loop.run_in_executor(None, query_arvi_cognitive, cmd)

                if "[ABAIKAN_OBROLAN_LAIN]" in (response_text or ""):
                    _buang_turn_terakhir(cmd)
                    await websocket.send_text(json.dumps({
                        "type": "agent_log",
                        "message": "[LISTENER] Voice detected as a side conversation — ARVI stays quiet."
                    }))
                    continue

                response_text, _log_exec = _terapkan_exec_key(response_text)
                response_text, _log_alat = _terapkan_tool_json(response_text)
                response_text, _log_tindak = _terapkan_exec_action(
                    response_text)
                for _log_aksi in (_log_exec, _log_alat, _log_tindak):
                    if _log_aksi:
                        _catat_hasil_eksekusi(_log_aksi)
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": _log_aksi
                        }))
                await websocket.send_text(json.dumps({
                    "type": "arvi_response",
                    "text": response_text,
                    "engine": "MUSE SPARK 1.3"
                }))


            elif msg_type == "vision_scan":
                image_b64 = data.get("image", "")
                custom_prompt = normalisasi_nama_arvi(
                    data.get("prompt", "Analyze the object in front of the camera technically."))


                if (data.get("sumber") or "") == "suara":
                    putusan_pindai = saring_transkrip_suara(
                        custom_prompt, data.get("final", True))
                    if putusan_pindai is None:
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": "[VOICE] Transcript without Arvi prefix — dropped."
                        }))
                        continue
                    if putusan_pindai.get("tak_jelas"):
                        await websocket.send_text(json.dumps({
                            "type": "arvi_response",
                            "text": PESAN_ULANGI_ARVI,
                            "engine": "MUSE SPARK 1.3"
                        }))
                        continue

                await websocket.send_text(json.dumps({
                    "type": "agent_log",
                    "message": "[META SEGMENTATION] SAM 3.1 + cloud vision in parallel..."
                }))

                loop = asyncio.get_event_loop()
                vision_result, sam_data = await asyncio.gather(
                    loop.run_in_executor(None, query_arvi_vision,
                                         image_b64, custom_prompt),
                    loop.run_in_executor(None, jalankan_segmentasi_meta,
                                         image_b64),
                )

                last_vision_frame["image"] = image_b64
                last_vision_frame["timestamp"] = time.time()
                _rekam_riwayat(f"[VISUAL SCAN] {custom_prompt}", vision_result)

                await websocket.send_text(json.dumps({
                    "type": "vision_response",
                    "text": vision_result,
                    "sumber": "laptop",
                    "engine": "MUSE OPEN 1026 // VISION",
                    "sam": sam_data
                }))


            elif msg_type == "os_command":
                mentah_os = normalisasi_nama_arvi(
                    (data.get("raw") or data.get("command")
                     or data.get("target") or ""))


                if (data.get("sumber") or "") == "suara":
                    putusan_os = saring_transkrip_suara(
                        mentah_os, data.get("final", True))
                    if putusan_os is None:
                        await websocket.send_text(json.dumps({
                            "type": "agent_log",
                            "message": "[VOICE] Transcript without Arvi prefix — dropped."
                        }))
                        continue
                    if putusan_os.get("tak_jelas"):
                        await websocket.send_text(json.dumps({
                            "type": "arvi_response",
                            "text": PESAN_ULANGI_ARVI,
                            "engine": "MUSE SPARK 1.3"
                        }))
                        continue
                intent_ulangan = deteksi_intent_os(mentah_os) if mentah_os else None
                if intent_ulangan is not None:
                    hasil_os = execute_os_command(intent_ulangan["target"],
                                                  intent_ulangan["aksi"])
                else:
                    nama_os = (data.get("target") or "").strip() or mentah_os.strip()
                    aksi_os = data.get("aksi") or "buka"
                    if aksi_os not in ("buka", "tutup"):
                        aksi_os = "buka"
                    hasil_os = (execute_os_command(nama_os, aksi_os) if nama_os
                                else "[SYSTEM] Empty application target.")
                await websocket.send_text(json.dumps({
                    "type": "agent_log",
                    "message": f"[OS CONTROL] {hasil_os}"
                }))
                await websocket.send_text(json.dumps({
                    "type": "system_response",
                    "message": _balasan_taktis(hasil_os)
                }))


            elif data.get("action") == "open_software":
                hasil_lama = execute_os_command(data.get("target") or "", "buka")
                await websocket.send_text(json.dumps({
                    "type": "agent_log",
                    "message": f"[OS CONTROL] {hasil_lama}"
                }))
                await websocket.send_text(json.dumps({
                    "type": "system_response",
                    "message": _balasan_taktis(hasil_lama)
                }))


            elif msg_type == "input_command":
                perintah_in = data.get("command") or ""
                params_in = data.get("params") or {}
                loop_masuk = asyncio.get_event_loop()
                hasil_masuk = await loop_masuk.run_in_executor(
                    None, execute_input_command, perintah_in, params_in)
                await websocket.send_text(json.dumps({
                    "type": "agent_log",
                    "message": f"[INPUT CONTROL] {hasil_masuk}"
                }))
                await websocket.send_text(json.dumps({
                    "type": "system_response",
                    "message": hasil_masuk
                }))


    except WebSocketDisconnect:
        hud_clients.discard(websocket)
        sesi_ws.pop(websocket, None)
        print("[-] HUD disconnected")


@app.websocket("/ws/node")
async def websocket_node_endpoint(websocket: WebSocket):
    await websocket.accept()


    try:
        pertama = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        data_awal = json.loads(pertama)
    except (asyncio.TimeoutError, ValueError):
        data_awal = {}
    if (data_awal.get("type") != "auth"
            or not arvi_node.verifikasi_psk(data_awal.get("token"))):
        try:
            await websocket.send_text(json.dumps({"type": "auth_failed"}))
        except Exception:
            pass
        await websocket.close()
        print("[-] Node rejected: wrong/missing PSK.")
        return
    node_clients.add(websocket)
    print("[+] Edge Node connected (authenticated)")
    await websocket.send_text(json.dumps({"type": "auth_ok"}))


    await websocket.send_text(json.dumps({"action": "INSPECT_CPU"}))

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type")

            if msg_type == "telemetry":
                payload_str = _bersihkan_telemetri(data.get("payload", ""))

                system_context["latest_telemetry"] = payload_str
                _catat_cpu_telemetri(payload_str)


            elif msg_type == "action_result":
                action_name = data.get("action")
                output = _bersihkan_telemetri(data.get("output", ""), batas=4000)


                if action_name == "INSPECT_CPU":
                    system_context["top_processes"] = output
                elif action_name == "PING_NETWORK":
                    system_context["last_ping"] = output

                baris = output.splitlines()[:60]
                for hud in list(hud_clients):
                    for line in baris:
                        try:
                            await hud.send_text(json.dumps({
                                "type": "agent_log",
                                "message": line
                            }))
                        except RuntimeError:
                            hud_clients.discard(hud)
                            sesi_ws.pop(hud, None)
                            break
                        except Exception:
                            continue

    except WebSocketDisconnect:
        node_clients.discard(websocket)
        print("[-] Edge Node disconnected")


@app.on_event("startup")
async def _mulai_tugas_latar():

    try:
        arvi_node.muat_atau_buat_psk()
    except arvi_node.NodeAuthError as galat:
        print(f"[!] Node PSK init failed: {galat}")
    if _mod_proaktif._TUGAS_PROAKTIF is None:
        _mod_proaktif._TUGAS_PROAKTIF = asyncio.ensure_future(
            _mod_proaktif._loop_proaktif())
        print("[+] Proactive scheduler started (reminders, briefing, CPU watch).")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=8080, reload=True)
