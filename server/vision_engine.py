import base64
import io
import json
import re
import time

import requests

from server.ai_engine import extract_baseten_message
from server.config import (BASETEN_API_KEY, BASETEN_URL, META_API_KEY,
                           ImageGrab)
from server.memory import (_normalisasi_kata_perintah,
                           conversation_history, last_vision_frame)
from server.kalibrasi_kursor import muat_kalibrasi_kursor
from server.os_control import (_MODIFIER_AMAN, _TOMBOL_AMAN,
                               _normalisasi_tombol, _PESAN_INSTALL_PAG, _pag,
                               _PYAUTOGUI_TERSEDIA, dapatkan_origin_layar_virtual,
                               deteksi_intent_os)


def query_arvi_vision(image_base64: str, prompt: str = "Identify the object, hardware, or activity in front of this camera, technically and briefly.", prompt_sistem: str = "") -> str:

    if not BASETEN_API_KEY:
        return "[VISION ERROR] BASETEN_API_KEY is required in .env for Muse Spark Open visual analysis."

    headers = {
        "Authorization": f"Bearer {BASETEN_API_KEY}",
        "Content-Type": "application/json"
    }

    if not image_base64.startswith("data:image"):
        image_url = f"data:image/jpeg;base64,{image_base64}"
    else:
        image_url = image_base64

    sistem = prompt_sistem or (
        "You are ARVI's eyes. Answer the user's question about this image "
        "VERY BRIEFLY, straight to the point (1-2 sentences). Match the "
        "language of the user's question (default English for generic prompts). "
        "If the user asks 'who is this', answer the name/category. "
        "If they ask 'how old' and it shows a human/animal, guess "
        "the age or answer logically. Do NOT write a long "
        "description or technical paragraph unless the user explicitly "
        "asks for one."
    )

    payload = {
        "model": "meta-models/muse-spark-open-1026",
        "messages": [
            {
                "role": "system",
                "content": sistem
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": 2048
    }

    try:
        res = requests.post(BASETEN_URL, headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            data = res.json()
            result_text = extract_baseten_message(data)
            print(f"[+] Vision Response: {result_text[:120]}...")
            return result_text
        else:
            print(f"[!] Vision API Error {res.status_code}: {res.text}")
            if res.status_code in (401, 403):
                return (f"[VISION API ERROR {res.status_code}] Baseten API key "
                        "rejected — check BASETEN_API_KEY in .env. "
                        "(Your ARVI login is valid.)")
            return f"[VISION API ERROR {res.status_code}] {res.text}"
    except Exception as e:
        return f"[VISION EXCEPTION] {str(e)}"


def _pil_dari_b64(image_b64, lebar_maks=640):

    mentah = (image_b64 or "").strip()
    if "," in mentah:
        mentah = mentah.split(",", 1)[1]
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(base64.b64decode(mentah))).convert("RGB")
    except Exception:
        return None
    if img.width > lebar_maks:
        skala = lebar_maks / img.width
        img = img.resize((lebar_maks, max(1, int(img.height * skala))))
    return img


def _bbox_dari_baseten(image_b64):

    if not BASETEN_API_KEY:
        return None
    tanya = ("Look at this image. Reply with ONLY exactly this JSON: "
             '{"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0} '
             "holding the main object's bounding box (0-1 coordinates from the top-left).")
    try:
        jawab = query_arvi_vision(image_b64, tanya)
        cocok = re.search(r"\{[^{}]*\"x1\"[^{}]*\}", jawab or "", re.DOTALL)
        if not cocok:
            return None
        data = json.loads(cocok.group(0))
        bbox = [float(data["x1"]), float(data["y1"]),
                float(data["x2"]), float(data["y2"])]
        if not all(0.0 <= v <= 1.0 for v in bbox):
            return None
        if not (bbox[2] > bbox[0] and bbox[3] > bbox[1]):
            return None
        return bbox
    except (ValueError, KeyError, TypeError):
        return None


def jalankan_segmentasi_meta(image_b64):

    kosong = {"sam_aktif": False, "annotated_image": "", "polygons": [],
              "bbox": [0.0, 0.0, 0.0, 0.0], "vertices_count": 0,
              "mask_count": 0, "confidence": 0.0, "model": ""}
    img = _pil_dari_b64(image_b64)
    if img is None:
        return kosong

    if META_API_KEY:
        try:
            from server import sam31_cloud
            hasil_cloud = sam31_cloud.segmentasi_sam31(
                image_b64, META_API_KEY, konsep="object")
            if hasil_cloud.get("sam_aktif"):
                return hasil_cloud
        except Exception as galat:
            print(f"[!] SAM 3.1 cloud failed, Baseten-BBox fallback: {galat}")

    bbox = _bbox_dari_baseten(image_b64)
    if bbox:
        kosong["bbox"] = [round(v, 4) for v in bbox]
        kosong["model"] = "Baseten-BBox"
    return kosong


def _ambil_screenshot_b64(lebar_maks=1280):

    try:
        if ImageGrab is not None:
            try:
                img = ImageGrab.grab(all_screens=True)
            except TypeError:
                img = ImageGrab.grab()
        elif _PYAUTOGUI_TERSEDIA and _pag is not None:
            img = _pag.screenshot()
        else:
            return None, ("[SCREEN ERROR] Failed to capture the screen: PIL.ImageGrab "
                          "and pyautogui are unavailable.")
    except Exception as galat:
        return None, f"[SCREEN ERROR] Failed to capture the screen: {galat}"
    try:
        asli = img.size
        if img.width > lebar_maks:
            skala = lebar_maks / img.width
            img = img.resize((lebar_maks, max(1, int(img.height * skala))))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=70)
        mentah = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{mentah}", asli
    except Exception as galat:
        return None, f"[SCREEN ERROR] Failed to compress the screenshot: {galat}"


def _koordinat_dari_vision(teks_vision):

    if not teks_vision:
        return None
    cocok = re.search(r"\{[^{}]*\"ditemukan\"[^{}]*\}", teks_vision, re.DOTALL)
    if not cocok:
        return None
    try:
        data = json.loads(cocok.group(0))
    except ValueError:
        return None
    if not data.get("ditemukan"):
        return {"ditemukan": False}
    try:
        x = float(data["x_persen"])
        y = float(data["y_persen"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0 <= x <= 100 and 0 <= y <= 100):
        return None
    return {"ditemukan": True, "x_persen": x, "y_persen": y}


def konversi_persen_ke_piksel(x_persen, y_persen, lebar_virtual, tinggi_virtual,
                              origin_x=0, origin_y=0, kalibrasi=None):

    from server.kalibrasi_kursor import terapkan_kalibrasi_kursor
    try:
        xp, yp = float(x_persen), float(y_persen)
        vw, vh = int(lebar_virtual), int(tinggi_virtual)
        ox, oy = int(origin_x), int(origin_y)
    except (TypeError, ValueError):
        return (int(origin_x), int(origin_y))
    if vw <= 0 or vh <= 0:
        return (ox, oy)
    raw_x = ox + (xp / 100.0) * vw
    raw_y = oy + (yp / 100.0) * vh
    if kalibrasi is None:
        kalibrasi = muat_kalibrasi_kursor()
    final_x, final_y = terapkan_kalibrasi_kursor(raw_x, raw_y, kalibrasi)
    final_x = max(ox, min(final_x, ox + vw - 1))
    final_y = max(oy, min(final_y, oy + vh - 1))
    return (final_x, final_y)


def tambah_grid_koordinat(image_b64, langkah_persen=10):

    try:
        from PIL import Image, ImageDraw
    except Exception:
        return image_b64 or ""
    try:
        mentah = (image_b64 or "").strip()
        if "," in mentah:
            mentah = mentah.split(",", 1)[1]
        dasar = Image.open(io.BytesIO(base64.b64decode(mentah))).convert("RGB")
    except Exception:
        return image_b64 or ""
    try:
        w, h = dasar.size
        layar = max(1, min(int(langkah_persen), 50))
        lapis = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gambar = ImageDraw.Draw(lapis)
        garis = (0, 240, 255, 80)
        teks = (255, 255, 255, 200)
        for persen in range(layar, 100, layar):
            x = int(persen / 100.0 * w)
            y = int(persen / 100.0 * h)
            gambar.line([(x, 0), (x, h)], fill=garis, width=1)
            gambar.line([(0, y), (w, y)], fill=garis, width=1)
            gambar.text((x + 3, 3), str(persen), fill=teks)
            gambar.text((3, y + 3), str(persen), fill=teks)
        gabung = Image.alpha_composite(dasar.convert("RGBA"), lapis)
        buf = io.BytesIO()
        gabung.convert("RGB").save(buf, "JPEG", quality=80)
        return ("data:image/jpeg;base64," +
                base64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        return image_b64 or ""


def lihat_dan_klik_layar(target_objek: str, pratinjau=None) -> str:

    target = (target_objek or "").strip()
    if not target:
        return "[SCREEN VISION] Empty target — say what should be clicked."
    if not _PYAUTOGUI_TERSEDIA or _pag is None:
        return _PESAN_INSTALL_PAG
    if not BASETEN_API_KEY:
        return "[SCREEN ERROR] BASETEN_API_KEY is required to read the screen."
    shot, info = _ambil_screenshot_b64()
    if shot is None:
        return info
    lebar_layar, tinggi_layar = info


    origin_x, origin_y = dapatkan_origin_layar_virtual()
    prompt_koordinat = (
        f"Look at this computer screenshot. Find the text, button, or profile named '{target}'. "
        "PENTING: Abaikan elemen UI dari aplikasi asisten 'ARVI' (seperti tombol Mic, HUD, atau terminal). "
        "Fokus cari teks/tombol pada aplikasi target di belakangnya. "
        "A faint percent grid (lines every 10 with numbers 10..90 on the "
        "top/left edges) is drawn on this screenshot — read those grid "
        "lines/numbers as a precision ruler for the center point. "
        "Give that element's center point as screen percentages (0 to 100) from the top-left. "
        "You MUST reply with ONLY exactly this JSON format and nothing else: "
        '{"ditemukan": true, "x_persen": 40.5, "y_persen": 52.0} '
        'If it is not on screen, reply: {"ditemukan": false, "x_persen": -1, "y_persen": -1}'
    )


    hasil_mentah = query_arvi_vision(tambah_grid_koordinat(shot),
                                     prompt_koordinat)
    data_lokasi = _koordinat_dari_vision(hasil_mentah)
    if data_lokasi is None:
        return (f"[SCREEN VISION] Failed to map coordinates for '{target}'. "
                f"AI response: {hasil_mentah[:200]}")
    if not data_lokasi["ditemukan"]:
        return f"[SCREEN VISION] I looked at the screen but could not find '{target}'."
    x_asli, y_asli = konversi_persen_ke_piksel(
        data_lokasi["x_persen"], data_lokasi["y_persen"],
        lebar_layar, tinggi_layar, origin_x, origin_y)
    try:
        _pag.moveTo(x_asli, y_asli, duration=0.5)
        _pag.click()
    except _pag.FailSafeException:
        return "[SCREEN VISION] FAILSAFE tripped — the click was cancelled by the operator."
    except Exception as galat:
        return f"[SCREEN ERROR] Failed to click: {galat}"
    if pratinjau is not None:
        try:
            from PIL import Image, ImageDraw
            mentah_b64 = shot.split(",", 1)[1] if "," in shot else shot
            img = Image.open(
                io.BytesIO(base64.b64decode(mentah_b64))).convert("RGB")

            px = int(data_lokasi["x_persen"] / 100.0 * img.width)
            py = int(data_lokasi["y_persen"] / 100.0 * img.height)
            gambar = ImageDraw.Draw(img)
            r, warna = 26, (255, 45, 85)
            gambar.ellipse([px - r, py - r, px + r, py + r], outline=warna, width=4)
            gambar.line([px - r - 14, py, px + r + 14, py], fill=warna, width=3)
            gambar.line([px, py - r - 14, px, py + r + 14], fill=warna, width=3)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=70)
            pratinjau.update({
                "image": "data:image/jpeg;base64," + base64.b64encode(
                    buf.getvalue()).decode("ascii"),
                "target": target, "x": x_asli, "y": y_asli,
                "sumber": "klik"})
        except Exception:
            pass
    return (f"[SCREEN VISION] Found '{target}' on screen ({x_asli}, {y_asli}) "
            "and clicked it.")


def baca_layar_monitor(pertanyaan="Briefly describe what is on this monitor screen.",
                       pratinjau=None):

    if not BASETEN_API_KEY:
        return "[SCREEN ERROR] BASETEN_API_KEY is required to read the screen."
    shot, info = _ambil_screenshot_b64()
    if shot is None:
        return info
    if pratinjau is not None:
        pratinjau.update({"image": shot, "target": "layar monitor",
                          "sumber": "layar"})
    tanya = (pertanyaan or "").strip() or "Briefly describe what is on this monitor screen."
    return query_arvi_vision(
        shot, f"Answer in the same language as the question (default English), VERY BRIEFLY "
        f"and to-the-point (1-2 sentences, straight to the answer). "
        f"This is a screenshot of my monitor. "
        f"Question: {tanya}")


_PENGISI_TARGET_LAYAR = ("di layar", "pada layar", "di monitor", "pada monitor",
                         "di layarku", "tombol", "ikon", "icon", "menu",
                         "akun", "profil", "profile", "user", "pengguna",
                         "on screen", "on the screen", "on my screen",
                         "on the monitor", "button", "account")


def _bersihkan_target_layar(kandidat):

    bersih = (kandidat or "").strip().strip("\"'").strip()
    for _ in range(3):
        kecil = bersih.lower()
        sebelum = bersih
        for isi in _PENGISI_TARGET_LAYAR:
            if kecil.startswith(isi + " "):
                bersih = bersih[len(isi):].strip()
                kecil = bersih.lower()
            if kecil.endswith(" " + isi):
                bersih = bersih[:-(len(isi))].strip()
                kecil = bersih.lower()
        if bersih == sebelum:
            break
    bersih = re.sub(r"\s+", " ", bersih).strip().strip(".,!?\"'")
    return bersih or None


def deteksi_intent_layar(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "

    if (re.search(r"(?<!\w)(lihat|baca|tampilkan|jelaskan|analisis|cek|periksa|look|read|show|describe|explain|analyze|check)(?!\w)", rendah)
            and re.search(r"(?<!\w)(layar|layarku|monitor|monitorku|desktop|tampilan|screen|display)(?!\w)", rendah)
            and not re.search(r"(?<!\w)(kamera|camera|objek|object|lihat ini|look at this|foto|photo|scan objek|scan object)(?!\w)", rendah)):
        return {"jenis": "baca", "pertanyaan": mentah}

    target = None
    cocok = re.search(r"(?<!\w)(pilih|klik|tekan|pencet|select|click|press)\s+(.+)", rendah)
    if cocok:
        kandidat = cocok.group(2).strip()

        if not re.match(r"^(kanan|kiri|tengah|dua kali|ganda|right|left|middle|double)(\s+|$)", kandidat):
            target = _bersihkan_target_layar(kandidat)
    if target is None:
        cocok = re.search(r"(?<!\w)(akun|profil|profile|user|pengguna|account)\s+([a-z0-9_.\- ]+)", rendah)
        if cocok:
            target = _bersihkan_target_layar(cocok.group(2))
    if not target:
        return None

    if _normalisasi_tombol(target) in _TOMBOL_AMAN | _MODIFIER_AMAN:
        return None

    if re.search(r"(kamera|camera)", target.lower()):
        return None

    intent_app = deteksi_intent_os(mentah)
    if intent_app is not None and intent_app["aksi"] == "buka":
        return {"jenis": "buka_dan_klik", "app": intent_app["target"], "target": target}
    return {"jenis": "klik", "target": target}


_KATA_VISUAL_LANGSUNG = (
    "umur", "umurnya", "warna", "warnanya", "tulisan", "teks", "terbaca",
    "terlihat", "memegang", "pegang", "memakai", "pakai baju", "latar",
    "background", "ukurannya", "bentuknya", "bahannya",
    "age", "color", "colour", "text", "written", "visible",
    "holding", "wearing", "size", "shape", "material",
)
_KATA_GANTI_VISUAL = ("dia", "mereka", "itu", "ini", "tersebut", "orangnya",
                      "bendanya", "hewan", "foto", "gambar",
                      "he", "she", "they", "it", "this", "that",
                      "the person", "the animal", "photo", "picture", "image")


_FRASA_RUJUKAN_VISUAL = (
    "gambar ini", "gambar itu", "gambar tersebut", "gambarnya",
    "foto ini", "foto itu", "foto tersebut", "fotonya",
    "orang di layar", "orangnya", "objek ini", "objek itu",
    "objek tersebut", "benda ini", "benda itu", "benda tersebut",
    "bendanya", "hewan ini", "hewan itu", "di foto", "di gambar",
    "pada foto", "pada gambar", "layar ini",
    "this image", "that image", "the image", "this photo",
    "that photo", "the photo", "this picture", "that picture",
    "the picture", "the person", "on screen", "on the screen",
    "in the image", "in the photo", "in the picture",
)
_KATA_TANYA = ("apa", "siapa", "berapa", "bagaimana", "gimana", "kenapa",
               "mengapa", "di mana", "dimana", "kapan",
               "what", "who", "how", "why", "when", "where", "which", "whose")


def deteksi_tanya_visual_lanjutan(teks: str, pakai_ganti=True):

    if not last_vision_frame.get("image"):
        return False
    if time.time() - (last_vision_frame.get("timestamp") or 0) >= 25:
        return False
    rendah = f" {(teks or '').lower()} "
    for kata in _KATA_VISUAL_LANGSUNG:
        if re.search(rf"(?<!\w){re.escape(kata)}(?!\w)", rendah):
            return True
    if not pakai_ganti:
        return False
    ada_rujukan = any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", rendah)
                      for k in _FRASA_RUJUKAN_VISUAL)
    ada_tanya = any(k in rendah for k in _KATA_TANYA)
    return bool(ada_rujukan and ada_tanya)


def _konteks_visual_terakhir():

    for pesan in reversed(conversation_history):
        if pesan.get("role") == "assistant":
            return str(pesan.get("content", ""))[:800]
    return ""


_PEMICU_FORENSIK_ID = ("cek foto", "cek gambar", "periksa foto",
                       "periksa gambar", "buatan ai", "ai atau asli",
                       "asli atau ai", "forensik")
_PEMICU_FORENSIK_EN = ("is this image ai", "is this ai", "ai or real",
                       "real or ai", "forensic", "ai-generated",
                       "ai generated", "check this photo",
                       "check this image")


def _mengandung_frasa(rendah, daftar_frasa):

    for frasa in daftar_frasa:
        if re.search(rf"(?<!\w){re.escape(frasa)}(?!\w)", rendah):
            return True
    return False


def deteksi_intent_forensik(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if _mengandung_frasa(rendah, _PEMICU_FORENSIK_EN):
        return "en"
    if _mengandung_frasa(rendah, _PEMICU_FORENSIK_ID):
        return "id"
    return None


_TANYA_BBOX_FOTO = (
    "Find the main photo, illustration, or picture currently displayed "
    "on this screen (ignore OS/app UI elements). Return ONLY a JSON with "
    "its bounding box coordinates (x1, y1, x2, y2) normalized between "
    "0.0 and 1.0. If no photo is found, return empty."
)


def _bbox_foto_dari_baseten(shot_b64):

    if not BASETEN_API_KEY:
        return None
    try:
        jawab = query_arvi_vision(shot_b64, _TANYA_BBOX_FOTO)
        cocok = re.search(r"\{[^{}]*\"x1\"[^{}]*\}", jawab or "", re.DOTALL)
        if not cocok:
            return None
        data = json.loads(cocok.group(0))
        bbox = [float(data["x1"]), float(data["y1"]),
                float(data["x2"]), float(data["y2"])]
        if not all(0.0 <= v <= 1.0 for v in bbox):
            return None
        if not (bbox[2] > bbox[0] and bbox[3] > bbox[1]):
            return None
        return bbox
    except (ValueError, KeyError, TypeError):
        return None


def _crop_bbox_ke_b64(shot_b64, bbox):

    try:
        from PIL import Image
        mentah = shot_b64.split(",", 1)[1] if "," in shot_b64 else shot_b64
        img = Image.open(io.BytesIO(base64.b64decode(mentah))).convert("RGB")
        x1 = max(0, int(bbox[0] * img.width))
        y1 = max(0, int(bbox[1] * img.height))
        x2 = min(img.width, int(bbox[2] * img.width))
        y2 = min(img.height, int(bbox[3] * img.height))
        if x2 <= x1 or y2 <= y1:
            return None
        potong = img.crop((x1, y1, x2, y2))
        buf = io.BytesIO()
        potong.save(buf, "JPEG", quality=80)
        return ("data:image/jpeg;base64," +
                base64.b64encode(buf.getvalue()).decode("ascii"))
    except Exception:
        return None


_PROMPT_FORENSIK = (
    "Act as a Digital Forensics Expert. Analyze this image for textures, "
    "lighting inconsistencies, asymmetry, spatial anomalies, and diffusion "
    "artifacts. Determine if this is a real camera photo or an "
    "AI-generated/synthetic image. Provide a very concise 1-2 sentence "
    "conclusion with your confidence percentage."
)


def jalankan_forensik_foto_layar(bahasa="id", pratinjau=None):

    if not BASETEN_API_KEY:
        return "[FORENSICS ERROR] BASETEN_API_KEY is required for photo forensics."
    shot, info = _ambil_screenshot_b64()
    if shot is None:
        return info
    bbox = _bbox_foto_dari_baseten(shot)
    if bbox is None:
        if str(bahasa or "id").lower().startswith("en"):
            return "Sorry Rifan, no photo or picture detected on screen."
        return "Maaf Rifan, tidak ada foto/gambar yang terdeteksi di layar."
    crop = _crop_bbox_ke_b64(shot, bbox)
    if crop is None:
        return "[FORENSICS ERROR] Failed to crop the detected photo."
    if pratinjau is not None:
        pratinjau.update({"image": crop, "target": "foto terdeteksi",
                          "sumber": "forensik"})
    bahasa_tanya = ("Reply in English."
                    if str(bahasa or "id").lower().startswith("en")
                    else "Reply in Bahasa Indonesia.")
    return query_arvi_vision(crop, f"{_PROMPT_FORENSIK} {bahasa_tanya}")


_PEMICU_QR_EN = ("read qr code", "read the qr", "read qr", "read barcode",
                 "scan the qr", "scan barcode now", "scan qr now",
                 "check qr", "decode qr")
_PEMICU_QR_ID = ("baca qr", "baca barcode", "cek qr", "periksa qr",
                 "scan qr", "scan barcode")
_PENANDA_BAHASA_INGGRIS = ("now", "please", "the", "read", "check", "decode")


def deteksi_intent_qr(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if _mengandung_frasa(rendah, _PEMICU_QR_EN):
        return "en"
    if _mengandung_frasa(rendah, _PEMICU_QR_ID):
        if _mengandung_frasa(rendah, _PENANDA_BAHASA_INGGRIS):
            return "en"
        return "id"
    return None


def _decoder_qr_tersedia():

    try:
        from pyzbar.pyzbar import decode as _uji_zbar
        from PIL import Image
        _uji_zbar(Image.new("RGB", (8, 8)))
        return "pyzbar"
    except Exception:
        pass
    try:
        import cv2
        _ = cv2.QRCodeDetector()
        return "cv2"
    except Exception:
        return None


def _varian_qr_untuk_decode(img_pil):

    try:
        from PIL import Image
        lebar = img_pil.width
        if lebar >= 2000:
            return [img_pil]
        ulang = getattr(Image, "LANCZOS", 1)
        varian = [img_pil]
        for skala in (1.5, 2.0):
            baru = (max(1, int(img_pil.width * skala)),
                    max(1, int(img_pil.height * skala)))
            varian.append(img_pil.resize(baru, ulang))
        return varian
    except Exception:
        return [img_pil]


def _decode_qr_satu(img_pil):

    hasil = []
    try:
        from pyzbar.pyzbar import decode as _decode_zbar
        for simbol in _decode_zbar(img_pil):
            try:
                teks = bytes(simbol.data).decode("utf-8", "replace").strip()
            except Exception:
                continue
            if teks and teks not in hasil:
                hasil.append(teks)
        if hasil:
            return hasil
    except Exception:
        pass
    try:
        import cv2
        import numpy as np
        detektor = cv2.QRCodeDetector()
        abu = np.array(img_pil.convert("L"))
        try:
            multi = detektor.detectAndDecodeMulti(abu)
            teks_multi = multi[1] if len(multi) > 1 else ()
        except Exception:
            teks_multi = ()
        for teks in teks_multi or ():
            teks = (teks or "").strip()
            if teks and teks not in hasil:
                hasil.append(teks)
        if not hasil:
            temu = detektor.detectAndDecode(abu)
            teks = (temu[0] or "").strip() if temu else ""
            if teks and teks not in hasil:
                hasil.append(teks)
    except Exception:
        pass
    return hasil


def _decode_qr_lokal(img_pil):

    if img_pil is None:
        return []
    for varian in _varian_qr_untuk_decode(img_pil):
        hasil = _decode_qr_satu(varian)
        if hasil:
            return hasil
    return []


def jalankan_soc_qr_layar(bahasa="id", pratinjau=None):

    shot, info = _ambil_screenshot_b64(lebar_maks=1920)
    if shot is None:
        return info
    img = _pil_dari_b64(shot, lebar_maks=1920)
    teks_qr = _decode_qr_lokal(img)
    if not teks_qr:
        inggris = str(bahasa or "id").lower().startswith("en")
        if _decoder_qr_tersedia() is None:
            if inggris:
                return ("QR reader is not installed — run: pip install "
                        "opencv-python (or pyzbar). Then try scanning again.")
            return ("Modul pembaca QR belum terinstal — jalankan: pip install "
                    "opencv-python (atau pyzbar). Lalu coba pindai lagi.")
        if inggris:
            return "No QR code detected on screen."
        return "QR Code tidak terdeteksi di layar."
    pertama = teks_qr[0]
    if pratinjau is not None:
        pratinjau.update({"image": shot, "target": pertama[:160],
                          "sumber": "qr"})


    from server.ai_engine import query_soc_evaluator
    putusan = query_soc_evaluator(pertama, bahasa)
    return f"{putusan}\n\n[QR] {pertama}"


_PEMICU_APPSEC_EN = ("audit code on screen", "audit code",
                     "check this code for vulnerabilities",
                     "check code for vulnerabilities",
                     "find security bugs", "security bugs",
                     "audit terminal", "audit the terminal", "appsec")
_PEMICU_APPSEC_ID = ("audit kode di layar", "audit kode",
                     "cek kerentanan kode", "cek kerentanan",
                     "kerentanan kode", "periksa keamanan layar",
                     "keamanan kode", "cek bug keamanan", "periksa kode")


_PROMPT_APPSEC_AUDITOR = (
    "You are a Principal Application Security Auditor. Read the programming "
    "code, scripts, configuration, or terminal/error logs visible in this "
    "monitor screenshot (ignore UI elements of the 'ARVI' assistant itself). "
    "Detect critical security flaws: hardcoded API keys/passwords/tokens, "
    "SQL Injection, XSS, Command Injection, insecure deserialization, fatal "
    "logic errors, or the cause of terminal errors/exceptions. "
    "STRICT OUTPUT RULE: reply in 1-3 short sentences ONLY: the status "
    "(SAFE or VULNERABLE), the finding and its line/location, and one "
    "instant fix suggestion. If no code, config, or terminal is visible, "
    "say so briefly."
)


def deteksi_intent_appsec(teks: str):

    mentah = _normalisasi_kata_perintah((teks or "").strip())
    if not mentah:
        return None
    rendah = f" {mentah.lower()} "
    if _mengandung_frasa(rendah, _PEMICU_APPSEC_EN):
        return "en"
    if _mengandung_frasa(rendah, _PEMICU_APPSEC_ID):
        return "id"
    return None


def jalankan_audit_appsec_layar(bahasa="id", pratinjau=None):

    if not BASETEN_API_KEY:
        return "[APPSEC ERROR] BASETEN_API_KEY is required for AppSec screen audit."
    shot, info = _ambil_screenshot_b64(lebar_maks=1920)
    if shot is None:
        return info
    inggris = str(bahasa or "id").lower().startswith("en")
    if pratinjau is not None:
        pratinjau.update({"image": shot,
                          "target": ("audited screen" if inggris
                                     else "layar diaudit"),
                          "sumber": "appsec"})
    bahasa_tanya = ("Reply in English." if inggris
                    else "Reply in Bahasa Indonesia.")
    mentah = query_arvi_vision(
        shot,
        f"{bahasa_tanya} Audit the code/config/terminal on this screen now.",
        prompt_sistem=_PROMPT_APPSEC_AUDITOR)
    from server.ai_engine import bersihkan_reasoning_trace
    return bersihkan_reasoning_trace(mentah)


def urai_vonis_appsec(teks):

    try:
        rendah = (teks or "").lower()
    except Exception:
        rendah = ""
    if "[appsec error]" in rendah or "[screen error]" in rendah:
        status = "ERROR"
    elif re.search(r"vulnerab", rendah):
        status = "VULNERABLE"
    elif re.search(r"(?<![a-z])safe(?![a-z])", rendah):
        status = "SAFE"
    else:
        status = "INFO"
    try:
        detail = re.sub(r"\s+", " ", str(teks or "")).strip()
    except Exception:
        detail = ""
    return {"status": status, "detail": detail}
