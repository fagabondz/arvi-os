import base64
import io
import math
import re

import requests

META_URL = "https://api.meta.ai/v1/responses"
MODEL_SAM = "sam-3.1"
LEBAR_KIRIM_MAKS = 1024

_RE_FRAME = re.compile(r"<(\d+)f>")
_RE_BOX = re.compile(r"(\d+)<\|box;([^|]*)\|>")


_RE_MASK = re.compile(
    r"<\|mask;(.*?)\|>(?=,\d+<\|box;|<\d+f>|\s*$)", re.DOTALL)
_RE_DATA = re.compile(r"data=(\d+),(\d+),(.)(.*)$", re.DOTALL)


class SamError(Exception):

    pass


def _ke_pil(image_b64):
    from PIL import Image
    mentah = (image_b64 or "").strip()
    if "," in mentah:
        mentah = mentah.split(",", 1)[1]
    try:
        return Image.open(io.BytesIO(base64.b64decode(mentah))).convert("RGB")
    except Exception as galat:
        raise SamError(f"invalid image: {galat}")


def _siapkan_gambar(image_b64):

    img = _ke_pil(image_b64)
    if img.width > LEBAR_KIRIM_MAKS:
        skala = LEBAR_KIRIM_MAKS / img.width
        img = img.resize((LEBAR_KIRIM_MAKS, max(1, int(img.height * skala))))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    return img, url, (img.width, img.height)


def prompt_konsep(frasa):

    frasa = " ".join((frasa or "").split())
    if not frasa:
        raise SamError("empty concept phrase")
    return frasa


def prompt_box(bbox_norm, lebar, tinggi, id_objek=1):

    try:
        x1n, y1n, x2n, y2n = [float(v) for v in bbox_norm]
    except (TypeError, ValueError):
        raise SamError("invalid bbox")
    kiri = max(0, min(lebar - 1, int(math.floor(x1n * lebar))))
    atas = max(0, min(tinggi - 1, int(math.floor(y1n * tinggi))))
    kanan = max(kiri + 1, min(lebar, int(math.ceil(x2n * lebar))))
    bawah = max(atas + 1, min(tinggi, int(math.ceil(y2n * tinggi))))
    return (f"<0f>{int(id_objek)}<|box;x1={kiri};y1={atas};"
            f"x2={kanan - 1};y2={bawah - 1};w={lebar};h={tinggi}|>")


def _teks_dari_respons(data):

    if isinstance(data, dict) and isinstance(data.get("output_text"), str):
        return data["output_text"]
    potongan = []
    for item in (data.get("output", []) if isinstance(data, dict) else []):
        if isinstance(item, dict) and item.get("type") == "message":
            for bagian in item.get("content", []) or []:
                if isinstance(bagian, dict) and bagian.get("type") == "output_text":
                    potongan.append(bagian.get("text", ""))
    return "".join(potongan)


def panggil_sam31(api_key, teks_prompt, image_url, timeout=60, sesi=None):

    if not api_key:
        raise SamError("META_API_KEY is empty")
    muatan = {
        "model": MODEL_SAM,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": teks_prompt},
            {"type": "input_image", "image_url": image_url},
        ]}],
        "metadata": {"include_confidence": "true", "mask_encoding": "one_bit"},
    }
    kepala = {"Authorization": f"Bearer {api_key}",
              "Content-Type": "application/json"}
    try:
        res = (sesi or requests).post(META_URL, headers=kepala, json=muatan,
                                      timeout=timeout)
    except requests.RequestException as galat:
        raise SamError(f"network: {galat}")
    if res.status_code == 200:
        return _teks_dari_respons(res.json())
    if res.status_code in (401, 403):
        raise SamError("Meta key rejected (401/403)")
    if res.status_code == 404:
        raise SamError("sam-3.1 model not found / account has no access (404)")
    raise SamError(f"HTTP {res.status_code}: {res.text[:200]}")


def _kv(isi):
    out = {}
    for bagian in isi.split(";"):
        if "=" in bagian:
            k, v = bagian.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def parse_keluaran(teks):

    hasil = []
    teks = teks or ""
    penanda = list(_RE_FRAME.finditer(teks))
    for i, m in enumerate(penanda):
        frame = int(m.group(1))
        ujung = penanda[i + 1].start() if i + 1 < len(penanda) else len(teks)
        baris = teks[m.end():ujung]
        for bm in _RE_BOX.finditer(baris):
            f = _kv(bm.group(2))
            try:
                kiri, atas = int(f["x1"]), int(f["y1"])
                kanan, bawah = int(f["x2"]) + 1, int(f["y2"]) + 1
                w, h = int(f["w"]), int(f["h"])
            except (KeyError, ValueError):
                continue
            conf = None
            if "c" in f:
                try:
                    conf = float(f["c"])
                except ValueError:
                    conf = None
            mask = None
            mm = _RE_MASK.match(baris, bm.end())
            if mm:
                dm = _RE_DATA.search(mm.group(1))
                if dm:
                    mask = {"tinggi": int(dm.group(1)), "lebar": int(dm.group(2)),
                            "enc": dm.group(3), "payload": dm.group(4),
                            "mentah": mm.group(0)}
            hasil.append({"frame": frame, "id": int(bm.group(1)),
                          "box": [kiri, atas, kanan, bawah], "w": w, "h": h,
                          "conf": conf, "mask": mask})
    return hasil


