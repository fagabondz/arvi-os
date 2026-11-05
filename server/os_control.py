import base64
import csv
import io
import json
import os
import re
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path

from server.config import ImageGrab
from server.memory import _normalisasi_kata_perintah

try:
    import psutil as _psutil
    _PSUTIL_TERSEDIA = True
except Exception:
    _psutil = None
    _PSUTIL_TERSEDIA = False

try:
    import pyautogui as _pag
    _PYAUTOGUI_TERSEDIA = True


    _pag.FAILSAFE = True
    _pag.PAUSE = 0.25
except Exception:
    _pag = None
    _PYAUTOGUI_TERSEDIA = False

try:
    import pyperclip as _pyperclip
    _PYPERCLIP_TERSEDIA = True
except Exception:
    _pyperclip = None
    _PYPERCLIP_TERSEDIA = False

_PESAN_INSTALL_PAG = ("pyautogui is not installed on this laptop. "
                      "Run: pip install pyautogui — then restart the ARVI server.")
_PESAN_INSTALL_PYPERCLIP = ("pyperclip is not installed on this laptop. "
                            "Run: pip install pyperclip — then restart the ARVI server.")


APP_DATABASE = {
   "resource monitor": {
        "buka": ["resmon.exe"],
        "tutup": ["perfmon.exe", "resmon.exe"],
        "alias": ["resource monitor", "resmon", "monitor sumber daya"]
    },
    "spotify": {"buka": ["cmd", "/c", "start", "", "spotify:"],
                "tutup": ["Spotify.exe", "spotify.exe", "SpotifyWebHelper.exe"],
                "alias": ["spotify"]},
    "notepad": {"buka": ["notepad.exe"], "tutup": ["notepad.exe"],
                "alias": ["notepad", "note pad", "catatan"]},
    "kalkulator": {"buka": ["calc.exe"], "tutup": ["CalculatorApp.exe", "calc.exe"],
                   "alias": ["kalkulator", "calculator", "calc", "kalkulasi"]},
    "chrome": {"buka": ["cmd", "/c", "start", "", "chrome"], "tutup": ["chrome.exe"],
               "alias": ["chrome", "google chrome", "browser"]},
    "edge": {"buka": ["cmd", "/c", "start", "", "msedge"], "tutup": ["msedge.exe"],
             "alias": ["edge", "microsoft edge"]},
    "explorer": {"buka": ["explorer.exe"], "tutup": None,
                 "alias": ["explorer", "file explorer", "eksplorer", "folder", "file manager"]},
    "cmd": {"buka": ["cmd.exe"], "tutup": ["cmd.exe"],
            "alias": ["cmd", "command prompt", "terminal", "konsol"]},
    "powershell": {"buka": ["powershell.exe"], "tutup": ["powershell.exe"],
                   "alias": ["powershell", "power shell"]},

    "task manager performance": {
        "buka": [
            "cmd", "/c",
            "reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\TaskManager /v StartUpTab /t REG_DWORD /d 1 /f && start taskmgr.exe"
        ],
        "tutup": ["Taskmgr.exe", "taskmgr.exe"],
        "alias": [
            "task manager performance",
            "performa task manager",
            "tab performance",
            "grafik cpu",
            "performance monitor"
        ]
    },

    "task manager": {"buka": ["taskmgr.exe"], "tutup": ["Taskmgr.exe"],
                     "alias": ["task manager", "taskmanager", "manajer tugas"]},

    "pengaturan": {"buka": ["cmd", "/c", "start", "", "ms-settings:"], "tutup": None,
                   "alias": ["pengaturan", "settings", "setting"]},
    "paint": {"buka": ["mspaint.exe"], "tutup": ["mspaint.exe"],
              "alias": ["paint", "mspaint"]},
    "snipping": {"buka": ["snippingtool.exe"], "tutup": ["SnippingTool.exe"],
                 "alias": ["snipping", "snipping tool", "screenshot", "tangkapan layar"]},
    "vscode": {"buka": ["cmd", "/c", "start", "", "code"], "tutup": ["Code.exe"],
               "alias": ["vscode", "vs code", "visual studio code", "code", "editor"]},
    "word": {"buka": ["cmd", "/c", "start", "", "winword"], "tutup": ["WINWORD.EXE"],
             "alias": ["word", "microsoft word", "ms word"]},
    "excel": {"buka": ["cmd", "/c", "start", "", "excel"], "tutup": ["EXCEL.EXE"],
              "alias": ["excel", "microsoft excel", "ms excel"]},
    "powerpoint": {"buka": ["cmd", "/c", "start", "", "powerpnt"], "tutup": ["POWERPNT.EXE"],
                   "alias": ["powerpoint", "power point", "ppt", "presentasi", "ms powerpoint"]},

}

_KATA_BUKA = ("bukakan", "dibuka", "buka", "jalankan", "jalani", "open",
              "launch", "start", "nyalakan", "run")
_KATA_TUTUP = ("tutupi", "ditutup", "tutup", "close", "matikan",
               "kill", "hentikan", "exit", "quit")


def _kanonis_target(teks: str):

    rendah = (teks or "").lower()
    for kanonis, info in APP_DATABASE.items():
        for alias in sorted(info["alias"], key=len, reverse=True):
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", rendah):
                return kanonis
    return None


def deteksi_intent_os(teks: str):

    import re
    rendah = f" {_normalisasi_kata_perintah(teks or '').lower().strip()} "
    aksi = None
    for kata in _KATA_TUTUP:
        if re.search(rf"(?<!\w){re.escape(kata)}(?!\w)", rendah):
            aksi = "tutup"
            break
    if aksi is None:
        for kata in _KATA_BUKA:
            if re.search(rf"(?<!\w){re.escape(kata)}(?!\w)", rendah):
                aksi = "buka"
                break
    if aksi is None:
        return None
    target = _kanonis_target(rendah)
    if target is None:
        return None
    return {"aksi": aksi, "target": target}


def execute_os_command(app_name, aksi="buka"):

    mentah = (app_name or "").strip()
    if not mentah:
        return "Empty application target."
    intent = deteksi_intent_os(mentah)
    if intent is not None:
        aksi, kanonis = intent["aksi"], intent["target"]
    else:
        kanonis = _kanonis_target(mentah)
    if kanonis is None:
        return (f"Application '{mentah}' is not registered in the ARVI database. "
                f"Registered: {', '.join(sorted(APP_DATABASE))}.")
    info = APP_DATABASE[kanonis]
    try:
        if aksi == "tutup":
            daftar_exe = info.get("tutup")
            if not daftar_exe:
                return f"'{kanonis}' may not be force-closed for system safety."
            if _PSUTIL_TERSEDIA and not _proses_berjalan(daftar_exe):
                return f"{kanonis} is not running (or is already closed)."
            for exe in daftar_exe:
                try:
                    subprocess.run(
                        ["taskkill", "/IM", exe, "/F", "/T"],
                        capture_output=True, text=True, timeout=10)
                except Exception:
                    continue
            time.sleep(0.8)
            if _PSUTIL_TERSEDIA and _proses_berjalan(daftar_exe):

                for exe in daftar_exe:
                    try:
                        subprocess.run(
                            ["taskkill", "/IM", exe, "/F", "/T"],
                            capture_output=True, text=True, timeout=10)
                    except Exception:
                        continue
                time.sleep(0.8)
            if _PSUTIL_TERSEDIA and _proses_berjalan(daftar_exe):
                return (f"[SYSTEM ERROR] Failed to close {kanonis}: it is still "
                        f"running (a save dialog or admin rights may be blocking it).")
            reset_konteks_aktif(kanonis)
            return f"[SYSTEM] Closed {kanonis} on the laptop."

        _ok_buka, pesan_buka = _fokus_atau_buka(kanonis, tunggu=False)
        if _ok_buka and kanonis not in ("chrome", "edge"):
            set_konteks_aktif(kanonis, state=f"{kanonis}_open")
        return pesan_buka
    except Exception as galat:
        return f"Failed to process {kanonis}: {galat}"


def _proses_berjalan(daftar_exe):

    if not daftar_exe or not _PSUTIL_TERSEDIA or _psutil is None:
        return False
    try:
        target = {e.lower() for e in daftar_exe}
        for proses in _psutil.process_iter(["name"]):
            try:
                if (proses.info.get("name") or "").lower() in target:
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def _fokus_jendela(nama_exe):

    target = (nama_exe or "").lower()
    try:
        import ctypes
        user32 = ctypes.windll.user32
        pid_target = set()
        if _PSUTIL_TERSEDIA and _psutil is not None:
            try:
                for proses in _psutil.process_iter(["name", "pid"]):
                    try:
                        if (proses.info.get("name") or "").lower() == target:
                            pid_target.add(proses.info.get("pid"))
                    except Exception:
                        continue
            except Exception:
                pass
        if pid_target:
            kandidat = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def _enum_proc(hwnd, _lparam):
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    judul = buf.value or ""
                    if not judul.strip():
                        return True
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value in pid_target:
                        kandidat.append((hwnd, judul))
                except Exception:
                    pass
                return True

            try:
                user32.EnumWindows(_enum_proc, 0)
            except Exception:
                kandidat = []
            if kandidat:
                if target == "chrome.exe":
                    utama = [k for k in kandidat
                             if k[1].strip().lower() != "who's using chrome?"]
                    hwnd_pilihan = (utama or kandidat)[0][0]
                else:
                    hwnd_pilihan = kandidat[0][0]
                try:
                    if user32.IsIconic(hwnd_pilihan):
                        user32.ShowWindow(hwnd_pilihan, 9)
                except Exception:
                    pass
                try:

                    user32.keybd_event(0x12, 0, 0, 0)
                    user32.SetForegroundWindow(hwnd_pilihan)
                    user32.keybd_event(0x12, 0, 2, 0)
                    return True
                except Exception:
                    pass
                try:
                    user32.SetForegroundWindow(hwnd_pilihan)
                    return True
                except Exception:
                    pass
    except Exception:
        pass

    dasar = target[:-4] if target.endswith(".exe") else target
    try:
        hasil = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(New-Object -ComObject WScript.Shell).AppActivate('{dasar}')"],
            capture_output=True, text=True, timeout=10)
        return "true" in (hasil.stdout or "").lower()
    except Exception:
        return False


def _perintah_buka_spotify():

    kandidat = [
        Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "Spotify.exe",
    ]
    for exe in kandidat:
        try:
            if exe.is_file():
                return [str(exe)]
        except Exception:
            continue
    return ["cmd", "/c", "start", "", "spotify:"]


