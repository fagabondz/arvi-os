import asyncio
import json
import re
import time
from collections import deque
from datetime import datetime, timedelta

from server.config import (_siar_ke_hud, hud_clients, node_clients,
                           system_context)
from server.memory import _rekam_riwayat, _simpan_memori, memori_ltm

_cpu_riwayat = deque(maxlen=240)
_peringatan_cpu_terakhir = 0.0
_TUGAS_PROAKTIF = None

_CPU_AMBANG_PERSEN = 80.0
_CPU_AMBANG_MENIT = 10
_CPU_COOLDOWN_JAM = 1

_NAMA_HARI = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
              "Saturday", "Sunday"]
_NAMA_BULAN = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November",
               "December"]


def _catat_cpu_telemetri(payload):

    try:
        cocok = re.search(r"CPU:\s*([\d.]+)", str(payload or ""))
        if cocok:
            _cpu_riwayat.append((time.time(), float(cocok.group(1))))
    except (TypeError, ValueError):
        pass


def _cpu_tinggi_berkepanjangan(kini=None):

    kini = kini if kini is not None else time.time()
    jendela = _CPU_AMBANG_MENIT * 60
    sampel = [(t, p) for (t, p) in _cpu_riwayat if 0 <= kini - t <= jendela]
    if len(sampel) < 5:
        return False

    if sampel[0][0] > kini - jendela + 120:
        return False
    return all(p > _CPU_AMBANG_PERSEN for (_, p) in sampel)


def _urai_waktu_pengingat(teks, kini=None):

    rendah = f" {(teks or '').lower()} "
    kini = kini if kini is not None else datetime.now()
    cocok = re.search(r"(?<!\w)dalam\s+(\d+)\s*(detik|menit|jam)(?!\w)",
                      rendah)
    if cocok:
        jumlah, satuan = int(cocok.group(1)), cocok.group(2)
        if satuan == "detik":
            delta = timedelta(seconds=jumlah)
        elif satuan == "menit":
            delta = timedelta(minutes=jumlah)
        else:
            delta = timedelta(hours=jumlah)
        return (kini + delta).timestamp()
    cocok = re.search(r"(?<!\w)in\s+(\d+)\s*(seconds?|minutes?|hours?)(?!\w)",
                      rendah)
    if cocok:
        jumlah, satuan = int(cocok.group(1)), cocok.group(2)
        if satuan.startswith("second"):
            delta = timedelta(seconds=jumlah)
        elif satuan.startswith("minute"):
            delta = timedelta(minutes=jumlah)
        else:
            delta = timedelta(hours=jumlah)
        return (kini + delta).timestamp()
    cocok = re.search(r"(?<!\w)jam\s+(\d{1,2})(?:[:.](\d{2}))?\s*"
                      r"(pagi|siang|sore|malam)?(?!\w)", rendah)
    if cocok:
        jam = int(cocok.group(1))
        menit = int(cocok.group(2) or 0)
        periode = cocok.group(3) or ""
        if menit > 59:
            return None
        if periode in ("siang", "sore", "malam"):
            if jam == 12:
                jam = 0 if periode == "malam" else 12
            elif jam < 12:
                jam += 12
        elif periode == "pagi" and jam == 12:
            jam = 0
        if jam > 23:
            return None
        target = kini.replace(hour=jam, minute=menit, second=0,
                              microsecond=0)
        if target <= kini:
            target += timedelta(days=1)
        return target.timestamp()
    cocok = re.search(r"(?<!\w)at\s+(\d{1,2})(?:[:.](\d{2}))?\s*"
                      r"(am|pm)?(?!\w)", rendah)
    if cocok:
        jam = int(cocok.group(1))
        menit = int(cocok.group(2) or 0)
        periode = cocok.group(3) or ""
        if menit > 59:
            return None
        if periode == "pm" and jam < 12:
            jam += 12
        elif periode == "pm" and jam == 12:
            jam = 12
        elif periode == "am" and jam == 12:
            jam = 0
        if jam > 23:
            return None
        target = kini.replace(hour=jam, minute=menit, second=0,
                              microsecond=0)
        if target <= kini:
            target += timedelta(days=1)
        return target.timestamp()
    return None


