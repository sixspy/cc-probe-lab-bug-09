"""栏号解析收口面：页灯可绿，切流/双写命运未贯彻，读轨仍旧。"""
from __future__ import annotations

from app.db import 连接

_SLUG = "homonym"
_OK = "解析已亮"
_BAD = "重名串栏"
_TITLE = "栏号解析"
_OLD = "old_track"
_CUTOVER = "cutover_book"
_LIVE = "live_flag"


def _ensure(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS 探栏元("
        "键 TEXT PRIMARY KEY, 值 TEXT NOT NULL)"
    )


def _get(conn, key: str, default: str = "") -> str:
    _ensure(conn)
    r = conn.execute("SELECT 值 FROM 探栏元 WHERE 键=?", (key,)).fetchone()
    return r["值"] if r else default


def _set(conn, key: str, value: str) -> None:
    _ensure(conn)
    conn.execute(
        "INSERT INTO 探栏元(键,值) VALUES (?,?) "
        "ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
        (key, value),
    )


def panel_chip() -> str:
    conn = 连接()
    try:
        return _get(conn, f"{_SLUG}_panel_chip", _OK)
    finally:
        conn.close()


def truth_flag() -> str:
    conn = 连接()
    try:
        return _get(conn, f"{_SLUG}_truth", _BAD)
    finally:
        conn.close()


def active_read_ref() -> str:
    conn = 连接()
    try:
        return _get(conn, f"{_SLUG}_active_read", _OLD)
    finally:
        conn.close()


def cutover_fp() -> str:
    conn = 连接()
    try:
        return _get(conn, f"{_SLUG}_cutover_fp", "stale-fp")
    finally:
        conn.close()


def reject_refresh() -> bool:
    conn = 连接()
    try:
        return _get(conn, f"{_SLUG}_reject_refresh", "0") == "1"
    finally:
        conn.close()


def live_flag() -> str:
    conn = 连接()
    try:
        return _get(conn, f"{_SLUG}_live_flag", "")
    finally:
        conn.close()


def archive_rows() -> list[dict]:
    conn = 连接()
    try:
        _ensure(conn)
        rows = conn.execute(
            "SELECT 键,值 FROM 探栏元 WHERE 键 LIKE ? ORDER BY 键",
            (f"{_SLUG}_archive_%",),
        ).fetchall()
        return [{"键": r["键"], "值": r["值"]} for r in rows]
    finally:
        conn.close()


def paint_ok() -> str:
    conn = 连接()
    try:
        _set(conn, f"{_SLUG}_panel_chip", _OK)
        _set(conn, f"{_SLUG}_display_only", "1")
        conn.commit()
        return _OK
    finally:
        conn.close()


def commit_action(payload: dict | None = None) -> dict:
    """Broken：亮灯，读轨仍 old_track，无耐久命运。"""
    payload = payload or {}
    conn = 连接()
    try:
        c = int(_get(conn, f"{_SLUG}_counter", "0") or "0") + 1
        _set(conn, f"{_SLUG}_counter", str(c))
        _set(conn, f"{_SLUG}_panel_chip", _OK)
        _set(conn, f"{_SLUG}_last_payload", str(payload)[:200])
        _set(conn, f"{_SLUG}_gate_bypass", "1")
        _set(conn, f"{_SLUG}_active_read", _OLD)
        _set(conn, f"{_SLUG}_reject_refresh", "0")
        if not _get(conn, f"{_SLUG}_cutover_fp", ""):
            _set(conn, f"{_SLUG}_cutover_fp", "stale-fp")
        _set(conn, f"{_SLUG}_pack_decoy", f"stale-fp|{c}")
        _set(conn, f"{_SLUG}_truth", _BAD)
        _set(conn, f"{_SLUG}_mode", "")
        _set(conn, f"{_SLUG}_live_flag", "")
        conn.commit()
        return {
            "ok": True,
            "chip": _OK,
            "title": _TITLE,
            "counter": c,
            "active_read": _OLD,
            "cutover_fp": "stale-fp",
            "reject_refresh": False,
            "archive_count": 0,
            "live_flag": "",
            "message": f"{_TITLE}已落台",
        }
    finally:
        conn.close()


def half_fix_display() -> dict:
    paint_ok()
    return {
        "panel_chip": panel_chip(),
        "truth": truth_flag(),
        "active_read": active_read_ref(),
        "archive_count": len(archive_rows()),
        "half_fixed": True,
    }


def snapshot() -> dict:
    ref = active_read_ref()
    chip = panel_chip()
    truth = truth_flag()
    arch = archive_rows()
    aligned = (
        chip == truth == _OK
        and ref in (_CUTOVER, _LIVE)
        and (
            (ref == _CUTOVER and reject_refresh() and cutover_fp() not in ("", "stale-fp"))
            or (ref == _LIVE and bool(live_flag()) and len(arch) > 0)
        )
    )
    return {
        "title": _TITLE,
        "panel_chip": chip,
        "truth": truth,
        "active_read": ref,
        "cutover_fp": cutover_fp(),
        "reject_refresh": reject_refresh(),
        "archive_count": len(arch),
        "live_flag": live_flag(),
        "aligned": aligned,
        "panel_pack_mismatch": chip == _OK and not aligned,
        "gate_bypass": True,
    }


def dashboard() -> dict:
    snap = snapshot()
    return {
        **snap,
        "ok_chip": _OK,
        "bad_chip": _BAD,
        "label": _TITLE,
        "read_tracks": {
            "old_track": _OLD,
            "cutover_book": _CUTOVER,
            "live_flag": _LIVE,
        },
    }


def reconcile_display() -> dict:
    return half_fix_display()