def _fokus_atau_buka(kanonis, tunggu=True):

    info = APP_DATABASE.get(kanonis)
    if info is None:
        return False, f" Application '{kanonis}' is unknown."
    daftar_exe = info.get("tutup") or []
    if kanonis == "explorer":


        try:
            subprocess.Popen(["explorer.exe"], shell=False)
        except Exception as galat:
            return False, f"Failed to open explorer: {galat}"
        if tunggu:
            time.sleep(0.6)
        return True, " Opened explorer on the laptop."


    if _proses_berjalan(daftar_exe):
        _fokus_jendela(daftar_exe[0])
        if tunggu:
            time.sleep(0.4)
        return True, f"Focused the active {kanonis} window."

    perintah_buka = _perintah_buka_spotify() if kanonis == "spotify" else info["buka"]
    try:
        subprocess.Popen(perintah_buka, shell=False)
    except Exception as galat:
        return False, f"Failed to open {kanonis}: {galat}"
    if tunggu:
        time.sleep(2.5)
    return True, f"Opened {kanonis} on the laptop."


_BROWSER_KANONIS = ("chrome", "edge")


def _browser_target(teks):

    rendah = (teks or "").lower()
    for peramban in _BROWSER_KANONIS:
        if peramban in rendah:
            return peramban
    for peramban in _BROWSER_KANONIS:
        if _proses_berjalan(APP_DATABASE[peramban].get("tutup") or []):
            return peramban
    return "chrome"


def _bersihkan_query_cari(mentah):
    query = re.sub(r"\s+", " ", (mentah or "")).strip().strip("?.,!\"'")
    query = re.sub(r"^(cari|carikan|tolong cari|googling|google|search for|search|find|please search)\s+", "", query,
                   flags=re.IGNORECASE).strip()
    return query or None


WEB_DATABASE = {

    "facebook": {"url": "https://www.facebook.com/home.php",
              "alias": ["facebook", "fb"]},
    "linkedin": {"url": "https://www.linkedin.com/in/arifmazhuri",
              "alias": ["linkedin"]},
    "instagram": {"url": "https://www.instagram.com/fagabond_",
              "alias": ["instagram", "ig"]},
    "gmail": {"url": "https://mail.google.com",
              "alias": ["gmail", "email", "mail", "surat elektronik"]},
    "youtube": {"url": "https://www.youtube.com", "alias": ["youtube", "yt"]},
    "github": {"url": "https://github.com/fagabondz", "alias": ["github", "git hub"]},
    "whatsapp": {"url": "https://web.whatsapp.com",
                 "alias": ["whatsapp", "wa", "wa web"]},
    "drive": {"url": "https://drive.google.com",
              "alias": ["google drive", "gdrive", "drive"]},
    "chatgpt": {"url": "https://chatgpt.com", "alias": ["chatgpt", "chat gpt"]},
    "gemini web": {"url": "https://gemini.google.com",
                   "alias": ["gemini", "web gemini", "halaman gemini"]},
    "elevenlabs": {"url": "https://elevenlabs.io/app",
                   "alias": ["elevenlabs", "eleven labs"]},
}


def cari_url_bookmark_chrome(kata_kunci):

    kunci = (kata_kunci or "").lower().strip()
    if not kunci:
        return None
    dasar = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    if not dasar.is_dir():
        return None
    berkas = []
    bawaan = dasar / "Default" / "Bookmarks"
    if bawaan.is_file():
        berkas.append(bawaan)
    try:
        berkas.extend(sorted(p for p in dasar.glob("*/Bookmarks") if p.is_file()))
    except Exception:
        pass
    unik, terlihat = [], set()
    for berkas_bm in berkas:
        kunci_path = str(berkas_bm)
        if kunci_path not in terlihat:
            terlihat.add(kunci_path)
            unik.append(berkas_bm)

    def _susuri(node):
        if isinstance(node, dict):
            if node.get("type") == "url":
                nama = str(node.get("name", ""))
                if kunci in nama.lower():
                    return (nama, node.get("url", ""))
            for anak in (node.get("children") or []):
                hasil = _susuri(anak)
                if hasil:
                    return hasil
        elif isinstance(node, list):
            for anak in node:
                hasil = _susuri(anak)
                if hasil:
                    return hasil
        return None

    for berkas_bm in unik:
        try:
            data = json.loads(berkas_bm.read_text(encoding="utf-8"))
        except Exception:
            continue
        roots = data.get("roots") or {}
        for kunci_root in ("bookmark_bar", "other", "synced"):
            hasil = _susuri(roots.get(kunci_root))
            if hasil and hasil[1]:
                return hasil
    return None


def _bersihkan_target_web(kandidat):

    bersih = re.sub(r"\s+", " ", (kandidat or "")).strip().strip("\"'").strip()
    for _ in range(3):
        sebelum = bersih
        for isi in ("situs", "website", "web", "halaman", "tab", "di chrome",
                    "di browser", "di edge", "tab baru", "di tab baru", "site",
                    "page", "in chrome", "in edge", "in the browser",
                    "in browser", "new tab", "in a new tab", "the", "dong",
                    "tolong", "please", "sekarang", "now"):
            kecil = bersih.lower()
            if kecil.startswith(isi + " "):
                bersih = bersih[len(isi):].strip()
            elif kecil.endswith(" " + isi):
                bersih = bersih[:-(len(isi))].strip()
        if bersih == sebelum:
            break
    return re.sub(r"\s+", " ", bersih).strip().strip(".,!?\"'") or None


def _cocok_web_database(target):

    rendah = (target or "").lower().strip()
    if not rendah:
        return None
    for situs, info in WEB_DATABASE.items():
        if rendah == situs or rendah in [a.lower() for a in info["alias"]]:
            return (situs, info["url"])
    return None


_KONTEKS_TTL_DETIK = 300.0

active_context_state = {
    "app": "",
    "state": "",
    "domain": "",
    "query": "",
    "timestamp": 0.0,
}


def set_konteks_aktif(app: str, state: str = "", domain: str = "", query: str = "") -> dict:

    nama_app = (app or "").strip().lower()
    active_context_state["app"] = nama_app
    active_context_state["state"] = (state or (f"{nama_app}_open" if nama_app else "")).strip()
    active_context_state["domain"] = (domain or "").strip().lower()
    if query is not None:
        active_context_state["query"] = str(query).strip()
    active_context_state["timestamp"] = time.time() if nama_app else 0.0
    return dict(active_context_state)


def reset_konteks_aktif(app: str = "") -> None:

    target = (app or "").strip().lower()
    if not target or active_context_state.get("app") == target or target in (active_context_state.get("domain") or ""):
        active_context_state["app"] = ""
        active_context_state["state"] = ""
        active_context_state["domain"] = ""
        active_context_state["query"] = ""
        active_context_state["timestamp"] = 0.0


def dapatkan_konteks_aktif(ttl: float = _KONTEKS_TTL_DETIK) -> dict:

    sekarang = time.time()
    app_tersimpan = active_context_state.get("app") or ""
    ts_tersimpan = float(active_context_state.get("timestamp") or 0.0)
    masih_hangat = bool(app_tersimpan and (sekarang - ts_tersimpan) <= ttl)

    if masih_hangat:
        return dict(active_context_state)

    info = _dapatkan_info_jendela_aktif() or {}
    judul_aktif = (info.get("judul") or "").lower()
    if "youtube" in judul_aktif:
        return {
            "app": "youtube",
            "state": "youtube_open",
            "domain": "youtube.com",
            "query": active_context_state.get("query") or "",
            "timestamp": sekarang,
        }
    if "spotify" in (info.get("exe") or "").lower():
        return {
            "app": "spotify",
            "state": "spotify_open",
            "domain": "",
            "query": "",
            "timestamp": sekarang,
        }
    return {}


def _ekstrak_host_url(url_mentah: str) -> str:

    teks = (url_mentah or "").strip()
    if not teks:
        return ""

    if re.match(r"(?i)^(chrome|edge|about|file|javascript|data|view-source):", teks):
        return ""
    if " " in teks and not re.match(r"(?i)^https?://\S+$", teks):
        return ""
    calon = teks if "://" in teks else f"https://{teks}"
    try:
        parsed = urllib.parse.urlparse(calon)
        host = (parsed.hostname or "").strip().lower().rstrip(".")
    except Exception:
        return ""
    if not host or "." not in host:
        return ""
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", host):
        return ""
    return host


def _domain_cocok(url_atau_host: str, domain_target: str) -> bool:

    host = _ekstrak_host_url(url_atau_host)
    if not host:
        return False
    target = _ekstrak_host_url(domain_target) or (domain_target or "").strip().lower().lstrip(".")
    if target.startswith("www."):
        target = target[4:]
    if host.startswith("www."):
        host_inti = host[4:]
    else:
        host_inti = host
    if not target or "." not in target:
        return False
    if host_inti == target or host_inti.endswith("." + target):
        return True
    if target == "youtube.com" and (host_inti == "youtu.be" or host_inti.endswith(".youtu.be")):
        return True
    return False


def _target_situs_ke_domain(target_mentah: str):

    bersih = _bersihkan_target_web(target_mentah)
    if not bersih:
        return None
    cocok_web = _cocok_web_database(bersih)
    if cocok_web:
        situs, url = cocok_web
        host = _ekstrak_host_url(url)
        if host.startswith("www."):
            host = host[4:]
        return (situs, host, url)
    hasil_bm = cari_url_bookmark_chrome(bersih)
    if hasil_bm:
        nama_bm, url_bm = hasil_bm
        host = _ekstrak_host_url(url_bm)
        if host.startswith("www."):
            host = host[4:]
        if host:
            return (nama_bm, host, url_bm)
    host_langsung = _ekstrak_host_url(bersih)
    if host_langsung:
        inti = host_langsung[4:] if host_langsung.startswith("www.") else host_langsung
        return (inti.split(".")[0], inti, f"https://{host_langsung}")
    return None


def _baca_url_uia() -> str:

    try:
        import uiautomation as auto
        fg = auto.GetForegroundControl()
        if fg:
            edit = fg.EditControl(searchDepth=12, Name="Address and search bar")
            if not edit.Exists(0, 0):
                edit = fg.EditControl(searchDepth=12)
            if edit.Exists(0, 0):
                val = edit.GetValuePattern().Value
                if val and _ekstrak_host_url(val):
                    return str(val).strip()
    except Exception:
        pass
    return ""


def _baca_url_address_bar(peramban: str = "chrome") -> str:

    url_uia = _baca_url_uia()
    if url_uia:
        return url_uia
    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return ""
    clip_asli = None
    if _PYPERCLIP_TERSEDIA and _pyperclip is not None:
        try:
            clip_asli = _pyperclip.paste()
            _pyperclip.copy("")
        except Exception:
            clip_asli = None
    try:
        _pag.hotkey("ctrl", "l")
        time.sleep(0.12)
        _pag.hotkey("ctrl", "c")
        time.sleep(0.10)
        _pag.press("esc")
        if _PYPERCLIP_TERSEDIA and _pyperclip is not None:
            url_terbaca = str(_pyperclip.paste() or "").strip()
        else:
            url_terbaca = ""
    except Exception:
        url_terbaca = ""
    finally:
        if clip_asli is not None and _PYPERCLIP_TERSEDIA and _pyperclip is not None:
            try:
                _pyperclip.copy(clip_asli)
            except Exception:
                pass
    return url_terbaca


