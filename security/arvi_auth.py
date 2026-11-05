from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

MASA_BERLAKU_TOKEN_JAM = 8
NAMA_ENV_SECRET = "ARVI_MASTER_SECRET"


class AuthError(Exception):

    pass


class TokenTidakValidError(AuthError):

    pass


class TokenKedaluwarsaError(AuthError):

    pass


def path_env_default() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def baca_master_secret(path_env: str | Path | None = None) -> str:

    jalur = Path(path_env) if path_env else path_env_default()
    try:
        isi = jalur.read_text(encoding="utf-8")
    except OSError as galat:
        raise AuthError(
            f"Berkas .env tidak bisa dibaca ({jalur}): {galat}") from galat
    for baris in isi.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, nilai = baris.split("=", 1)
        if kunci.strip() == NAMA_ENV_SECRET:
            secret = nilai.strip().strip('"').strip("'").strip()
            if secret:
                return secret
            break
    raise AuthError(f"{NAMA_ENV_SECRET} kosong/hilang di {jalur}.")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    tambal = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + tambal).encode("ascii"))


def _kunci_token() -> bytes:
    return hashlib.sha256(
        baca_master_secret().encode("utf-8") + b"|arvi-sesi-v1"
    ).digest()


def buat_token(pemilik: str, metode: str, jam_berlaku: float = MASA_BERLAKU_TOKEN_JAM,
               peran: str = "operator") -> str:

    kini = int(time.time())
    payload = {"sub": pemilik, "metode": metode, "peran": peran, "iat": kini,
               "exp": kini + int(jam_berlaku * 3600)}
    badan = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    tag = hmac.new(_kunci_token(), f"v1.{badan}".encode("ascii"), hashlib.sha256).hexdigest()
    return f"v1.{badan}.{tag}"


def verifikasi_token(token: str) -> dict:

    try:
        versi, badan, tag = str(token).split(".")
        if versi != "v1":
            raise ValueError("versi")
        harapan = hmac.new(
            _kunci_token(), f"v1.{badan}".encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(tag, harapan):
            raise TokenTidakValidError("Tanda tangan token tidak cocok.")
        klaim = json.loads(_b64url_decode(badan).decode("utf-8"))
        if not isinstance(klaim, dict) or "sub" not in klaim or "exp" not in klaim:
            raise TokenTidakValidError("Isi token tidak lengkap.")
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as galat:
        raise TokenTidakValidError(f"Format token salah: {galat}") from galat
    if int(klaim["exp"]) < int(time.time()):
        raise TokenKedaluwarsaError("Token sudah kedaluwarsa; login ulang.")
    return klaim