def atur_pengingat(teks, kini=None):

    mentah = (teks or "").strip()
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if not re.search(r"(?<!\w)(ingatkan|ingetin|ingetkan|remind)(?!\w)",
                     rendah):
        return None
    target = _urai_waktu_pengingat(mentah, kini=kini)
    if target is None:
        return ("[REMINDER] When? Example: 'remind me to drink in "
                "30 minutes' or 'remind me about the meeting at 9 am'.")
    pesan = re.sub(r"(?i)\b(tolong\s+|please\s+)?(ingatkan|ingetin|ingetkan|remind)"
                   r"\s+(aku|saya|gue|gua|me|us|myself)?\s*", "", mentah).strip()
    pesan = re.sub(r"(?i)\s*dalam\s+\d+\s*(detik|menit|jam)\s*", " ",
                   pesan).strip()
    pesan = re.sub(r"(?i)\s*in\s+\d+\s*(seconds?|minutes?|hours?)\s*", " ",
                   pesan).strip()
    pesan = re.sub(r"(?i)\s*jam\s+\d{1,2}(?:[:.]\d{2})?\s*"
                   r"(pagi|siang|sore|malam)?\s*", " ", pesan).strip()
    pesan = re.sub(r"(?i)\s*at\s+\d{1,2}(?:[:.]\d{2})?\s*"
                   r"(am|pm)?\s*", " ", pesan).strip()
    pesan = re.sub(r"\s+", " ", pesan).strip(" .,:")
    if not pesan:
        pesan = "ARVI reminder"
    memori_ltm.setdefault("pengingat", []).append(
        {"teks": pesan[:200], "waktu": target, "dibuat": time.time()})
    memori_ltm["pengingat"] = memori_ltm["pengingat"][-50:]
    _simpan_memori()
    kapan = datetime.fromtimestamp(target).strftime("%d %b %H:%M")
    return f"[REMINDER] Done, I'll remind you '{pesan}' at {kapan}."


def daftar_pengingat():

    kini = time.time()
    aktif = [p for p in memori_ltm.get("pengingat", [])
             if p.get("waktu", 0) > kini]
    if not aktif:
        return "[REMINDER] No active reminders."
    baris = []
    for i, p in enumerate(sorted(aktif, key=lambda x: x["waktu"]), 1):
        kapan = datetime.fromtimestamp(p["waktu"]).strftime("%d %b %H:%M")
        baris.append(f"{i}. '{p.get('teks', '?')}' → {kapan}")
    return "[REMINDER] Active:\n" + "\n".join(baris)


def hapus_pengingat(teks):

    rendah = f" {(teks or '').lower()} "
    if "pengingat" not in rendah and "reminder" not in rendah:
        return None
    if not re.search(r"(?<!\w)(hapus|hapuskan|batal|batalkan|delete|cancel|remove|clear)(?!\w)",
                     rendah):
        return None
    daftar = memori_ltm.get("pengingat", [])
    if re.search(r"(?<!\w)(semua|all)(?!\w)", rendah):
        jumlah = len(daftar)
        memori_ltm["pengingat"] = []
        _simpan_memori()
        return f"[REMINDER] Deleted all {jumlah} reminders."
    cocok = re.search(r"(\d+)", rendah)
    if not cocok:
        return ("[REMINDER] Say the number ('delete reminder 2') or "
                "'delete all reminders'.")
    nomor = int(cocok.group(1))
    aktif = sorted([p for p in daftar if p.get("waktu", 0) > time.time()],
                   key=lambda x: x["waktu"])
    if not 1 <= nomor <= len(aktif):
        return (f"[REMINDER] No such number ({len(aktif)} active). "
                "Check 'show reminders'.")
    target = aktif[nomor - 1]
    memori_ltm["pengingat"] = [p for p in daftar if p is not target]
    _simpan_memori()
    return f"[REMINDER] Deleted: '{target.get('teks', '?')}'."


def deteksi_perintah_pengingat(teks):

    mentah = (teks or "").strip()
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if ("pengingat" not in rendah and "reminder" not in rendah
            and not re.search(r"(?<!\w)(ingatkan|ingetin|ingetkan|remind)"
                              r"(?!\w)", rendah)):
        return None
    hasil_hapus = hapus_pengingat(mentah)
    if hasil_hapus is not None:
        return hasil_hapus
    if re.search(r"(?<!\w)(ingatkan|ingetin|ingetkan|remind)(?!\w)",
                 rendah):
        return atur_pengingat(mentah)
    return daftar_pengingat()