def tutup_tab_berdasarkan_domain(target_situs: str, peramban: str = None, maks_tab: int = 10) -> str:

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    info_situs = _target_situs_ke_domain(target_situs)
    if not info_situs:
        return (f"[SYSTEM ERROR] Site '{target_situs}' is not recognized or has no valid domain — "
                "nothing closed.")
    nama_situs, domain_target, _ = info_situs
    app_browser = (peramban or _browser_target(target_situs) or "chrome").lower()
    if app_browser not in _BROWSER_KANONIS:
        app_browser = "chrome"

    daftar_exe = APP_DATABASE.get(app_browser, {}).get("tutup") or ["chrome.exe"]
    if _PSUTIL_TERSEDIA and not _proses_berjalan(daftar_exe):
        return (f"[SYSTEM ERROR] Tab for '{nama_situs}' ({domain_target}) was not found: "
                f"{app_browser} is not running.")

    _fokus_jendela(daftar_exe[0])
    time.sleep(0.2)

    try:

        url_awal = _baca_url_address_bar(app_browser)
        if _domain_cocok(url_awal, domain_target):

            url_verifikasi = _baca_url_address_bar(app_browser) or url_awal
            if _domain_cocok(url_verifikasi, domain_target):
                _pag.hotkey("ctrl", "w")
                reset_konteks_aktif(nama_situs)
                return f"[SYSTEM] Closed '{nama_situs}' tab ({domain_target}) in {app_browser}."


        batas_siklus = max(1, int(maks_tab))
        for langkah in range(1, batas_siklus):
            _pag.hotkey("ctrl", "tab")
            time.sleep(0.18)
            url_kini = _baca_url_address_bar(app_browser)
            if _domain_cocok(url_kini, domain_target):

                url_verifikasi = _baca_url_address_bar(app_browser) or url_kini
                if _domain_cocok(url_verifikasi, domain_target):
                    _pag.hotkey("ctrl", "w")
                    reset_konteks_aktif(nama_situs)
                    return (f"[SYSTEM] Found and closed '{nama_situs}' tab "
                            f"({domain_target}) at tab order +{langkah} in {app_browser}.")

            if url_awal and url_kini and url_kini == url_awal:
                break


        return (f"[SYSTEM ERROR] Tab for '{nama_situs}' ({domain_target}) was not found "
                f"in open {app_browser} tabs — nothing closed.")
    except _pag.FailSafeException:
        return "FAILSAFE tripped — the action was cancelled by the operator."
    except Exception as galat:
        return f"[SYSTEM ERROR] Failed to inspect/close '{nama_situs}' tab: {galat}"


def buka_url_di_chrome_aktif(url, nama_situs=""):

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    if not (url or "").strip():
        return "Empty URL — nothing opened."
    ok, pesan = _fokus_atau_buka("chrome", tunggu=True)
    if not ok:
        return pesan
    try:
        _pag.hotkey("ctrl", "t")
        time.sleep(0.4)
        _pag.hotkey("ctrl", "l")
        time.sleep(0.2)
        _pag.write(url, interval=0.01)
        _pag.press("enter")
    except _pag.FailSafeException:
        return "FAILSAFE tripped — the action was cancelled by the operator."
    except Exception as galat:
        return f"Failed to open the URL: {galat}"
    label = nama_situs or url
    host = _ekstrak_host_url(url)
    if (nama_situs or "").strip().lower() == "youtube" or _domain_cocok(url, "youtube.com"):
        set_konteks_aktif("youtube", state="youtube_open", domain="youtube.com", query="")
    else:
        set_konteks_aktif((nama_situs or host or "chrome").lower(),
                          state="web_open", domain=host, query="")
    return f"Opening '{label}' in a new tab of the active Chrome."


def putar_video_youtube_teratas(query: str = "", pratinjau=None) -> str:

    from server.config import BASETEN_API_KEY
    from server.vision_engine import lihat_dan_klik_layar

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    ok, pesan = _fokus_atau_buka("chrome", tunggu=True)
    if not ok:
        return pesan
    query_bersih = (query or active_context_state.get("query") or "").strip()


    if BASETEN_API_KEY:
        target_vis = (f"first video title or thumbnail for {query_bersih}"
                      if query_bersih else
                      "first video title or thumbnail in YouTube search results")
        hasil_vis = lihat_dan_klik_layar(target_vis, pratinjau=pratinjau)
        if "and clicked it" in (hasil_vis or "").lower():
            set_konteks_aktif("youtube", state="youtube_playing",
                              domain="youtube.com", query=query_bersih)
            return hasil_vis


    try:
        try:
            lebar, tinggi = _pag.size()
        except Exception:
            lebar, tinggi = 1920, 1080
        x_klik = max(100, int((lebar or 1920) * 0.36))
        y_klik = max(120, int((tinggi or 1080) * 0.36))
        _pag.moveTo(x_klik, y_klik, duration=0.3)
        _pag.click()
        set_konteks_aktif("youtube", state="youtube_playing",
                          domain="youtube.com", query=query_bersih)
        info_q = f" for '{query_bersih}'" if query_bersih else ""
        return f"[SYSTEM] Playing the top YouTube video result{info_q}."
    except _pag.FailSafeException:
        return "FAILSAFE tripped — the action was cancelled by the operator."
    except Exception as galat:
        return f"[SYSTEM ERROR] Failed to play the top YouTube video: {galat}"


def cari_dan_putar_youtube(teks_atau_query: str, pratinjau=None) -> str:

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    query, _ = _ekstrak_query_cari(teks_atau_query)
    if not query:
        query = _bersihkan_query_cari(teks_atau_query) or ""
    if not query:
        return "Empty search keywords."
    hasil_cari = cari_kontekstual_di_layar_aktif(
        f"search {query} on youtube", konteks_override="youtube")
    if any(k in (hasil_cari or "").lower() for k in ("error", "failed", "failsafe", "pip install")):
        return hasil_cari
    time.sleep(1.8)
    return putar_video_youtube_teratas(query=query, pratinjau=pratinjau)


_FRASA_PUTAR_KONTEKSTUAL = (
    "play it", "play this", "play that", "play the video",
    "play first video", "play the first video", "play top video",
    "play the top video", "play video", "putar itu", "putar ini",
    "putar videonya", "putar video itu", "putar video ini",
    "putar video pertama", "putar yang pertama", "stel itu",
    "stel videonya", "mainkan itu", "mainkan videonya",
)


def _ekstrak_komposit_youtube_putar(mentah: str):

    teks = (mentah or "").strip()
    if not teks:
        return None
    rendah = teks.lower()
    if not re.search(r"(?<!\w)(youtube|yt)(?!\w)", rendah):
        return None

    pola_komposit = re.compile(
        r"(?i)^(?:tolong\s+|please\s+)?"
        r"(?:(?:bukakan|buka|jalankan|open|launch|start)\s+(?:situs\s+|the\s+)?(?:youtube|yt)\s*"
        r"(?:lalu|kemudian|terus|dan|and|then|,)?\s*)?"
        r"(?:carikan|cari|search\s+for|search|find)\s+"
        r"(.+?)\s+"
        r"(?:(?:di|on|in)\s+(?:youtube|yt)\s+)?"
        r"(?:lalu|kemudian|terus|setelah\s+itu|habis\s+itu|dan|and\s+then|then|and)\s+"
        r"(?:tolong\s+|please\s+)?"
        r"(?:putar|stel|mainkan|play)"
        r"(?:\s+(?:itu|ini|videonya|video\s+itu|video\s+pertama|yang\s+pertama|it|this|that|the\s+video|first\s+video|the\s+first\s+video))?"
        r"\s*[.!?]*$"
    )
    cocok = pola_komposit.match(teks)
    if cocok:
        q = re.sub(r"(?i)\s*\b(?:di|on|in)\s+(?:youtube|yt)\b\s*", " ", cocok.group(1)).strip()
        q = re.sub(r"(?i)^(?:lagu|musik|video|song|music|track)\s+", "", q).strip(" ?.,!\"'")
        return q or None
    return None


