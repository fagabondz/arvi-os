from __future__ import annotations

import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

NAMA_BERKAS = "arvi_mobile.json"
PANJANG_TOKEN_BYTE = 32
PANJANG_LABEL_MAKS = 40


class MobileError(Exception):

    pass


def path_default() -> Path:
    return Path(__file__).resolve().parent / NAMA_BERKAS


def cap_waktu_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _muat(path: str | Path | None = None) -> dict:

    jalur = Path(path) if path else path_default()
    if not jalur.exists():
        return {"format": "arvi-mobile/1", "token": ""}
    try:
        data = json.loads(jalur.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as galat:
        raise MobileError(f"Berkas token HP korup ({jalur}): {galat}") from galat
    if not isinstance(data, dict):
        raise MobileError("Format berkas token HP tidak valid.")
    return data


def _simpan(data: dict, path: str | Path | None = None) -> None:
    jalur = Path(path) if path else path_default()
    try:
        jalur.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    except OSError as galat:
        raise MobileError(
            f"Berkas token HP tak bisa ditulis ({jalur}): {galat}") from galat


def buat_token_hp(label: str = "qr-hp",
                  path: str | Path | None = None) -> str:

    token = secrets.token_urlsafe(PANJANG_TOKEN_BYTE)
    _simpan({"format": "arvi-mobile/1", "token": token,
             "label": str(label or "")[:PANJANG_LABEL_MAKS],
             "dibuat": cap_waktu_utc_iso()}, path)
    return token


def muat_atau_buat_token_hp(path: str | Path | None = None) -> str:

    data = _muat(path)
    if data.get("token"):
        return str(data["token"])
    return buat_token_hp(path=path)


def verifikasi_token_hp(token: str | None,
                        path: str | Path | None = None) -> bool:

    if not token:
        return False
    try:
        simpan = str(_muat(path).get("token") or "")
    except MobileError:
        return False
    return bool(simpan) and hmac.compare_digest(str(token), simpan)


def cabut_token_hp(path: str | Path | None = None) -> None:

    _simpan({"format": "arvi-mobile/1", "token": "",
             "dicabut": cap_waktu_utc_iso()}, path)