def _poligon_valid(poli):

    if not isinstance(poli, (list, tuple)) or len(poli) < 3:
        return False
    try:
        for titik in poli:
            x, y = float(titik[0]), float(titik[1])
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                return False
    except (TypeError, ValueError, IndexError):
        return False
    return True


def _oktagon_dari_box(box, w, h):

    try:
        kiri, atas, kanan, bawah = [float(v) for v in box]
        w, h = float(w), float(h)
    except (TypeError, ValueError):
        return []
    if w <= 0 or h <= 0 or kanan <= kiri or bawah <= atas:
        return []
    potong = 0.2 * min(kanan - kiri, bawah - atas)
    titik = [(kiri + potong, atas), (kanan - potong, atas),
             (kanan, atas + potong), (kanan, bawah - potong),
             (kanan - potong, bawah), (kiri + potong, bawah),
             (kiri, bawah - potong), (kiri, atas + potong)]
    return [[round(min(1.0, max(0.0, x / w)), 4),
             round(min(1.0, max(0.0, y / h)), 4)] for x, y in titik]


def _poligon_dari_mask(record):

    rek = record or {}
    try:
        import meta_sam_parser as _msp
    except Exception:
        _msp = None
    if _msp is not None:
        mask = rek.get("mask") or {}
        muatan = mask.get("payload") or ""
        if muatan:
            for kandidat in ("decode_mask_to_polygon", "decode_mask"):
                fungsi = getattr(_msp, kandidat, None)
                if not callable(fungsi):
                    continue
                try:
                    poli = fungsi(muatan)
                except Exception:
                    continue
                if _poligon_valid(poli):
                    return [[round(float(p[0]), 4), round(float(p[1]), 4)]
                            for p in poli]
    return _oktagon_dari_box(rek.get("box"), rek.get("w"), rek.get("h"))


def _gambar_anotasi(img, rekaman):
    from PIL import Image, ImageDraw
    dasar = img.convert("RGBA")
    lapisan = Image.new("RGBA", dasar.size, (0, 0, 0, 0))
    gambar = ImageDraw.Draw(lapisan)
    for r in rekaman:
        poli = _poligon_dari_mask(r)
        if poli:
            piksel = [(p[0] * dasar.width, p[1] * dasar.height)
                      for p in poli]
            gambar.polygon(piksel, fill=(0, 240, 255, 55))
            gambar.line(piksel + [piksel[0]], fill=(0, 240, 255, 255),
                        width=3)
    anotasi = Image.alpha_composite(dasar, lapisan).convert("RGB")
    pena = ImageDraw.Draw(anotasi)
    for r in rekaman:
        sx = img.width / float(r["w"] or img.width)
        sy = img.height / float(r["h"] or img.height)
        kiri, atas = int(r["box"][0] * sx), int(r["box"][1] * sy)
        label = f"#{r['id']}" + (f" - {r['conf'] * 100:.0f}%" if r['conf'] is not None else "")
        pena.rectangle([kiri, max(0, atas - 14), kiri + 8 * len(label) + 6, atas],
                       fill=(0, 240, 255))
        pena.text((kiri + 3, max(0, atas - 13)), label, fill=(0, 0, 0))
    buf = io.BytesIO()
    anotasi.save(buf, "JPEG", quality=75)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def segmentasi_sam31(image_b64, api_key, konsep=None, bbox_norm=None, sesi=None):

    kosong = {"sam_aktif": False, "annotated_image": "", "polygons": [],
              "bbox": [0.0, 0.0, 0.0, 0.0], "vertices_count": 0,
              "mask_count": 0, "confidence": 0.0,
              "model": MODEL_SAM, "mode": "", "galat": ""}
    try:
        img, url, (w, h) = _siapkan_gambar(image_b64)
        if konsep:
            teks_prompt, mode = prompt_konsep(konsep), "konsep"
        elif bbox_norm:
            teks_prompt, mode = prompt_box(bbox_norm, w, h), "box"
        else:
            raise SamError("need konsep or bbox_norm")
        keluar = panggil_sam31(api_key, teks_prompt, url, sesi=sesi)
        rekaman = [r for r in parse_keluaran(keluar) if r["frame"] == 0]
    except SamError as galat:
        return dict(kosong, galat=str(galat))
    except Exception as galat:
        return dict(kosong, galat=f"unexpected: {galat}")

    hasil = dict(kosong, sam_aktif=True, mode=mode)
    if not rekaman:
        return hasil
    utama = max(rekaman, key=lambda r: (r["conf"] if r["conf"] is not None else 0.0))
    kiri, atas, kanan, bawah = utama["box"]
    w, h = float(utama["w"] or w), float(utama["h"] or h)
    poligon = [p for p in (_poligon_dari_mask(r) for r in rekaman) if p]
    daftar_conf = [r["conf"] for r in rekaman if r["conf"] is not None]
    hasil.update(
        annotated_image=_gambar_anotasi(img, rekaman),
        polygons=poligon,
        bbox=[round(min(1.0, kiri / w), 4), round(min(1.0, atas / h), 4),
              round(min(1.0, kanan / w), 4), round(min(1.0, bawah / h), 4)],
        vertices_count=sum(len(p) for p in poligon),
        mask_count=len(rekaman),
        confidence=round(sum(daftar_conf) / len(daftar_conf) * 100, 1) if daftar_conf else 0.0,
    )
    return hasil
