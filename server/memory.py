import json
import re
import threading
from pathlib import Path

import requests

from server.config import BASETEN_API_KEY, META_API_KEY, BASETEN_URL, META_URL

MEMORY_PATH = Path(__file__).resolve().parent / "arvi_memory.json"

conversation_history: list = []


def _memori_bawaan():
    return {"profil_user": {"nama": "", "preferensi": "", "gaya_kerja": ""},
            "fakta_penting": [], "ringkasan_terakhir": "", "interaksi": 0,
            "pengingat": [], "briefing": {"aktif": False, "jam": 7,
                                          "terakhir": ""}}


def _muat_memori():
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _memori_bawaan()
        keluar = _memori_bawaan()
        profil = data.get("profil_user") or {}
        for kunci in ("nama", "preferensi", "gaya_kerja"):
            if profil.get(kunci):
                keluar["profil_user"][kunci] = str(profil[kunci])[:200]
        fakta = data.get("fakta_penting") or []
        keluar["fakta_penting"] = [str(f)[:500] for f in fakta if str(f).strip()][-100:]
        keluar["ringkasan_terakhir"] = str(data.get("ringkasan_terakhir") or "")[:1000]
        keluar["interaksi"] = int(data.get("interaksi") or 0)
        ingat = data.get("pengingat") or []
        keluar["pengingat"] = [p for p in ingat
                               if isinstance(p, dict) and p.get("waktu")][-50:]
        brif = data.get("briefing") or {}
        try:
            jam = max(0, min(int(brif.get("jam", 7)), 23))
        except (TypeError, ValueError):
            jam = 7
        keluar["briefing"] = {"aktif": bool(brif.get("aktif", False)),
                              "jam": jam,
                              "terakhir": str(brif.get("terakhir") or "")}
        return keluar
    except Exception:
        return _memori_bawaan()


memori_ltm = _muat_memori()


last_vision_frame = {"image": None, "timestamp": 0}