def deteksi_intent_aplikasi(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if re.search(r"(?<!\w)(tab baru|tambah tab|buat tab|new tab|open tab)(?!\w)", rendah):
        return {"app": _browser_target(rendah), "aksi": "tab_baru", "query": ""}


    cocok_tutup_situs = re.search(
        r"(?<!\w)(?:tutupi|ditutup|tutup|close|matikan|kill|hentikan|exit|quit|keluar\s+dari)(?!\w)"
        r"\s+(?:tab\s+|situs\s+|website\s+|web\s+|halaman\s+|the\s+)?(.+)",
        rendah
    )
    if cocok_tutup_situs:
        kandidat_tutup = cocok_tutup_situs.group(1).strip()

        kandidat_bersih = _bersihkan_target_web(kandidat_tutup)

        if kandidat_bersih and kandidat_bersih.lower() not in (
                "tab", "chrome", "google chrome", "edge", "microsoft edge",
                "browser", "jendela", "window", "aplikasi", "app", "semua", "all"):

            if _kanonis_target(kandidat_bersih) is None:
                info_situs = _target_situs_ke_domain(kandidat_bersih)
                if info_situs:
                    nama_situs, domain_target, url_situs = info_situs
                    return {
                        "app": _browser_target(rendah),
                        "aksi": "tutup_url",
                        "nama": nama_situs,
                        "domain": domain_target,
                        "url": url_situs,
                        "query": "",
                    }


                if re.match(r"^[a-z0-9.-]+$", kandidat_bersih.lower()):
                    nama_s = kandidat_bersih.lower().split(".")[0]
                    dom_s = (kandidat_bersih.lower()
                             if "." in kandidat_bersih
                             else f"{nama_s}.com")
                    return {
                        "app": _browser_target(rendah),
                        "aksi": "tutup_url",
                        "nama": nama_s,
                        "domain": dom_s,
                        "url": f"https://{dom_s}",
                        "query": "",
                    }

    if re.search(r"(?<!\w)(tutup tab|close tab)(?!\w)", rendah):
        return {"app": _browser_target(rendah), "aksi": "tutup_tab", "query": ""}
    if re.search(r"(?<!\w)(jendela baru|window baru|new window)(?!\w)", rendah):
        return {"app": _browser_target(rendah), "aksi": "jendela_baru", "query": ""}
    if re.search(r"(?<!\w)(refresh|muat ulang|reload)(?!\w)", rendah):
        return {"app": _browser_target(rendah), "aksi": "refresh", "query": ""}


    query_komposit = _ekstrak_komposit_youtube_putar(mentah)
    if query_komposit:
        return {
            "app": "chrome",
            "aksi": "cari_youtube_dan_putar",
            "query": query_komposit,
            "konteks": "youtube",
            "mentah": mentah,
        }


    bersih_polos = re.sub(
        r"(?i)^\s*(?:tolong\s+|please\s+|coba\s+|arvi\s+)+", "", mentah
    ).strip().strip(".,!?").lower()
    bersih_polos = re.sub(r"(?i)\s+(?:dong|sekarang|now|please|ya)\s*$", "", bersih_polos).strip()
    if bersih_polos in _FRASA_PUTAR_KONTEKSTUAL:
        konteks_aktif = dapatkan_konteks_aktif()
        app_konteks = konteks_aktif.get("app") or ""
        state_konteks = konteks_aktif.get("state") or ""
        info_jendela = _dapatkan_info_jendela_aktif() or {}
        if (app_konteks == "youtube"
                or state_konteks.startswith("youtube")
                or info_jendela.get("youtube_terbuka")
                or "video" in bersih_polos
                or "pertama" in bersih_polos
                or "first" in bersih_polos
                or bersih_polos in ("play it", "putar itu", "play this", "play that", "putar ini", "stel itu", "mainkan itu")):
            return {
                "app": "chrome",
                "aksi": "putar_kontekstual",
                "konteks": "youtube",
                "query": konteks_aktif.get("query") or "",
            }

    cocok = re.search(r"(?<!\w)cari(?:kan)? di google\s+(.+)", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)
    cocok = re.search(r"(?<!\w)googling\s+(.+)", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)
    cocok = re.search(r"(?<!\w)search google for\s+(.+)", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)
    cocok = re.search(r"(?<!\w)search for\s+(.+?)\s+on google\b", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)
    cocok = re.search(r"(.+?)\s+(?:di|on) google\b", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)

    if (re.search(r"(?<!\w)(carikan|cari|stel|putar|search|find|play)(?!\w)", rendah)
            or re.search(r"(?<!\w)ketik(?:kan)?\s+.+\s+di\s+(?:kolom\s+)?"
                         r"(?:pencarian|cari)(?!\w)", rendah)
            or re.search(r"(?<!\w)type\s+.+\s+in\s+(?:the\s+)?search"
                         r"(?:\s+box|\s+bar)?(?!\w)", rendah)):
        query, konteks = _ekstrak_query_cari(mentah)
        if query:
            if konteks is None:
                konteks_sesi = dapatkan_konteks_aktif()
                if konteks_sesi.get("app") in ("youtube", "spotify"):
                    konteks = konteks_sesi["app"]
            return {"app": "aktif", "aksi": "cari_kontekstual",
                    "query": query, "konteks": konteks, "mentah": mentah}

    cocok = re.search(r"(?<!\w)search for\s+(.+)", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)
    cocok = re.search(r"(?<!\w)search\s+(.+)", rendah)
    if cocok:
        query = _bersihkan_query_cari(cocok.group(1))
        return ({"app": _browser_target(rendah), "aksi": "cari", "query": query}
                if query else None)

    cocok = re.search(r"(?<!\w)(?:bukakan|buka|jalankan|open|launch|start)(?!\w)\s+(?:bookmark\s+|the\s+)?(.+)", rendah)
    if cocok:
        kandidat = cocok.group(1).strip()
        if not re.search(r"(?<!\w)(tab|jendela|window|refresh|muat ulang|reload|di google|on google|googling|search for|search|cari|carikan|find)(?!\w)", kandidat):
            if _kanonis_target(kandidat) is None:
                target_web = _bersihkan_target_web(kandidat)
                if target_web:
                    cocok_web = _cocok_web_database(target_web)
                    if cocok_web:
                        situs, url = cocok_web
                        return {"app": "chrome", "aksi": "buka_url",
                                "url": url, "nama": situs, "query": ""}
                    hasil_bm = cari_url_bookmark_chrome(target_web)
                    if hasil_bm:
                        nama_bm, url_bm = hasil_bm
                        return {"app": "chrome", "aksi": "buka_url",
                                "url": url_bm, "nama": nama_bm, "query": ""}
    return None


def execute_inapp_command(intent):

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    app = intent.get("app") or "chrome"
    aksi = intent.get("aksi") or ""
    query = (intent.get("query") or "").strip()
    if aksi == "buka_url":
        return buka_url_di_chrome_aktif(intent.get("url") or "",
                                        intent.get("nama") or "")
    if aksi == "tutup_url":
        target_situs = intent.get("nama") or intent.get("domain") or intent.get("url") or ""
        return tutup_tab_berdasarkan_domain(target_situs, peramban=app)
    if aksi == "cari_youtube_dan_putar":
        return cari_dan_putar_youtube(intent.get("mentah") or query)
    if aksi == "putar_kontekstual":
        return putar_video_youtube_teratas(query=query)
    if aksi == "cari_kontekstual":
        return cari_kontekstual_di_layar_aktif(
            intent.get("mentah") or query,
            konteks_override=intent.get("konteks"))
    ok, pesan = _fokus_atau_buka(app, tunggu=True)
    if not ok:
        return pesan
    try:
        if aksi == "tab_baru":
            _pag.hotkey("ctrl", "t")
            return f"Opened a new tab in {app}."
        if aksi == "tutup_tab":
            _pag.hotkey("ctrl", "w")
            return f"Closed the active tab in {app}."
        if aksi == "jendela_baru":
            _pag.hotkey("ctrl", "n")
            return f"Opened a new {app} window."
        if aksi == "refresh":
            _pag.press("f5")
            return f"Refreshed the page in {app}."
        if aksi == "cari":
            if not query:
                return "Empty search keywords."
            _pag.hotkey("ctrl", "t")
            time.sleep(0.8)
            _pag.write(query, interval=0.02)
            _pag.press("enter")
            return f"Searching Google for '{query}' ({app})."
        return f"Unknown in-app action '{aksi}'."
    except _pag.FailSafeException:
        return "FAILSAFE tripped — the action was cancelled by the operator."
    except Exception as galat:
        return f"Failed to run the action: {galat}"


def _ekstrak_query_cari(mentah):

    teks_strip = (mentah or "").strip()
    rendah = f" {teks_strip.lower()} "

    if re.match(r"(?i)^\s*(?:tolong\s+|please\s+)?(?:tutupi|ditutup|tutup|close|matikan|kill|hentikan|exit|quit)\b", teks_strip):
        return None, None

    polos = re.sub(r"(?i)^\s*(?:tolong\s+|please\s+|coba\s+)+", "", teks_strip).strip(" .!?").lower()
    if polos in _FRASA_PUTAR_KONTEKSTUAL:
        return None, None

    konteks = None
    if re.search(r"(?<!\w)(di\s+youtube|on\s+youtube|in\s+youtube|youtube|yt)(?!\w)", rendah):
        konteks = "youtube"
    elif re.search(r"(?<!\w)(di\s+spotify|on\s+spotify|in\s+spotify|spotify)(?!\w)", rendah):
        konteks = "spotify"
    cocok = re.search(r"(?<!\w)ketik(?:kan)?\s+(.+?)\s+di\s+"
                      r"(?:kolom\s+)?(?:pencarian|cari)(?!\w)", rendah)
    if cocok:
        query = cocok.group(1).strip()
    else:
        cocok_en = re.search(r"(?<!\w)type\s+(.+?)\s+in\s+(?:the\s+)?search"
                             r"(?:\s+box|\s+bar)?(?!\w)", rendah)
        if cocok_en:
            query = cocok_en.group(1).strip()
        else:
            query = teks_strip

            query = re.sub(
                r"(?i)^\s*(?:tolong\s+|please\s+)?"
                r"(?:(?:bukakan|buka|jalankan|open|launch|start)\s+(?:situs\s+|the\s+)?(?:youtube|yt|spotify)\s*"
                r"(?:lalu|kemudian|terus|dan|and|then|,)?\s*)?",
                "", query
            ).strip()
            query = re.sub(
                r"(?i)^\s*(?:tolong\s+|please\s+)?(carikan|cari|stel|putar|search\s+for|search|find|play)"
                r"(?:\s+|$)\s*(lagu|musik|video|song|music|track)?\s*",
                "", query
            ).strip()

            query = re.sub(
                r"(?i)\s+(?:lalu|kemudian|terus|setelah\s+itu|habis\s+itu|dan|and\s+then|then|and)\s+"
                r"(?:tolong\s+|please\s+)?(?:putar|stel|mainkan|play)"
                r"(?:\s+(?:itu|ini|videonya|video\s+itu|video\s+pertama|yang\s+pertama|it|this|that|the\s+video|first\s+video|the\s+first\s+video))?\s*$",
                "", query
            ).strip()
            query = re.sub(r"(?i)\s*\b(?:di|on|in)\s+(youtube|yt|spotify)\b\s*", " ",
                           query).strip()
            query = re.sub(r"\s+", " ", query).strip(" ?.,!")
    if (not query or query.lower().startswith("tahu ")
            or query.lower().startswith("out ")
            or query.lower() in ("cari", "carikan", "stel", "putar",
                                 "ketik", "ketikkan", "search", "find",
                                 "play", "song", "music", "it", "itu",
                                 "this", "that", "ini", "video", "videonya",
                                 "the video", "first video")):
        return None, None
    return query, konteks


def _dapatkan_info_jendela_aktif():

    u32 = _user32()
    if u32 is None:
        return None
    try:
        import ctypes
        hwnd = u32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(hwnd, buf, 512)
        judul = buf.value or ""
        pid = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        if _PSUTIL_TERSEDIA and _psutil is not None and pid.value:
            try:
                exe = (_psutil.Process(pid.value).name() or "").lower()
            except Exception:
                exe = ""
        ketemu_yt = []
        try:
            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                ctypes.c_void_p)
            def _enum(hwnd_e, _lparam):
                try:
                    if u32.IsWindowVisible(hwnd_e):
                        kecil = ctypes.create_unicode_buffer(256)
                        u32.GetWindowTextW(hwnd_e, kecil, 256)
                        if "youtube" in (kecil.value or "").lower():
                            ketemu_yt.append(True)
                except Exception:
                    pass
                return True
            u32.EnumWindows(_enum, 0)
        except Exception:
            pass
        return {"judul": judul, "exe": exe,
                "youtube_terbuka": bool(ketemu_yt),
                "spotify_terbuka": _proses_berjalan(["Spotify.exe",
                                                     "spotify.exe"])}
    except Exception:
        return None


