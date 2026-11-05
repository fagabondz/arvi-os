from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

NAMA_BERKAS = "arvi_users.json"
ITERASI_PBKDF2 = 200_000
PANJANG_GARAM = 16
PANJANG_MIN_SANDI = 8
PANJANG_MAKS_SANDI = 200
PANJANG_NAMA_MAKS = 40


class UsersError(Exception):

    pass


class LoginGagalError(UsersError):

    pass


def path_default() -> Path:
    return Path(__file__).resolve().parent / NAMA_BERKAS


def cap_waktu_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validasi_username(username: str) -> str:

    bersih = " ".join(str(username or "").split())
    if not bersih:
        raise ValueError("Username tidak boleh kosong.")
    if len(bersih) > PANJANG_NAMA_MAKS:
        raise ValueError(f"Username maksimal {PANJANG_NAMA_MAKS} karakter.")
    return bersih


def validasi_password(password: str) -> str:

    sandi = str(password or "")
    if len(sandi) < PANJANG_MIN_SANDI:
        raise ValueError(f"Sandi minimal {PANJANG_MIN_SANDI} karakter.")
    if len(sandi) > PANJANG_MAKS_SANDI:
        raise ValueError(f"Sandi maksimal {PANJANG_MAKS_SANDI} karakter.")
    return sandi


def _hash(sandi: str, garam: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", sandi.encode("utf-8"), garam, ITERASI_PBKDF2)


def _muat(path: str | Path | None = None) -> dict:

    jalur = Path(path) if path else path_default()
    if not jalur.exists():
        return {"format": "arvi-users/1", "users": {}}
    try:
        data = json.loads(jalur.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as galat:
        raise UsersError(f"Berkas akun korup ({jalur}): {galat}") from galat
    if not isinstance(data, dict) or not isinstance(data.get("users"), dict):
        raise UsersError("Format berkas akun tidak valid.")
    return data


def _simpan(data: dict, path: str | Path | None = None) -> None:
    jalur = Path(path) if path else path_default()
    data = {"format": "arvi-users/1", "users": data.get("users", {})}
    sementara = jalur.with_suffix(".json.tulis")
    sementara.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(sementara, jalur)


def ada_pengguna(path: str | Path | None = None) -> bool:

    return bool(_muat(path).get("users"))


def daftar_pengguna(path: str | Path | None = None) -> list[dict]:

    data = _muat(path)
    return [
        {"username": nama, "peran": rekam.get("peran", "operator"),
         "dibuat_pada": rekam.get("dibuat_pada", "")}
        for nama, rekam in data.get("users", {}).items()
        if isinstance(rekam, dict)
    ]


def _cari(users: dict, username: str) -> tuple[str, dict] | None:
    target = username.strip().lower()
    for nama, rekam in users.items():
        if not isinstance(rekam, dict):
            continue
        if str(nama).strip().lower() == target:
            return str(nama), rekam
    return None


def buat_pengguna_pertama(
    username: str, password: str, path: str | Path | None = None
) -> dict:

    nama = validasi_username(username)
    sandi = validasi_password(password)
    data = _muat(path)
    users = data.get("users", {})
    if users:
        raise FileExistsError("Akun sudah ada; setup tertutup.")
    garam = secrets.token_bytes(PANJANG_GARAM)
    users[nama] = {
        "salt_hex": garam.hex(),
        "hash_hex": _hash(sandi, garam).hex(),
        "iterasi": ITERASI_PBKDF2,
        "peran": "pemilik",
        "dibuat_pada": cap_waktu_utc_iso(),
    }
    data["users"] = users
    _simpan(data, path)
    return {"username": nama, "peran": "pemilik"}


def verifikasi(
    username: str, password: str, path: str | Path | None = None
) -> dict:

    nama = " ".join(str(username or "").split())
    sandi = str(password or "")
    users = _muat(path).get("users", {})
    temu = _cari(users, nama) if nama else None
    if temu is None:
        _hash(sandi, secrets.token_bytes(PANJANG_GARAM))
        raise LoginGagalError("Username atau sandi salah.")
    kunci, rekam = temu
    try:
        garam = bytes.fromhex(rekam["salt_hex"])
        harapan = bytes.fromhex(rekam["hash_hex"])
    except (KeyError, ValueError) as galat:
        raise UsersError(f"Rekam akun '{kunci}' korup: {galat}") from galat
    if not hmac.compare_digest(_hash(sandi, garam), harapan):
        raise LoginGagalError("Username atau sandi salah.")
    return {"username": kunci, "peran": rekam.get("peran", "operator")}