def _simpan_memori():
    try:
        MEMORY_PATH.write_text(json.dumps(memori_ltm, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    except Exception as galat:
        print(f"[!] Failed to save LTM memory: {galat}")


def _tambah_fakta(fakta):
    fakta = re.sub(r"\s+", " ", (fakta or "")).strip()
    if not fakta or fakta in memori_ltm["fakta_penting"]:
        return False
    memori_ltm["fakta_penting"].append(fakta[:500])
    memori_ltm["fakta_penting"] = memori_ltm["fakta_penting"][-100:]
    return True


_PEMICU_INGAT = ("ingat ya", "ingat ini", "tolong ingat", "ingat bahwa",
                 "catat bahwa", "catat ini", "tolong catat",
                 "jangan lupa bahwa", "jangan lupa kalau", "jangan lupa",
                 "remember that", "remember this", "please remember",
                 "note that", "take note that", "do not forget",
                 "don't forget")


def _simpan_fakta_eksplisit(teks):

    if not teks:
        return None
    cocok_nama = re.search(
        r"(?:namaku|nama saya|nama aku|panggil aku|panggil saya|my name is|call me)\s+(?:adalah\s+|is\s+)?([a-zA-Z][a-zA-Z .']{1,39})",
        teks)
    if cocok_nama:
        nama = re.sub(r"\s+", " ", cocok_nama.group(1)).strip().strip(".,!?")
        if nama:
            memori_ltm["profil_user"]["nama"] = nama
            _tambah_fakta(f"User's name is {nama}.")
            _simpan_memori()
            return f"user's name is {nama}"
    rendah = teks.lower()
    for pemicu in _PEMICU_INGAT:
        pos = rendah.find(pemicu)
        if pos >= 0:
            fakta = teks[pos + len(pemicu):].strip().strip(":,.-– ").strip()
            if not fakta:
                fakta = teks.strip()
            _tambah_fakta(fakta)
            _simpan_memori()
            return fakta
    return None


def _blok_memori_untuk_persona():
    profil = memori_ltm.get("profil_user") or {}
    baris = []
    if profil.get("nama"):
        baris.append(f"- User's name: {profil['nama']} (greet them warmly).")
    if profil.get("preferensi"):
        baris.append(f"- Preferences: {profil['preferensi']}")
    if profil.get("gaya_kerja"):
        baris.append(f"- Work style: {profil['gaya_kerja']}")
    for fakta in (memori_ltm.get("fakta_penting") or [])[-15:]:
        baris.append(f"- {fakta}")
    if memori_ltm.get("ringkasan_terakhir"):
        baris.append(f"- Past chat summary: {memori_ltm['ringkasan_terakhir']}")
    if not baris:
        return "No permanent memory about the user yet."
    return "\n".join(baris)


def _instruksi_lawan_bicara(nama_user):

    nama = nama_user or "Rifan"
    return (
        f"CONVERSATION-PARTNER DETECTION (IMPORTANT): Because {nama}'s microphone "
        "is always on (hands-free), voices chatting with other people in the "
        "room sometimes get recorded. Analyze the input sentence: (1) If it mentions "
        "your name ('Arvi', 'Arfi'), asks something, gives a command, vents to "
        "you, or continues the previous conversation in the chat history, then "
        "ANSWER warmly and attentively. (2) But if the sentence is CLEARLY aimed "
        "at a third person in the real world (for example calling someone else's "
        "name/family/friend in the room, asking another person to fetch a physical "
        "thing like 'please grab me a drink from the kitchen', or meaningless "
        "mumbling with zero link to the context), reply with ONLY the exact text: "
        "[ABAIKAN_OBROLAN_LAIN] and nothing else."
    )


def _buang_turn_terakhir(user_prompt):

    try:
        if (len(conversation_history) >= 2
                and conversation_history[-2].get("role") == "user"
                and conversation_history[-2].get("content") == user_prompt
                and conversation_history[-1].get("role") == "assistant"):
            del conversation_history[-2:]
            memori_ltm["interaksi"] = max(0, int(memori_ltm.get("interaksi") or 0) - 1)
            _simpan_memori()
    except Exception:
        pass


def _butuh_telemetri(teks):

    rendah = (teks or "").lower()
    return any(k in rendah for k in (
        "cpu", "ram", "memori", "memory", "proses", "process", "suhu", "temperatur",
        "temperature", "panas", "baterai", "battery", "batre", "ping", "jaringan",
        "network", "latensi", "internet", "wifi", "performa", "kinerja",
        "performance", "lemot", "lambat", "slow", "kencang", "diagnostik",
        "diagnostic", "spek", "spesifikasi", "specs", "hardware", "laptop",
        "komputer", "computer", "node"))


def _rekam_riwayat(user_prompt, response_text):

    conversation_history.append({"role": "user", "content": user_prompt})
    conversation_history.append({"role": "assistant", "content": response_text})
    del conversation_history[:-20]
    memori_ltm["interaksi"] = int(memori_ltm.get("interaksi") or 0) + 1
    _simpan_memori()
    if memori_ltm["interaksi"] % 10 == 0:
        try:
            threading.Thread(
                target=_ekstrak_fakta_latar,
                args=(list(conversation_history[-10:]),),
                daemon=True,
            ).start()
        except Exception as galat:
            print(f"[!] Background memory extraction failed: {galat}")


def _ekstrak_fakta_latar(potongan_riwayat):


    from server.ai_engine import extract_baseten_message

    if not potongan_riwayat:
        return
    transkrip = "\n".join(
        f"{'User' if m['role'] == 'user' else 'ARVI'}: {m['content'][:400]}"
        for m in potongan_riwayat)
    prompt = (
        "From the conversation below, extract up to 2 important facts about the user "
        "(name, preferences, projects, promises, important stories). Ignore small talk. "
        "Reply with ONLY JSON: {\"fakta\": [\"...\"], \"ringkasan\": \"one sentence\"}. "
        "If there are no important facts: {\"fakta\": [], \"ringkasan\": \"\"}.\n\n" + transkrip)
    mentah = ""
    try:
        if BASETEN_API_KEY:
            res = requests.post(BASETEN_URL, headers={
                "Authorization": f"Bearer {BASETEN_API_KEY}",
                "Content-Type": "application/json"}, json={
                "model": "meta-models/muse-spark-open-1026",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256}, timeout=30)
            if res.status_code == 200:
                mentah = extract_baseten_message(res.json())
        elif META_API_KEY:
            res = requests.post(META_URL, headers={
                "Authorization": f"Bearer {META_API_KEY}",
                "Content-Type": "application/json"}, json={
                "model": "muse-spark-1.3", "reasoning": {"effort": "low"},
                "input": prompt}, timeout=30)
            if res.status_code == 200:
                data = res.json()
                for item in (data.get("output", []) if isinstance(data, dict) else data):
                    if isinstance(item, dict) and item.get("type") == "message":
                        for bagian in item.get("content", []):
                            if bagian.get("type") == "output_text":
                                mentah = bagian.get("text", "")
    except Exception:
        return
    cocok = re.search(r"\{[^{}]*\"fakta\"[^{}]*\}", mentah or "", re.DOTALL)
    if not cocok:
        return
    try:
        data = json.loads(cocok.group(0))
    except ValueError:
        return
    berubah = False
    for fakta in (data.get("fakta") or [])[:2]:
        if _tambah_fakta(str(fakta)):
            berubah = True
    if data.get("ringkasan"):
        memori_ltm["ringkasan_terakhir"] = str(data["ringkasan"])[:1000]
        berubah = True
    if berubah:
        _simpan_memori()
        print(f"[+] LTM memory updated ({len(memori_ltm['fakta_penting'])} facts).")


_VARIAN_SALAH_ARVI = ("arfi", "arbi", "alfi", "arvy", "harfi", "arvie",
                          "rv", "arvee", "arpi", "arwi", "harvi")


def normalisasi_nama_arvi(teks: str) -> str:

    if not teks:
        return teks

    hasil = re.sub(r"(?i)\b(hai|halo|hei|hello|oi|tolong|coba)\s+arti\b",
                     r"\1 Arvi", teks)

    hasil = re.sub(r"(?im)(^|[.!?]\s+)(arti)(?=[,\s]|$)", r"\1Arvi", hasil)

    pola = r"(?i)(?<![\w])(?:" + "|".join(_VARIAN_SALAH_ARVI) + r")(?![\w])"
    return re.sub(pola, "Arvi", hasil)


_KATA_KERJA_NORMAL = (
    "bukakan", "dibuka", "buka", "tutupi", "ditutup", "tutup", "jalankan",
    "jalani", "matikan", "hentikan", "arahkan", "pindahkan", "geser",
    "carikan", "cari", "ketikkan", "ketik", "tuliskan", "tulis", "klik",
    "tekan", "pencet", "baca", "lihat", "tampilkan",
)


_ALIAS_AWALAN_SUARA = ("avi", "awi", "ari")


_KATA_ISI_TAK_JELAS = ("eh", "anu", "hmm", "mmm", "ehm", "heh")

PESAN_ULANGI_ARVI = ("Maaf, perintahnya belum tertangkap. "
                     "Ulangi dengan awalan Arvi.")


def _kata_pertama(rendah):
    cocok = re.search(r"[a-z]+", rendah or "")
    return cocok.group(0) if cocok else ""


def saring_transkrip_suara(transkrip, final=True):

    if not final:
        return None
    mentah = (transkrip or "").strip()
    if not mentah:
        return None
    normal = normalisasi_nama_arvi(mentah)
    if _kata_pertama(normal.lower()) == "arvi":
        sisa = re.sub(r"^[^a-zA-Z]*arvi\b", "", normal, flags=re.IGNORECASE)
    elif _kata_pertama(mentah.lower()) in _ALIAS_AWALAN_SUARA:
        sisa = re.sub(r"^[^a-zA-Z]*[a-zA-Z]+", "", mentah, count=1)
    else:
        return None
    sisa = sisa.strip().lstrip(",.:;!?-–— ").strip()
    if not re.search(r"[a-zA-Z0-9]", sisa):
        return {"tak_jelas": True}
    if sisa.lower() in _KATA_ISI_TAK_JELAS:
        return {"tak_jelas": True}
    return {"perintah": mentah, "sisa": sisa}


def _normalisasi_kata_perintah(teks):

    if not teks:
        return teks
    hasil = str(teks)
    for kata in _KATA_KERJA_NORMAL:
        pola = (r"(?i)(?<![a-z])"
                + "+".join(re.escape(h) for h in kata)
                + r"+(?![a-z])")
        hasil = re.sub(pola, kata, hasil)
    return hasil