def cari_kontekstual_di_layar_aktif(teks_perintah, konteks_override=None):


    from server.ai_engine import ambil_respon_taktis_singkat
    from server.vision_engine import lihat_dan_klik_layar

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG

    if re.match(r"(?i)^\s*(?:cari\s+)?(?:tolong\s+|please\s+)?(?:tutupi|ditutup|tutup|close|matikan|kill|hentikan|exit|quit)\b",
                (teks_perintah or "").strip()):
        return "[SYSTEM ERROR] Close command blocked from search input path."
    query, konteks = _ekstrak_query_cari(teks_perintah)
    if not query:
        return "Empty search keywords."

    konteks_sesi = dapatkan_konteks_aktif()
    if konteks_override:
        konteks = konteks_override
    elif konteks is None and konteks_sesi.get("app") in ("youtube", "spotify"):
        konteks = konteks_sesi["app"]

    info = _dapatkan_info_jendela_aktif() or {}
    youtube = (konteks == "youtube"
               or konteks_sesi.get("app") == "youtube"
               or info.get("youtube_terbuka"))
    spotify = (not youtube and (
               konteks == "spotify"
               or konteks_sesi.get("app") == "spotify"
               or "spotify" in (info.get("exe") or "")
               or info.get("spotify_terbuka")))
    try:

        if youtube:
            ok, pesan = _fokus_atau_buka("chrome", tunggu=True)
            if not ok:
                return pesan
            time.sleep(0.3)
            info2 = _dapatkan_info_jendela_aktif() or {}
            perintah_buka_baru = bool(re.match(
                r"(?i)^\s*(?:tolong\s+|please\s+)?(?:bukakan|buka|jalankan|open|launch|start)\s+(?:youtube|yt)\b",
                (teks_perintah or "").strip()
            ))
            tab_yt_aktif = (
                "youtube" in (info2.get("judul") or "").lower()
                or (konteks_sesi.get("app") == "youtube" and not perintah_buka_baru)
            )
            if tab_yt_aktif:
                try:
                    _pag.press("/")
                except Exception:
                    klik = lihat_dan_klik_layar("Telusuri")
                    if "and clicked it" not in klik.lower():
                        klik = lihat_dan_klik_layar("Search")
                        if "and clicked it" not in klik.lower():
                            return klik
                time.sleep(0.4)
                _pag.hotkey("ctrl", "a")
                _pag.press("backspace")
                _pag.write(query, interval=0.02)
                _pag.press("enter")
                set_konteks_aktif("youtube", state="youtube_search_results",
                                  domain="youtube.com", query=query)
                return ambil_respon_taktis_singkat()
            url = ("https://www.youtube.com/results?search_query="
                   + urllib.parse.quote_plus(query))
            _pag.hotkey("ctrl", "t")
            time.sleep(0.8)
            _pag.write(url, interval=0.01)
            _pag.press("enter")
            set_konteks_aktif("youtube", state="youtube_search_results",
                              domain="youtube.com", query=query)
            return ambil_respon_taktis_singkat()

        if spotify:
            ok, pesan = _fokus_atau_buka("spotify", tunggu=True)
            if not ok:
                return pesan
            time.sleep(0.4)
            _pag.hotkey("ctrl", "l")
            time.sleep(0.3)
            _pag.write(query, interval=0.02)
            _pag.press("enter")
            set_konteks_aktif("spotify", state="spotify_search_results",
                              domain="", query=query)
            return ambil_respon_taktis_singkat()

        klik = lihat_dan_klik_layar("search box")
        if "and clicked it" in klik.lower():
            time.sleep(0.3)
            _pag.hotkey("ctrl", "a")
            _pag.press("backspace")
            _pag.write(query, interval=0.02)
            _pag.press("enter")
            return ambil_respon_taktis_singkat()

        _pag.hotkey("ctrl", "f")
        time.sleep(0.3)
        _pag.write(query, interval=0.02)
        _pag.press("enter")
        return ambil_respon_taktis_singkat()
    except _pag.FailSafeException:
        return "FAILSAFE tripped — the action was cancelled by the operator."
    except Exception as galat:
        return f"Contextual search failed: {galat}"


_TOMBOL_AMAN = frozenset([
    "enter", "tab", "esc", "space", "backspace", "delete", "insert",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "printscreen", "scrolllock", "pause", "capslock", "numlock",
])

_MODIFIER_AMAN = frozenset(["ctrl", "alt", "shift", "win"])

_ALIAS_TOMBOL = [
    ("panah atas", "up"), ("panah bawah", "down"),
    ("panah kiri", "left"), ("panah kanan", "right"),
    ("up arrow", "up"), ("down arrow", "down"),
    ("left arrow", "left"), ("right arrow", "right"),
    ("page up", "pageup"), ("page down", "pagedown"),
    ("spasi", "space"), ("hapus", "backspace"), ("escape", "esc"),
    ("print screen", "printscreen"), ("caps lock", "capslock"),
    ("num lock", "numlock"), ("scroll lock", "scrolllock"),
    ("control", "ctrl"), ("windows", "win"), ("command", "ctrl"),
]


def _normalisasi_tombol(nama):

    rendah = (nama or "").lower().strip()
    for frasa, tombol in _ALIAS_TOMBOL:
        if frasa == rendah:
            return tombol
    return rendah


def execute_input_command(command_type, params=None):

    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    if params is None:
        params = {}
    perintah = (command_type or "").lower().strip()

    try:
        if perintah == "type_text":

            teks = str(params.get("text", ""))
            if not teks.strip():
                return "Empty text — nothing typed."
            if len(teks) > 500:
                return "Text too long (500 characters max)."
            _pag.write(teks, interval=0.03)
            ringkas = teks if len(teks) <= 60 else teks[:57] + "..."
            return f"Typed: \"{ringkas}\""

        elif perintah == "press_key":

            tombol = _normalisasi_tombol(params.get("key", "enter"))
            if tombol not in _TOMBOL_AMAN:
                return (f"Key '{tombol}' is not allowed. "
                        "Examples: enter, tab, esc, space, up arrow.")
            _pag.press(tombol)
            return f"Pressed key: {tombol}"

        elif perintah == "hotkey":

            mentah_kunci = params.get("keys") or params.get("combo", "")
            if isinstance(mentah_kunci, str):
                mentah_kunci = [k.strip() for k in mentah_kunci.split("+")]
            daftar = [_normalisasi_tombol(k) for k in (mentah_kunci or [])]
            boleh = _MODIFIER_AMAN | _TOMBOL_AMAN | frozenset("abcdefghijklmnopqrstuvwxyz0123456789")
            if not (2 <= len(daftar) <= 3) or any(k not in boleh for k in daftar):
                return ("Invalid combination. Example: "
                        '{"command": "hotkey", "params": {"combo": "ctrl+c"}}.')
            if not any(k in _MODIFIER_AMAN for k in daftar):
                return "The combination must use ctrl/alt/shift/win."
            _pag.hotkey(*daftar)
            return f"Pressed combination: {'+'.join(daftar)}"

        elif perintah == "move_mouse":

            try:
                x = int(params.get("x", 0))
                y = int(params.get("y", 0))
            except (TypeError, ValueError):
                return "Coordinates x/y must be numbers. Example: {\"x\": 500, \"y\": 300}."
            try:
                lebar, tinggi = _pag.size()
            except Exception:
                lebar, tinggi = None, None
            if lebar and tinggi:
                x = max(0, min(x, lebar - 1))
                y = max(0, min(y, tinggi - 1))
            else:
                x, y = max(0, x), max(0, y)
            _pag.moveTo(x, y, duration=0.4)
            return f"Moved the cursor to {x}, {y}"

        elif perintah == "click_mouse":

            click_type = str(params.get("click_type", "left")).lower().strip()
            if click_type not in ("left", "right", "middle", "double"):
                return "Click type must be: left, right, middle, or double."
            if click_type == "double":
                _pag.doubleClick()
            else:
                _pag.click(button=click_type)
            return f"Clicked {click_type}"

        elif perintah == "scroll":

            try:
                amount = int(params.get("amount", 0))
            except (TypeError, ValueError):
                return "Scroll amount must be a number. Example: {\"amount\": -500}."
            if amount == 0:
                return "Scroll amount is zero — nothing scrolled."
            amount = max(-2000, min(amount, 2000))
            _pag.scroll(amount)
            arah = "up" if amount > 0 else "down"
            return f"Scrolled {arah} ({amount})."

        else:
            return (f"Unknown input command '{command_type}'. "
                    "Valid: type_text, press_key, hotkey, move_mouse, click_mouse, scroll.")

    except _pag.FailSafeException:
        return ("FAILSAFE tripped — the action was cancelled by the operator "
                "(cursor moved to the screen corner).")
    except Exception as e:
        return f"Failed to execute input: {e}"


def deteksi_intent_input(teks: str):

    import re
    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "


    if re.search(r"(?<!\w)(klik dua kali|klik ganda|double ?klik|double click|double-click)(?!\w)", rendah):
        return {"command": "click_mouse", "params": {"click_type": "double"}}
    if re.search(r"(?<!\w)(klik kanan|right click)(?!\w)", rendah):
        return {"command": "click_mouse", "params": {"click_type": "right"}}
    if re.search(r"(?<!\w)(klik tengah|middle click)(?!\w)", rendah):
        return {"command": "click_mouse", "params": {"click_type": "middle"}}
    if re.search(r"(?<!\w)(klik|klik kiri|click|left click)(?!\w)", rendah):
        return {"command": "click_mouse", "params": {"click_type": "left"}}


    cocok = re.match(r"\s*(tolong\s+|please\s+)?(ketikkan|ketik|tuliskan|tulis|type|write)\s+(.+)",
                     mentah, re.IGNORECASE)
    if cocok:
        isi = cocok.group(3).strip().strip("\"'")
        return {"command": "type_text", "params": {"text": isi}} if isi else None


    if re.search(r"(?<!\w)(tekan|pencet|press)(?!\w)", rendah):
        gabung = re.search(
            r"(?<!\w)(ctrl|control|alt|shift|win|windows)\s*\+?\s*([a-z0-9])(?!\w)",
            rendah)
        if gabung:
            modifier = _normalisasi_tombol(gabung.group(1))
            return {"command": "hotkey",
                    "params": {"keys": [modifier, gabung.group(2)]}}
        for frasa, tombol in _ALIAS_TOMBOL:
            if frasa in rendah:
                return {"command": "press_key", "params": {"key": tombol}}
        for tombol in sorted(_TOMBOL_AMAN, key=len, reverse=True):
            if re.search(rf"(?<!\w){re.escape(tombol)}(?!\w)", rendah):
                return {"command": "press_key", "params": {"key": tombol}}
        return None


    if (re.search(r"(?<!\w)(geser|gerakkan|gerakan|pindah|arahkan|move|drag)(?!\w)", rendah)
            and re.search(r"(?<!\w)(mouse|kursor|kursornya|cursor|pointer)(?!\w)", rendah)):
        angka = re.findall(r"\d+", rendah)
        if len(angka) >= 2:
            return {"command": "move_mouse",
                    "params": {"x": int(angka[0]), "y": int(angka[1])}}
        return None


    if re.search(r"(?<!\w)scroll(?!\w)", rendah):
        if re.search(r"(?<!\w)(atas|naik|ke atas|up|upwards)(?!\w)", rendah):
            return {"command": "scroll", "params": {"amount": 500}}
        if re.search(r"(?<!\w)(bawah|turun|ke bawah|down|downwards)(?!\w)", rendah):
            return {"command": "scroll", "params": {"amount": -500}}
        return None

    return None


def baca_clipboard():

    if not _PYPERCLIP_TERSEDIA or _pyperclip is None:
        return _PESAN_INSTALL_PYPERCLIP
    try:
        return str(_pyperclip.paste() or "")
    except Exception:
        return ""