def _susun_briefing(kini=None):

    kini = kini if kini is not None else datetime.now()
    nama_user = (memori_ltm.get("profil_user") or {}).get("nama") or "friend"
    tanggal = (f"{_NAMA_HARI[kini.weekday()]}, {kini.day} "
               f"{_NAMA_BULAN[kini.month]} {kini.year}")
    tele = system_context.get("latest_telemetry", "-")
    proses = (system_context.get("top_processes", "") or "").splitlines()
    tiga = "; ".join(p.strip()[:60] for p in proses[:3] if p.strip()) or "-"
    ingat_aktif = [p for p in memori_ltm.get("pengingat", [])
                   if p.get("waktu", 0) > time.time()]
    if ingat_aktif:
        daftar = "; ".join(
            f"'{p.get('teks', '?')}' "
            f"{datetime.fromtimestamp(p['waktu']).strftime('%H:%M')}"
            for p in sorted(ingat_aktif, key=lambda x: x["waktu"])[:5])
    else:
        daftar = "none"
    return (
        f"☀ Good morning, {nama_user}! This is the ARVI briefing — {tanggal}.\n"
        f"• Laptop node: {'connected' if node_clients else 'not connected'} "
        f"({tele}).\n"
        f"• Top processes: {tiga}.\n"
        f"• Today's reminders: {daftar}.\n"
        f"• Facts I remember about you: "
        f"{len(memori_ltm.get('fakta_penting', []))}."
    )


def deteksi_perintah_briefing(teks):

    mentah = (teks or "").strip()
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if "briefing" not in rendah:
        return None
    brif = memori_ltm.setdefault("briefing", {"aktif": False, "jam": 7,
                                              "terakhir": ""})
    if re.search(r"(?<!\w)(matikan|nonaktif|non-aktif|stop|berhenti|turn off|disable|deactivate)(?!\w)",
                 rendah):
        brif["aktif"] = False
        _simpan_memori()
        return "[BRIEFING] Morning briefing off."
    cocok_jam = re.search(r"(?<!\w)(?:jam|at)\s+(\d{1,2})(?!\w)", rendah)
    if (re.search(r"(?<!\w)(aktifkan|nyalakan|aktif|setel|atur|setiap|turn on|enable|activate|set|every|daily)(?!\w)",
                  rendah) or cocok_jam):
        jam = 7
        if cocok_jam:
            try:
                jam = max(0, min(int(cocok_jam.group(1)), 23))
            except ValueError:
                jam = 7
        brif["aktif"] = True
        brif["jam"] = jam
        brif["terakhir"] = ""
        _simpan_memori()
        return f"[BRIEFING] Morning briefing on, every day at {jam:02d}:00."
    return _susun_briefing()


async def _loop_proaktif():

    global _peringatan_cpu_terakhir
    while True:
        try:
            await asyncio.sleep(30)
            kini = time.time()
            if not hud_clients:
                continue
            loop = asyncio.get_event_loop()

            jatuh = [p for p in memori_ltm.get("pengingat", [])
                     if p.get("waktu", 0) <= kini]
            if jatuh:
                memori_ltm["pengingat"] = [
                    p for p in memori_ltm.get("pengingat", [])
                    if p.get("waktu", 0) > kini]
                _simpan_memori()
                for p in sorted(jatuh, key=lambda x: x["waktu"]):
                    teks = f"⏰ Reminder: {p.get('teks', '')}"
                    await loop.run_in_executor(
                        None, _rekam_riwayat,
                        f"[SYSTEM: due reminder] {p.get('teks', '')}",
                        teks)
                    await _siar_ke_hud({"type": "arvi_response", "text": teks,
                                        "engine": "ARVI PROACTIVE"})

            brif = memori_ltm.get("briefing") or {}
            if brif.get("aktif"):
                sekarang = datetime.now()
                if (brif.get("terakhir") != sekarang.strftime("%Y-%m-%d")
                        and sekarang.hour >= int(brif.get("jam", 7) or 7)):
                    brif["terakhir"] = sekarang.strftime("%Y-%m-%d")
                    _simpan_memori()
                    teks = _susun_briefing(sekarang)
                    await loop.run_in_executor(
                        None, _rekam_riwayat, "[SYSTEM: morning briefing]",
                        teks)
                    await _siar_ke_hud({"type": "arvi_response", "text": teks,
                                        "engine": "ARVI PROACTIVE"})

            if (_cpu_tinggi_berkepanjangan(kini)
                    and kini - _peringatan_cpu_terakhir
                    > _CPU_COOLDOWN_JAM * 3600):
                _peringatan_cpu_terakhir = kini
                for node_ws in list(node_clients):
                    try:
                        await node_ws.send_text(
                            json.dumps({"action": "INSPECT_CPU"}))
                    except Exception:
                        continue
                teks = ("⚠ Laptop CPU has been high (>80%) for the last 10 minutes. "
                        "Want me to kill the heaviest process? Name the app "
                        "(e.g. 'close chrome') — or ignore this if you are "
                        "rendering/compiling.")
                await loop.run_in_executor(
                    None, _rekam_riwayat, "[SYSTEM: high CPU]", teks)
                await _siar_ke_hud({"type": "arvi_response", "text": teks,
                                    "engine": "ARVI PROACTIVE"})
        except Exception as galat:
            print(f"[!] Proactive loop: {galat}")
