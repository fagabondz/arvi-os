import json
import re
from pathlib import Path

KALIBRASI_PATH = Path(__file__).resolve().parent / "arvi_kalibrasi_kursor.json"

_OFFSET_MAKS_PX = 500
_SKALA_MIN, _SKALA_MAKS = 0.8, 1.2


def kalibrasi_bawaan():

    return {"offset_x": 0, "offset_y": 0, "scale_x": 1.0, "scale_y": 1.0}


def muat_kalibrasi_kursor():

    keluar = kalibrasi_bawaan()
    try:
        data = json.loads(KALIBRASI_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return keluar
        keluar["offset_x"] = max(-_OFFSET_MAKS_PX, min(
            int(data.get("offset_x", 0)), _OFFSET_MAKS_PX))
        keluar["offset_y"] = max(-_OFFSET_MAKS_PX, min(
            int(data.get("offset_y", 0)), _OFFSET_MAKS_PX))
        keluar["scale_x"] = max(_SKALA_MIN, min(
            float(data.get("scale_x", 1.0)), _SKALA_MAKS))
        keluar["scale_y"] = max(_SKALA_MIN, min(
            float(data.get("scale_y", 1.0)), _SKALA_MAKS))
    except Exception:
        pass
    return keluar


def simpan_kalibrasi_kursor(offset_x, offset_y, scale_x=1.0, scale_y=1.0):

    try:
        data = {
            "offset_x": max(-_OFFSET_MAKS_PX, min(int(offset_x), _OFFSET_MAKS_PX)),
            "offset_y": max(-_OFFSET_MAKS_PX, min(int(offset_y), _OFFSET_MAKS_PX)),
            "scale_x": max(_SKALA_MIN, min(float(scale_x), _SKALA_MAKS)),
            "scale_y": max(_SKALA_MIN, min(float(scale_y), _SKALA_MAKS)),
        }
    except (TypeError, ValueError):
        return None
    try:
        KALIBRASI_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        return data
    except Exception as galat:
        print(f"[!] Failed to save cursor calibration: {galat}")
        return None


def reset_kalibrasi_kursor():

    return simpan_kalibrasi_kursor(0, 0, 1.0, 1.0)


def terapkan_kalibrasi_kursor(raw_x, raw_y, kalibrasi=None):

    kal = kalibrasi if isinstance(kalibrasi, dict) else muat_kalibrasi_kursor()
    try:
        sx = float(kal.get("scale_x", 1.0))
        sy = float(kal.get("scale_y", 1.0))
        ox = int(kal.get("offset_x", 0))
        oy = int(kal.get("offset_y", 0))
    except (TypeError, ValueError):
        sx, sy, ox, oy = 1.0, 1.0, 0, 0
    return (int(round(float(raw_x) * sx + ox)),
            int(round(float(raw_y) * sy + oy)))


_FRASA_OTO_ID = ("kalibrasi kursor", "kalibrasi mouse", "perbaiki akurasi klik")
_FRASA_OTO_EN = ("calibrate cursor", "calibrate mouse")
_FRASA_RESET_ID = ("reset kalibrasi kursor", "reset kalibrasi mouse")
_FRASA_RESET_EN = ("reset cursor calibration", "reset mouse calibration")

_ARAH_ID = {"kanan": (1, 0), "kiri": (-1, 0), "atas": (0, -1),
            "bawah": (0, 1)}
_ARAH_EN = {"right": (1, 0), "left": (-1, 0), "up": (0, -1),
            "down": (0, 1)}


def _frasa_utuh(rendah, frasa):
    return re.search(rf"(?<!\w){re.escape(frasa)}(?!\w)", rendah) is not None


def deteksi_intent_kalibrasi(teks: str):

    mentah = (teks or "").strip()
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "

    cocok = re.search(
        r"atur\s+offset\s+kursor\s+(-?\d+)\s+(-?\d+)", rendah)
    if cocok:
        return {"jenis": "offset_manual", "bahasa": "id", "mode_set": True,
                "dx": int(cocok.group(1)), "dy": int(cocok.group(2))}

    cocok = re.search(
        r"calibrat(?:e|ion)\s+(?:cursor|mouse)\s+offset\s+(-?\d+)\s+(-?\d+)",
        rendah)
    if cocok:
        return {"jenis": "offset_manual", "bahasa": "en", "mode_set": True,
                "dx": int(cocok.group(1)), "dy": int(cocok.group(2))}

    if ("kalibrasi" in rendah or "calibrat" in rendah) and (
            "geser" in rendah or "shift" in rendah or "nudge" in rendah):
        dx = dy = 0
        hitung = 0
        kamus = dict(_ARAH_ID)
        if "calibrat" in rendah:
            kamus.update(_ARAH_EN)
        for arah, (sx, sy) in kamus.items():
            for angka in re.findall(
                    rf"(?<!\w){re.escape(arah)}\s+(\d+)(?!\w)", rendah):
                dx += sx * int(angka)
                dy += sy * int(angka)
                hitung += 1
        if hitung:
            bahasa = "en" if ("calibrat" in rendah
                              and "kalibrasi" not in rendah) else "id"
            return {"jenis": "offset_manual", "bahasa": bahasa,
                    "mode_set": False, "dx": dx, "dy": dy}

    for frasa in _FRASA_RESET_EN:
        if _frasa_utuh(rendah, frasa):
            return {"jenis": "reset", "bahasa": "en", "mode_set": True,
                    "dx": 0, "dy": 0}
    for frasa in _FRASA_RESET_ID:
        if _frasa_utuh(rendah, frasa):
            return {"jenis": "reset", "bahasa": "id", "mode_set": True,
                    "dx": 0, "dy": 0}

    for frasa in _FRASA_OTO_EN:
        if _frasa_utuh(rendah, frasa):
            return {"jenis": "otomatis", "bahasa": "en", "mode_set": False,
                    "dx": 0, "dy": 0}
    for frasa in _FRASA_OTO_ID:
        if _frasa_utuh(rendah, frasa):
            return {"jenis": "otomatis", "bahasa": "id", "mode_set": False,
                    "dx": 0, "dy": 0}
    return None


def _inggris(bahasa):
    return str(bahasa or "id").lower().startswith("en")


def jawab_kalibrasi_selesai(bahasa, offset_x, offset_y):

    if _inggris(bahasa):
        return (f"Cursor calibration complete. Offset adjusted "
                f"(X: {int(offset_x)}, Y: {int(offset_y)}).")
    return (f"Kalibrasi kursor selesai. Offset dikoreksi "
            f"(X: {int(offset_x)}, Y: {int(offset_y)}).")


def jawab_kalibrasi_reset(bahasa):

    if _inggris(bahasa):
        return "Cursor calibration reset."
    return "Kalibrasi kursor di-reset."


def jawab_kalibrasi_offset(bahasa, offset_x, offset_y):

    if _inggris(bahasa):
        return (f"Cursor offset updated (X: {int(offset_x)}, "
                f"Y: {int(offset_y)}).")
    return (f"Offset kursor diperbarui (X: {int(offset_x)}, "
            f"Y: {int(offset_y)}).")


def jawab_kalibrasi_gagal(bahasa):

    if _inggris(bahasa):
        return "Calibration failed, try again."
    return "Kalibrasi gagal, coba lagi."


_TITIK_B_A = (0.30, 0.45)
_TITIK_B_B = (0.70, 0.60)
_JARAK_MIN_MARKER = 0.15


def _gambar_marker_kalibrasi(img, titik_xy, label):

    from PIL import ImageDraw
    gambar = ImageDraw.Draw(img)
    x, y = int(titik_xy[0]), int(titik_xy[1])
    r = max(10, min(img.width, img.height) // 28)

    gambar.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3],
                   outline=(255, 255, 255), width=3)
    gambar.ellipse([x - r, y - r, x + r, y + r],
                   outline=(255, 0, 255), width=3)
    gambar.line([x - r - 8, y, x + r + 8, y], fill=(255, 255, 255), width=2)
    gambar.line([x, y - r - 8, x, y + r + 8], fill=(255, 255, 255), width=2)
    gambar.text((x + r + 5, y - r - 5), label, fill=(255, 255, 255))
    try:
        gambar.text((x + r + 4, y - r - 6), label, fill=(255, 0, 255))
    except Exception:
        pass