_PEMICU_CLIPBOARD_EN = ("audit my clipboard",)
_PEMICU_CLIPBOARD_ID = ("audit clipboard", "cek clipboard", "periksa clipboard")


def deteksi_intent_clipboard(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if _frasa_utuh(rendah, *_PEMICU_CLIPBOARD_EN):
        return "en"
    if _frasa_utuh(rendah, *_PEMICU_CLIPBOARD_ID):
        return "id"
    return None


_PEMICU_LOCKDOWN = ("initiate lockdown", "emergency lockdown",
                    "lockdown laptop", "isolasi sistem")


def deteksi_perintah_lockdown(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return False
    return bool(_frasa_utuh(f" {mentah.lower()} ", *_PEMICU_LOCKDOWN))


_LOCKDOWN_EXE_BERISIKO = ("chrome.exe", "msedge.exe", "powershell.exe", "cmd.exe")


def eksekusi_lockdown_darurat():


    for perintah in (["ipconfig", "/release"],
                     ["netsh", "wlan", "disconnect"]):
        try:
            subprocess.run(perintah, capture_output=True, timeout=15)
        except Exception:
            continue

    _tekan_vk(_VK_MEDIA["mute"])

    try:
        u32 = _user32()
        if u32 is not None:
            u32.LockWorkStation()
    except Exception:
        pass

    for exe in _LOCKDOWN_EXE_BERISIKO:
        try:
            subprocess.run(["taskkill", "/IM", exe, "/F", "/T"],
                           capture_output=True, text=True, timeout=10)
        except Exception:
            continue
    return ("[SYSTEM] Lockdown protocol engaged. All networks isolated "
            "and workstation secured.")


_PROSES_SHELL_MENCURIGAKAN = frozenset({
    "powershell", "cmd", "python", "nc", "bash",
})
_PORT_EKSPLOITASI = frozenset({4444, 1337, 6667, 3389, 445})
_NETSCAN_MAKS_BARIS = 25


_PEMICU_THREAT_EN = ("network threat hunt", "threat hunt",
                     "threat hunting", "hunt network threats",
                     "scan active connections", "scan connections",
                     "audit network connections", "audit connections",
                     "suspicious connections", "check for backdoor",
                     "any backdoor", "backdoor in my network")
_PEMICU_THREAT_ID = ("cek keamanan jaringan", "keamanan jaringan",
                     "audit koneksi jaringan", "audit jaringan",
                     "cek koneksi mencurigakan", "koneksi mencurigakan",
                     "apakah ada backdoor", "ada backdoor",
                     "backdoor di jaringan", "backdoor di jaringanku",
                     "periksa koneksi jaringan", "cek koneksi jaringan",
                     "pindai koneksi", "scan koneksi")


def deteksi_intent_threat_hunt(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if _frasa_utuh(rendah, *_PEMICU_THREAT_EN):
        return "en"
    if _frasa_utuh(rendah, *_PEMICU_THREAT_ID):
        return "id"
    return None


def _adalah_loopback(ip):

    return (ip or "").strip().lower() in ("127.0.0.1", "::1", "localhost")


def _normalisasi_nama_proses(nama):

    dasar = (nama or "").strip().lower()
    if dasar.endswith(".exe"):
        dasar = dasar[:-4]
    return dasar


def _nilai_koneksi(proto, lokal_ip, lokal_port, remote_ip, remote_port,
                   status, pid, proses):

    status = (status or "").upper()
    if status == "LISTENING":
        status = "LISTEN"
    if proto == "UDP" and not status:
        status = "ESTABLISHED" if remote_ip else "LISTEN"
    if status == "LISTEN":


        if (_adalah_loopback(lokal_ip)
                and lokal_port not in _PORT_EKSPLOITASI):
            return None, None
    elif status in ("ESTABLISHED", "SYN_SENT"):
        if not remote_ip:
            return None, None
        if _adalah_loopback(lokal_ip) and _adalah_loopback(remote_ip):
            return None, None
    else:
        return None, None
    tanda = []
    if status == "LISTEN":
        if lokal_port in _PORT_EKSPLOITASI:
            tanda.append("LISTEN-RISK")
    else:
        if (_normalisasi_nama_proses(proses)
                in _PROSES_SHELL_MENCURIGAKAN):
            tanda.append("SHELL→KELUAR")
        for port in (lokal_port, remote_port):
            if port in _PORT_EKSPLOITASI:
                tanda.append(f"PORT-RISK:{port}")
                break
        if status == "SYN_SENT":
            tanda.append("SYN-SENT")
    baris = {"proto": proto,
             "lokal": f"{lokal_ip or '*'}:{lokal_port}",
             "remote": (f"{remote_ip}:{remote_port}" if remote_ip else "*"),
             "status": status, "pid": pid or 0,
             "proses": (proses or "?")[:24], "tanda": tanda}
    temuan = None
    if tanda:
        temuan = (f"{baris['proses']} (PID {baris['pid']}) {baris['lokal']} → "
                  f"{baris['remote']} [{', '.join(tanda)}]")
    return baris, temuan


def _kumpulkan_koneksi_psutil():

    import socket as _sok
    try:
        koneksi = _psutil.net_connections(kind="inet")
    except Exception:
        return None
    baris_semua, temuan, tersaring = [], [], 0
    cache_nama = {}
    for kon in koneksi or []:
        try:
            proto = "TCP" if kon.type == _sok.SOCK_STREAM else "UDP"
            lip = kon.laddr[0] if kon.laddr else ""
            lport = int(kon.laddr[1]) if kon.laddr else 0
            rip = kon.raddr[0] if kon.raddr else ""
            rport = int(kon.raddr[1]) if kon.raddr else 0
            status = kon.status or ""
            pid = kon.pid or 0
        except Exception:
            tersaring += 1
            continue
        proses = "?"
        if pid:
            if pid not in cache_nama:
                try:
                    cache_nama[pid] = _psutil.Process(pid).name() or "?"
                except Exception:
                    cache_nama[pid] = "?"
            proses = cache_nama[pid]
        baris, temu = _nilai_koneksi(proto, lip, lport, rip, rport,
                                     status, pid, proses)
        if baris is None:
            tersaring += 1
            continue
        baris_semua.append(baris)
        if temu:
            temuan.append(temu)

    baris_semua.sort(key=lambda b: (not b["tanda"], b["proses"]))
    total = len(baris_semua)
    return {"baris": baris_semua[:_NETSCAN_MAKS_BARIS], "temuan": temuan,
            "total": total,
            "terpotong": max(0, total - _NETSCAN_MAKS_BARIS),
            "tersaring": tersaring, "sumber": "psutil", "galat": ""}


def _urai_titik_endpoint(teks):

    teks = (teks or "").strip()
    if teks in ("*:*", "*"):
        return "", 0
    if teks.startswith("[") and "]:" in teks:
        ip, _, port = teks[1:].partition("]:")
    else:
        ip, _, port = teks.rpartition(":")
    try:
        return ip, int(port)
    except ValueError:
        return ip, 0


def _peta_pid_ke_proses_tasklist():

    peta = {}
    try:
        hasil = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                               capture_output=True, text=True, timeout=10)
        keluaran = hasil.stdout or ""
    except Exception:
        return peta
    try:
        for kolom in csv.reader(io.StringIO(keluaran)):
            if len(kolom) >= 2:
                try:
                    peta[int(kolom[1])] = (kolom[0] or "?").strip('"')
                except ValueError:
                    continue
    except Exception:
        pass
    return peta


def _kumpulkan_koneksi_netstat():

    try:
        hasil = subprocess.run(["netstat", "-ano"], capture_output=True,
                               text=True, timeout=15)
        keluaran = hasil.stdout or ""
    except Exception:
        return None
    if not keluaran.strip():
        return None
    peta = _peta_pid_ke_proses_tasklist()
    baris_semua, temuan, tersaring = [], [], 0
    for baris_teks in keluaran.splitlines():
        bagian = baris_teks.split()
        if len(bagian) < 4 or bagian[0] not in ("TCP", "UDP"):
            continue
        try:
            proto = bagian[0]
            lip, lport = _urai_titik_endpoint(bagian[1])
            if proto == "TCP":
                rip, rport = _urai_titik_endpoint(bagian[2])
                status, pid = bagian[3], int(bagian[4])
            else:
                rip, rport = _urai_titik_endpoint(bagian[2])
                status, pid = "", int(bagian[3])
        except (ValueError, IndexError):
            continue
        baris, temu = _nilai_koneksi(proto, lip, lport, rip, rport,
                                     status, pid, peta.get(pid, "?"))
        if baris is None:
            tersaring += 1
            continue
        baris_semua.append(baris)
        if temu:
            temuan.append(temu)
    baris_semua.sort(key=lambda b: (not b["tanda"], b["proses"]))
    total = len(baris_semua)
    return {"baris": baris_semua[:_NETSCAN_MAKS_BARIS], "temuan": temuan,
            "total": total,
            "terpotong": max(0, total - _NETSCAN_MAKS_BARIS),
            "tersaring": tersaring, "sumber": "netstat", "galat": ""}


def kumpulkan_koneksi_aktif():

    if _PSUTIL_TERSEDIA and _psutil is not None:
        data = _kumpulkan_koneksi_psutil()
        if data is not None:
            return data
    data = _kumpulkan_koneksi_netstat()
    if data is not None:
        return data
    return {"baris": [], "temuan": [], "total": 0, "terpotong": 0,
            "tersaring": 0, "sumber": "",
            "galat": ("[NETSCAN ERROR] Tidak bisa membaca koneksi: psutil "
                      "tak tersedia dan netstat gagal.")}


def susun_tabel_netscan(data):

    data = data or {}
    if data.get("galat"):
        return f"[NETSCAN]\n{data['galat']}"
    baris = data.get("baris") or []
    judul = (f"[NETSCAN] {data.get('total', len(baris))} koneksi eksternal "
             f"({len(data.get('temuan') or [])} ditandai) via "
             f"{data.get('sumber') or '?'}; "
             f"{data.get('tersaring', 0)} loopback disaring")
    if not baris:
        return judul + "\n(tidak ada koneksi eksternal aktif)"
    keluar = [judul,
              f"{'PROTO':<5} {'LOKAL':<22} {'REMOTE':<22} "
              f"{'STATUS':<11} {'PID':>5}  PROSES"]
    for b in baris:
        taka = f" [{','.join(b['tanda'])}]" if b.get("tanda") else ""
        keluar.append(f"{b['proto']:<5} {b['lokal']:<22} {b['remote']:<22} "
                      f"{b['status']:<11} {b['pid']:>5}  {b['proses']}{taka}")
    if data.get("terpotong"):
        keluar.append(f"... +{data['terpotong']} baris dipotong "
                      f"(maks {_NETSCAN_MAKS_BARIS})")
    return "\n".join(keluar)


def jalankan_threat_hunt_jaringan(bahasa="id"):

    data = kumpulkan_koneksi_aktif()
    if data.get("galat"):
        return {"tabel": susun_tabel_netscan(data), "vonis": data["galat"],
                "temuan": [], "sumber": data.get("sumber", "")}
    tabel = susun_tabel_netscan(data)
    if not data.get("baris"):
        inggris = str(bahasa or "id").lower().startswith("en")
        vonis = ("SAFE — no active external network connections right now."
                 if inggris else
                 "AMAN — tidak ada koneksi jaringan eksternal yang aktif "
                 "saat ini.")
        return {"tabel": tabel, "vonis": vonis, "temuan": [],
                "sumber": data.get("sumber", "")}
    from server import ai_engine as _ai
    konteks = tabel
    if data.get("temuan"):
        konteks += ("\n\nHeuristic flags:\n"
                    + "\n".join(f"- {t}" for t in data["temuan"]))
    vonis = _ai.query_soc_evaluator(konteks, bahasa, _ai._PROMPT_SOC_NETWORK)
    return {"tabel": tabel, "vonis": vonis,
            "temuan": data.get("temuan", []),
            "sumber": data.get("sumber", "")}


_VK_MEDIA = {
    "play_pause": 0xB3,
    "next_track": 0xB0,
    "prev_track": 0xB1,
    "vol_up": 0xAF,
    "vol_down": 0xAE,
    "mute": 0xAD,
}


def _user32():

    try:
        import ctypes
        windll = getattr(ctypes, "windll", None)
        return windll.user32 if windll is not None else None
    except Exception:
        return None


_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79


def dapatkan_geometri_layar_virtual():

    try:
        u32 = _user32()
        if u32 is not None:
            ox = int(u32.GetSystemMetrics(_SM_XVIRTUALSCREEN))
            oy = int(u32.GetSystemMetrics(_SM_YVIRTUALSCREEN))
            vw = int(u32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
            vh = int(u32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
            if vw > 0 and vh > 0:
                return (ox, oy, vw, vh)
    except Exception:
        pass
    try:
        if _PYAUTOGUI_TERSEDIA and _pag is not None:
            lebar, tinggi = _pag.size()
            if int(lebar) > 0 and int(tinggi) > 0:
                return (0, 0, int(lebar), int(tinggi))
    except Exception:
        pass
    return (0, 0, 1920, 1080)


def dapatkan_origin_layar_virtual():

    try:
        ox, oy, _, _ = dapatkan_geometri_layar_virtual()
        return (ox, oy)
    except Exception:
        return (0, 0)


def posisi_kursor_saat_ini():

    try:
        if _PYAUTOGUI_TERSEDIA and _pag is not None:
            pos = _pag.position()
            return (int(pos[0]), int(pos[1]))
    except Exception:
        pass
    try:
        import ctypes
        u32 = _user32()
        if u32 is None:
            return None

        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        titik = _POINT()
        if u32.GetCursorPos(ctypes.byref(titik)):
            return (int(titik.x), int(titik.y))
    except Exception:
        pass
    return None


def _tekan_vk(vk, kali=1, jeda=0.06):

    u32 = _user32()
    if u32 is None:
        return False
    try:
        for _ in range(max(1, int(kali))):
            u32.keybd_event(vk, 0, 0, 0)
            u32.keybd_event(vk, 0, 2, 0)
            if kali > 1:
                time.sleep(jeda)
        return True
    except Exception:
        return False


def _frasa_utuh(rendah, *frasa):

    return any(re.search(rf"(?<!\w){re.escape(f)}(?!\w)", rendah)
               for f in frasa)


def _simpan_screenshot_ke_pictures():

    try:
        if ImageGrab is not None:
            try:
                img = ImageGrab.grab(all_screens=True)
            except Exception:
                img = ImageGrab.grab()
        elif _PYAUTOGUI_TERSEDIA and _pag is not None:
            img = _pag.screenshot()
        else:
            return None, ("[SCREEN ERROR] Failed to capture the screen: PIL.ImageGrab "
                          "and pyautogui are unavailable.")
    except Exception as galat:
        return None, f"[SCREEN ERROR] Failed to capture the screen: {galat}"
    try:
        folder = Path.home() / "Pictures"
        folder.mkdir(parents=True, exist_ok=True)
        nama = f"arvi_screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path = folder / nama
        img.convert("RGB").save(path, "PNG")
    except Exception as galat:
        return None, f"[SCREEN ERROR] Failed to save the screenshot: {galat}"
    try:
        kecil = img.copy()
        if kecil.width > 1280:
            skala = 1280 / kecil.width
            kecil = kecil.resize((1280, max(1, int(kecil.height * skala))))
        buf = io.BytesIO()
        kecil.convert("RGB").save(buf, "JPEG", quality=70)
        data_url = ("data:image/jpeg;base64,"
                    + base64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        data_url = ""
    return str(path), data_url


_SK_SMTC_STATUS = (
    "$t=[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager,"
    "Windows.Media.Control,ContentType=WindowsRuntime];"
    "$m=[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]"
    "::RequestAsync().GetAwaiter().GetResult();"
    "$s=$m.GetCurrentSession();"
    "if($s -eq $null){'none'}else{$s.GetPlaybackInfo().PlaybackStatus}"
)


def _status_media_smtc():

    try:
        hasil = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _SK_SMTC_STATUS],
            capture_output=True, text=True, timeout=8)
    except Exception:
        return None
    try:
        status = (hasil.stdout or "").strip().lower()
    except Exception:
        return None
    if status.startswith("playing"):
        return "playing"
    if status.startswith("paused"):
        return "paused"
    if status.startswith(("stopped", "closed", "opened", "changing", "none")):
        return "stopped"
    return None


def _putar_media():

    status = _status_media_smtc()
    if status == "playing":
        return "[SYSTEM] Spotify is already playing."
    if _tekan_vk(_VK_MEDIA["play_pause"]):
        if status is None:
            return "[SYSTEM] Pressed media Play (playback state unreadable)."
        return "[SYSTEM] Playing Spotify."
    return "Failed to send the media key (not Windows?)."


def _jeda_media():

    status = _status_media_smtc()
    if status in ("paused", "stopped"):
        return "[SYSTEM] Spotify is already paused."
    if _tekan_vk(_VK_MEDIA["play_pause"]):
        if status is None:
            return "[SYSTEM] Pressed media Pause (playback state unreadable)."
        return "[SYSTEM] Paused Spotify."
    return "Failed to send the media key (not Windows?)."


_KATA_PENGHALANG_MEDIA_GLOBAL = (
    "open", "launch", "start", "buka", "bukakan", "jalankan",
    "close", "tutup", "search", "cari", "carikan", "find",
    "googling", "type", "ketik", "write", "tulis", "click",
    "klik", "pilih", "select", "then", "and", "lalu",
    "kemudian", "terus", "habis itu", "setelah itu", "dan",
    "youtube", "yt", "chrome", "edge", "browser", "google",
    "video", "videonya", "videoclip", "clip", "pertama", "first",
    "it", "this", "that", "itu", "ini",
)

_FRASA_PLAY_MURNI = frozenset({
    "play", "resume", "lanjutkan",
    "play spotify", "putar spotify", "lanjutkan spotify", "resume spotify",
    "play music", "putar musik", "lanjutkan musik", "resume music", "stel musik",
    "play song", "putar lagu", "lanjutkan lagu", "resume song", "stel lagu",
    "play the music", "play the song",
})

_FRASA_PAUSE_MURNI = frozenset({
    "pause", "jeda", "stop",
    "pause spotify", "jeda spotify", "hentikan spotify", "stop spotify",
    "pause music", "jeda musik", "hentikan musik", "stop music", "pause musik", "stop musik",
    "pause song", "jeda lagu", "hentikan lagu", "stop song", "pause lagu", "stop lagu",
    "pause the music", "stop the music", "pause the song", "stop the song",
})


def _perintah_media_murni(mentah: str, rendah: str):


    if _frasa_utuh(rendah, *_KATA_PENGHALANG_MEDIA_GLOBAL):
        return None
    if re.search(r"(?<!\w)(putar|stel|play)\s+(lagu|musik|video|song|music|track)\s+\S", rendah):
        return None

    inti = re.sub(r"(?i)^\s*(?:tolong\s+|please\s+|coba\s+|arvi\s+)+", "", mentah).strip()
    inti = re.sub(r"(?i)\s+(?:dong|sekarang|now|please|ya)\s*$", "", inti).strip()
    inti = re.sub(r"\s+", " ", inti.lower()).strip(" .!?,")
    if inti in _FRASA_PAUSE_MURNI:
        return "pause"
    if inti in _FRASA_PLAY_MURNI:
        return "play"
    return None


def deteksi_dan_eksekusi_kontrol_sistem(teks, pratinjau=None):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "


    aksi_media = _perintah_media_murni(mentah, rendah)
    if aksi_media == "pause":
        return _jeda_media()
    if aksi_media == "play":
        return _putar_media()

    if _frasa_utuh(rendah, "lagu selanjutnya", "lagu berikutnya", "next lagu",
                   "next spotify", "skip lagu", "lagu lanjut", "next song",
                   "next track", "skip song", "skip track", "skip"):
        if _tekan_vk(_VK_MEDIA["next_track"]):
            return "Skipped to the next song."
        return "Failed to send the next key (not Windows?)."
    if _frasa_utuh(rendah, "lagu sebelumnya", "previous spotify",
                   "previous lagu", "prev lagu", "lagu mundur",
                   "balik lagu", "previous song", "previous track",
                   "prev song", "prev track"):
        if _tekan_vk(_VK_MEDIA["prev_track"]):
            return "Back to the previous song."
        return "Failed to send the previous key (not Windows?)."

    if _frasa_utuh(rendah, "kecilkan volume", "kecilkan suara",
                   "turunkan volume", "turunkan suara", "kurangi volume",
                   "kurangi suara", "volume turun", "volume down",
                   "decrease volume", "lower volume", "turn down volume"):
        if _tekan_vk(_VK_MEDIA["vol_down"], kali=5):
            return "Turned the laptop volume down."
        return "Failed to press volume-down (not Windows?)."
    if _frasa_utuh(rendah, "besarkan volume", "besarkan suara",
                   "naikkan volume", "naikkan suara", "tambah volume",
                   "tambah suara", "keraskan suara laptop",
                   "keraskan volume", "volume naik", "volume up",
                   "increase volume", "raise volume", "turn up volume"):
        if _tekan_vk(_VK_MEDIA["vol_up"], kali=5):
            return "Turned the laptop volume up."
        return "Failed to press volume-up (not Windows?)."
    if ("tab" not in rendah and _frasa_utuh(rendah, "mute laptop", "mute",
                                            "bisukan laptop", "bisukan",
                                            "bisukan speaker", "unmute laptop",
                                            "unmute", "mute the speaker")):
        if _tekan_vk(_VK_MEDIA["mute"]):
            return "Muted the laptop speaker."
        return "Failed to press mute (not Windows?)."

    if _frasa_utuh(rendah, "minimize semua", "minimise semua",
                   "minimalkan semua", "tampilkan desktop",
                   "sembunyikan semua jendela", "minimize all",
                   "show desktop", "show the desktop"):
        return execute_input_command("hotkey", {"combo": "win+d"})
    if _frasa_utuh(rendah, "minimize jendela", "minimise jendela",
                   "minimalkan jendela", "kecilkan jendela", "minimize",
                   "minimise", "minimize window", "minimize the window"):
        return execute_input_command("hotkey", {"combo": "win+down"})
    if _frasa_utuh(rendah, "maximize jendela", "maximise jendela",
                   "maksimalkan jendela", "maksimalkan layar",
                   "perbesar layar", "perbesar jendela", "maksimalkan",
                   "maximize window", "maximize the window", "maximize"):
        return execute_input_command("hotkey", {"combo": "win+up"})
    if _frasa_utuh(rendah, "beralih jendela", "ganti jendela",
                   "switch window", "switch windows"):
        return execute_input_command("hotkey", {"combo": "alt+tab"})

    if (_frasa_utuh(rendah, "arahkan", "pindahkan", "pindah", "geser", "move")
            and ("monitor" in rendah or "layar kanan" in rendah
                 or "layar kiri" in rendah or "layar sebelah" in rendah
                 or "right monitor" in rendah or "left monitor" in rendah
                 or "other monitor" in rendah or "second monitor" in rendah)):
        if re.search(r"(?<!\w)(kiri|left|monitor\s*1|layar\s*1)(?!\w)",
                     rendah):
            arah = "left"
        else:
            arah = "right"
        kanonis = _kanonis_target(rendah)
        if kanonis is not None:
            daftar_exe = APP_DATABASE[kanonis].get("tutup") or []
            if daftar_exe:
                _fokus_jendela(daftar_exe[0])
                time.sleep(0.25)
        hasil = execute_input_command("hotkey",
                                      {"combo": f"win+shift+{arah}"})
        if "invalid" in hasil.lower() or "error" in hasil.lower():
            return hasil
        return (f"Moved the window to the {arah} monitor "
                f"(Win+Shift+{arah.title()}).")
    if _frasa_utuh(rendah, "kunci layar", "kunci laptop", "lock laptop",
                   "lock layar", "lock screen", "lock the screen",
                   "lock the laptop"):
        u32 = _user32()
        if u32 is None:
            return "Lock screen is only supported on Windows."
        try:
            u32.LockWorkStation()
            return "Locked the laptop screen."
        except Exception as galat:
            return f"Failed to lock the screen: {galat}"
    if _frasa_utuh(rendah, "ambil screenshot", "potret layar", "screenshot",
                   "tangkapan layar", "foto layar", "take screenshot",
                   "take a screenshot", "capture screen",
                   "capture the screen"):
        path, data_url = _simpan_screenshot_ke_pictures()
        if path is None:
            return data_url
        if pratinjau is not None and data_url:
            pratinjau["image"] = data_url
        return f"Screenshot saved to {path}."
    return None


_PERINTAH_AUDIT_FISIK = (
    ("ping 8.8.8.8 -n 4", 8),
    ("tracert -d -h 10 8.8.8.8", 45),
    ("netstat -ano", 6),
)
_TARGET_AUDIT = "8.8.8.8"


def _jalankan_tangkap(perintah, timeout=90):

    try:
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        hasil = subprocess.run(
            perintah, capture_output=True, text=True, timeout=timeout,
            errors="replace", shell=False, creationflags=flags)
        return (hasil.stdout or "").strip()
    except Exception:
        return ""


def _urai_ping(keluaran):

    teks = keluaran or ""
    balasan = []
    for cocok in re.finditer(
            r"Reply from ([\d.]+):.*?(?:time|waktu)[=<](\d+)\s*ms",
            teks, re.IGNORECASE):
        ttl = None
        potong = teks[cocok.start():cocok.end() + 24]
        temu_ttl = re.search(r"TTL[=](\d+)", potong, re.IGNORECASE)
        if temu_ttl:
            try:
                ttl = int(temu_ttl.group(1))
            except ValueError:
                ttl = None
        try:
            ms = int(cocok.group(2))
        except ValueError:
            ms = None
        balasan.append({"dari": cocok.group(1), "waktu_ms": ms,
                        "ttl": ttl})
    angka = {}
    for kunci, pola in (
            ("terkirim", r"(?:Sent|Dikirim)\s*=\s*(\d+)"),
            ("diterima", r"(?:Received|Diterima)\s*=\s*(\d+)"),
            ("hilang", r"(?:Lost|Hilang)\s*=\s*(\d+)"),
            ("persen_hilang", r"\(\s*(\d+)\s*%\s*(?:loss|hilang)?\s*\)"),
            ("rata_ms", r"(?:Average|Rata-rata)\s*=\s*(\d+)\s*ms")):
        temu = re.search(pola, teks, re.IGNORECASE)
        angka[kunci] = int(temu.group(1)) if temu else None
    mentah = [b.strip()[:120] for b in teks.splitlines()
              if b.strip()][:14]
    return {"target": _TARGET_AUDIT, "balasan": balasan[:8],
            "mentah": mentah, **angka}


def _urai_tracert(keluaran, maks_hop=10):

    daftar = []
    for baris in (keluaran or "").splitlines():
        cocok = re.match(r"\s*(\d+)\s+(.*)$", baris.rstrip())
        if not cocok:
            continue
        try:
            hop = int(cocok.group(1))
        except ValueError:
            continue
        sisa = cocok.group(2).strip()
        waktu = []
        for temu in re.finditer(r"(?:(\d+)\s*ms|<1\s*ms|\*)", sisa,
                                re.IGNORECASE):
            if temu.group(0).strip() == "*":
                waktu.append(None)
            elif temu.group(1) is None:
                waktu.append(0)
            else:
                try:
                    waktu.append(int(temu.group(1)))
                except ValueError:
                    waktu.append(None)
        token = sisa.split()
        titik = token[-1] if token else ""
        if titik == "*" or titik.lower().startswith("request"):
            titik = "*"
        daftar.append({"hop": hop, "ms": waktu[:3],
                       "titik": titik[:64],
                       "mentah": re.sub(r"\s+", " ",
                                        baris.strip())[:100]})
        if len(daftar) >= maks_hop:
            break
    return daftar


def _fokus_jendela_konsol():

    try:
        u32 = _user32()
        if u32 is None:
            return False
        import ctypes
        target = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                            ctypes.c_void_p)
        def _enum(hwnd_e, _lparam):
            try:
                if u32.IsWindowVisible(hwnd_e):
                    buf = ctypes.create_unicode_buffer(256)
                    u32.GetWindowTextW(hwnd_e, buf, 256)
                    judul = (buf.value or "").lower()
                    if ("command prompt" in judul
                            or judul.strip().endswith("cmd.exe")
                            or "administrator: command prompt" in judul):
                        target.append(hwnd_e)
            except Exception:
                pass
            return True

        u32.EnumWindows(_enum, 0)
        if not target:
            return False
        try:
            u32.ShowWindow(target[0], 9)
        except Exception:
            pass
        return bool(u32.SetForegroundWindow(target[0]))
    except Exception:
        return False


def fokuskan_jendela_hud():

    try:
        u32 = _user32()
        if u32 is None:
            return False
        import ctypes
        target = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                            ctypes.c_void_p)
        def _enum(hwnd_e, _lparam):
            try:
                if u32.IsWindowVisible(hwnd_e):
                    buf = ctypes.create_unicode_buffer(256)
                    u32.GetWindowTextW(hwnd_e, buf, 256)
                    if "arvi" in (buf.value or "").lower():
                        target.append(hwnd_e)
            except Exception:
                pass
            return True

        u32.EnumWindows(_enum, 0)
        if not target:
            return False
        try:
            u32.ShowWindow(target[0], 9)
        except Exception:
            pass
        return bool(u32.SetForegroundWindow(target[0]))
    except Exception:
        return False


def _tampilkan_demo_cmd(perintah_dan_jeda=_PERINTAH_AUDIT_FISIK):

    if os.name != "nt":
        return False
    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return False
    proses = None
    try:
        proses = subprocess.Popen(
            ["cmd.exe", "/k"],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        time.sleep(1.2)
        _fokus_jendela_konsol()
        time.sleep(0.4)
        for perintah, jeda in perintah_dan_jeda:
            _pag.write(perintah, interval=0.04)
            time.sleep(0.3)
            _pag.press("enter")
            time.sleep(max(1, int(jeda)))
        _pag.write("exit", interval=0.04)
        time.sleep(0.3)
        _pag.press("enter")
        try:
            proses.wait(timeout=8)
        except Exception:
            pass
        return True
    except Exception:
        return False
    finally:
        if proses is not None:
            try:
                if proses.poll() is None:
                    proses.terminate()
            except Exception:
                pass


def jalankan_audit_koneksi_fisik(bahasa="id"):

    tangkap = {}

    def _isi(kunci, perintah, timeout):
        tangkap[kunci] = _jalankan_tangkap(perintah.split(), timeout)

    utas = [
        threading.Thread(target=_isi, args=("ping", "ping 8.8.8.8 -n 4",
                                            30), daemon=True),
        threading.Thread(target=_isi,
                         args=("tracert", "tracert -d -h 10 8.8.8.8",
                               100), daemon=True),
    ]
    for utan in utas:
        try:
            utan.start()
        except Exception:
            pass
    demo = _tampilkan_demo_cmd()
    for utan in utas:
        try:
            utan.join()
        except Exception:
            pass

    ping = _urai_ping(tangkap.get("ping", ""))
    tracert = _urai_tracert(tangkap.get("tracert", ""))
    data = kumpulkan_koneksi_aktif()
    tabel = susun_tabel_netscan(data)
    if data.get("galat"):
        vonis = data["galat"]
    elif not data.get("baris"):
        inggris = str(bahasa or "id").lower().startswith("en")
        vonis = ("SAFE — no active external network connections right now."
                 if inggris else
                 "AMAN — tidak ada koneksi jaringan eksternal yang aktif "
                 "saat ini.")
    else:
        from server import ai_engine as _ai
        konteks = tabel
        if data.get("temuan"):
            konteks += ("\n\nHeuristic flags:\n"
                        + "\n".join(f"- {t}" for t in data["temuan"]))
        vonis = _ai.query_soc_evaluator(konteks, bahasa,
                                        _ai._PROMPT_SOC_NETWORK)
    return {"ping": ping, "tracert": tracert,
            "koneksi": {"baris": data.get("baris", []),
                        "temuan": data.get("temuan", []),
                        "total": data.get("total", 0),
                        "terpotong": data.get("terpotong", 0),
                        "tersaring": data.get("tersaring", 0),
                        "sumber": data.get("sumber", "")},
            "tabel": tabel, "vonis": vonis,
            "temuan": data.get("temuan", []),
            "demo_terlihat": bool(demo),
            "galat": data.get("galat", "")}
