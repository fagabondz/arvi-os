import base64
import re
from io import BytesIO

from server.ai_engine import query_arvi_cognitive

EKSTENSI_GAMBAR = frozenset({".jpg", ".jpeg", ".png", ".webp"})
EKSTENSI_PDF = frozenset({".pdf"})
EKSTENSI_TEKS = frozenset({".txt", ".md", ".csv", ".json", ".xml", ".yaml",
                           ".yml", ".ini", ".py", ".js", ".ts", ".html",
                           ".css", ".sh", ".ps1", ".bat", ".sql", ".log"})
BATAS_BYTE_FILE = 6 * 1024 * 1024
BATAS_CHAR_TEKS = 8000
BATAS_HALAMAN_PDF = 20


def jenis_file(nama_file):

    rendah = (nama_file or "").strip().lower()
    if rendah.endswith(".env.example"):
        return "teks"
    titik = rendah.rfind(".")
    ekst = rendah[titik:] if titik >= 0 else ""
    if ekst in EKSTENSI_GAMBAR:
        return "gambar"
    if ekst in EKSTENSI_PDF:
        return "pdf"
    if ekst in EKSTENSI_TEKS:
        return "teks"
    return None


def daftar_ekstensi_didukung():

    semua = sorted(EKSTENSI_GAMBAR | EKSTENSI_PDF | EKSTENSI_TEKS)
    semua.append(".env.example")
    return ", ".join(semua)


def decode_file_hp(nama_file, data_b64):

    nama = (nama_file or "").strip()
    if not nama:
        raise ValueError("Nama file kosong.")
    jenis = jenis_file(nama)
    if jenis is None:
        raise ValueError(f"Format '{nama}' belum didukung. "
                         f"Didukung: {daftar_ekstensi_didukung()}.")
    try:
        mentah = (data_b64 or "").strip()
        if "," in mentah:
            mentah = mentah.split(",", 1)[1]
        raw = base64.b64decode(mentah)
    except Exception:
        raise ValueError(f"File '{nama}' rusak (base64 tidak valid).")
    if not raw:
        raise ValueError(f"File '{nama}' kosong.")
    if len(raw) > BATAS_BYTE_FILE:
        raise ValueError(f"File '{nama}' terlalu besar (maks 6 MB).")
    return jenis, raw


def data_url_dari_gambar(raw, nama_file):

    rendah = (nama_file or "").lower()
    mime = "image/jpeg"
    if rendah.endswith(".png"):
        mime = "image/png"
    elif rendah.endswith(".webp"):
        mime = "image/webp"
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


def _teks_pdf_pustaka(raw, nama_paket):

    try:
        paket = __import__(nama_paket)
    except Exception:
        return None
    try:
        baca = paket.PdfReader(BytesIO(raw))
        keluar = []
        for halaman in list(baca.pages)[:BATAS_HALAMAN_PDF]:
            try:
                keluar.append(halaman.extract_text() or "")
            except Exception:
                continue
        teks = "\n".join(keluar).strip()
        return teks or None
    except Exception:
        return None


def _teks_pdf_regex(raw):

    try:
        teks = raw.decode("latin-1", errors="ignore")
    except Exception:
        return None
    fragmen = re.findall(r"\(((?:[^()\\]|\\.)*)\)\s*Tj", teks)
    bersih = []
    for bagian in fragmen[:400]:
        isi = re.sub(r"\\([()\\])", r"\1", bagian)
        isi = re.sub(r"\s+", " ", isi).strip()
        if isi:
            bersih.append(isi)
    return " ".join(bersih).strip() or None


def ekstrak_teks_pdf(raw):

    return (_teks_pdf_pustaka(raw, "pypdf")
            or _teks_pdf_pustaka(raw, "PyPDF2")
            or _teks_pdf_regex(raw) or "")


def baca_teks_aman(raw, batas=BATAS_CHAR_TEKS):

    teks = raw.decode("utf-8", errors="replace").replace("\x00", "")
    teks = teks.strip()
    if len(teks) > batas:
        return teks[:batas], True
    return teks, False


def analisis_dokumen_teks(jenis, nama_file, isi_teks, instruksi):

    perintah = (instruksi or "").strip() or (
        "Summarize this document briefly." if jenis == "pdf"
        else "Review this file briefly.")
    label = "PDF text" if jenis == "pdf" else "File content"
    prompt = f"{perintah}\n\nFile: {nama_file}\n{label}:\n{isi_teks}"
    return query_arvi_cognitive(prompt)


def proses_dokumen_hp(jenis, nama_file, raw, instruksi):

    if jenis == "pdf":
        isi = ekstrak_teks_pdf(raw).strip()
        if not isi:
            raise ValueError(f"Tidak ada teks terbaca dari '{nama_file}'.")
        terpotong = len(isi) > BATAS_CHAR_TEKS
        if terpotong:
            isi = isi[:BATAS_CHAR_TEKS]
    else:
        isi, terpotong = baca_teks_aman(raw)
        if not isi:
            raise ValueError(f"File '{nama_file}' kosong.")
    if terpotong:
        isi += "\n[...dipotong...]"
    return analisis_dokumen_teks(jenis, nama_file, isi, instruksi)