def _urai_tebakan_marker(mentah):

    if not mentah:
        return None

    start = mentah.find("{")
    end = mentah.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(mentah[start:end + 1])
    except ValueError:
        return None
    try:
        hasil = {}
        for kunci in ("A", "B"):
            x = float(data[kunci]["x_persen"])
            y = float(data[kunci]["y_persen"])
            if not (0 <= x <= 100 and 0 <= y <= 100):
                return None
            hasil[kunci] = (x, y)
        return hasil
    except (KeyError, TypeError, ValueError):
        return None


_PROMPT_MARKER_KALIBRASI = (
    "Look at this computer screenshot. Two calibration targets are drawn on "
    "it: a magenta circle labeled 'A' and a magenta circle labeled 'B'. "
    "Give each target's center point as screen percentages (0 to 100) from "
    "the top-left. A faint percent grid (lines every 10 with numbers 10..90 "
    "on the top/left edges) is drawn as a precision ruler — read it. "
    "You MUST reply with ONLY exactly this JSON format and nothing else: "
    '{"A": {"x_persen": 30.0, "y_persen": 45.0}, '
    '"B": {"x_persen": 70.0, "y_persen": 60.0}}'
)


def jalankan_kalibrasi_kursor_otomatis(bahasa="id", pratinjau=None):

    try:
        from server.config import BASETEN_API_KEY
        from server.os_control import (
            _pag, _PYAUTOGUI_TERSEDIA, dapatkan_geometri_layar_virtual,
            posisi_kursor_saat_ini)
        from server.vision_engine import (
            _ambil_screenshot_b64, query_arvi_vision, tambah_grid_koordinat)
    except Exception:
        return jawab_kalibrasi_gagal(bahasa)
    if not BASETEN_API_KEY:
        return jawab_kalibrasi_gagal(bahasa)
    try:
        from PIL import Image
        import base64 as _b64
        import io as _io
    except Exception:
        return jawab_kalibrasi_gagal(bahasa)

    shot, info = _ambil_screenshot_b64()
    if shot is None:
        return jawab_kalibrasi_gagal(bahasa)
    ox, oy, vw, vh = dapatkan_geometri_layar_virtual()
    try:
        mentah_b64 = shot.split(",", 1)[1] if "," in shot else shot
        img = Image.open(_io.BytesIO(_b64.b64decode(mentah_b64))).convert("RGB")
    except Exception:
        return jawab_kalibrasi_gagal(bahasa)
    lebar_shot, tinggi_shot = img.size
    if lebar_shot <= 0 or tinggi_shot <= 0:
        return jawab_kalibrasi_gagal(bahasa)


    pos = posisi_kursor_saat_ini()
    if pos is not None and vw > 0 and vh > 0:
        titik_a = ((pos[0] - ox) / vw * lebar_shot,
                   (pos[1] - oy) / vh * tinggi_shot)
    else:
        titik_a = (_TITIK_B_A[0] * lebar_shot, _TITIK_B_A[1] * tinggi_shot)

    titik_b = (0.5 * lebar_shot, 0.5 * tinggi_shot)
    if abs(titik_b[0] - titik_a[0]) / max(1, lebar_shot) < _JARAK_MIN_MARKER:
        titik_b = (_TITIK_B_B[0] * lebar_shot, _TITIK_B_B[1] * tinggi_shot)
    for titik in (titik_a, titik_b):
        if not (0 <= titik[0] < lebar_shot and 0 <= titik[1] < tinggi_shot):
            return jawab_kalibrasi_gagal(bahasa)

    _gambar_marker_kalibrasi(img, titik_a, "A")
    _gambar_marker_kalibrasi(img, titik_b, "B")
    try:
        buf = _io.BytesIO()
        img.save(buf, "JPEG", quality=80)
        bertanda = ("data:image/jpeg;base64," +
                    _b64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        return jawab_kalibrasi_gagal(bahasa)
    if pratinjau is not None:
        pratinjau.update({"image": bertanda, "target": "titik kalibrasi",
                          "sumber": "kalibrasi"})

    kirim = tambah_grid_koordinat(bertanda)
    tebakan = _urai_tebakan_marker(query_arvi_vision(kirim, _PROMPT_MARKER_KALIBRASI))
    if tebakan is None:
        return jawab_kalibrasi_gagal(bahasa)


    exp_a = (ox + titik_a[0] / lebar_shot * vw,
             oy + titik_a[1] / tinggi_shot * vh)
    exp_b = (ox + titik_b[0] / lebar_shot * vw,
             oy + titik_b[1] / tinggi_shot * vh)
    gue_a = (ox + tebakan["A"][0] / 100.0 * vw,
             oy + tebakan["A"][1] / 100.0 * vh)
    gue_b = (ox + tebakan["B"][0] / 100.0 * vw,
             oy + tebakan["B"][1] / 100.0 * vh)

    def _cocok_linear(e1, e2, g1, g2):
        denom = g2 - g1
        if abs(denom) < 1.0:
            return 1.0, (e1 - g1 + e2 - g2) / 2.0
        skala = (e2 - e1) / denom
        return skala, e1 - g1 * skala

    sk_x, of_x = _cocok_linear(exp_a[0], exp_b[0], gue_a[0], gue_b[0])
    sk_y, of_y = _cocok_linear(exp_a[1], exp_b[1], gue_a[1], gue_b[1])
    tersimpan = simpan_kalibrasi_kursor(round(of_x), round(of_y), sk_x, sk_y)
    if tersimpan is None:
        return jawab_kalibrasi_gagal(bahasa)


    try:
        if _PYAUTOGUI_TERSEDIA and _pag is not None:
            _pag.moveTo(int(ox + vw / 2), int(oy + vh / 2), duration=0.4)
    except Exception:
        pass
    return jawab_kalibrasi_selesai(bahasa, tersimpan["offset_x"],
                                   tersimpan["offset_y"])
