from __future__ import annotations

import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

NAMA_BERKAS = "arvi_node.json"
PANJANG_PSK_HEX = 32


class NodeAuthError(Exception):

    pass


def path_default() -> Path:
    return Path(__file__).resolve().parent / NAMA_BERKAS


def cap_waktu_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _muat(path: str | Path | None = None) -> dict:
    jalur = Path(path) if path else path_default()
    if not jalur.exists():
        return {"format": "arvi-node/1", "psk": ""}
    try:
        data = json.loads(jalur.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as galat:
        raise NodeAuthError(f"Berkas PSK node korup ({jalur}): {galat}") from galat
    if not isinstance(data, dict):
        raise NodeAuthError("Format berkas PSK node tidak valid.")
    return data


def muat_atau_buat_psk(path: str | Path | None = None) -> str:

    data = _muat(path)
    if data.get("psk"):
        return str(data["psk"])
    psk = secrets.token_hex(PANJANG_PSK_HEX)
    jalur = Path(path) if path else path_default()
    try:
        jalur.write_text(json.dumps(
            {"format": "arvi-node/1", "psk": psk,
             "dibuat": cap_waktu_utc_iso()},
            ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as galat:
        raise NodeAuthError(
            f"Berkas PSK node tak bisa ditulis ({jalur}): {galat}") from galat
    return psk


def verifikasi_psk(psk: str | None, path: str | Path | None = None) -> bool:

    if not psk:
        return False
    try:
        simpan = str(_muat(path).get("psk") or "")
    except NodeAuthError:
        return False
    return bool(simpan) and hmac.compare_digest(str(psk), simpan)
