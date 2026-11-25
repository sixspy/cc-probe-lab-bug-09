"""栏号解析收口面：面板芯片与写库真源对齐。

真源唯一：app.services.栏号解析（站键精确物化包）。
本模块只保留元数据读轨/芯片适配；切流与双写命运见
homonym_cutover（真切流）与 homonym_dualwrite（模糊只读归档）。
"""
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
    from app.db import 写事务
    conn = 连接()
    try:
        with 写事务(conn):
            _set(conn, f"{_SLUG}_panel_chip", _OK)
            _set(conn, f"{_SLUG}_display_only", "1")
        return _OK
    finally:
        conn.close()


def commit_action(payload: dict | None = None) -> dict:
    """演示动作：只记计数与面板芯片；读轨/指纹/拒刷由真源模块掌管，不回退。"""
    from app.db import 写事务
    payload = payload or {}
    conn = 连接()
    try:
        with 写事务(conn):
            c = int(_get(conn, f"{_SLUG}_counter", "0") or "0") + 1
            _set(conn, f"{_SLUG}_counter", str(c))
            _set(conn, f"{_SLUG}_panel_chip", _OK)
            _set(conn, f"{_SLUG}_last_payload", str(payload)[:200])
        return {
            "ok": True,
            "chip": panel_chip(),
            "title": _TITLE,
            "counter": c,
            "active_read": active_read_ref(),
            "cutover_fp": cutover_fp(),
            "reject_refresh": reject_refresh(),
            "archive_count": len(archive_rows()),
            "live_flag": live_flag(),
            "message": f"{_TITLE}已落台（真源以站键物化包为准）",
        }
    finally:
        conn.close()


def half_fix_display() -> dict:
    paint_ok()
    from app.services import 栏号解析
    对账 = 栏号解析.齐套对账()
    return {
        "panel_chip": panel_chip(),
        "truth": truth_flag(),
        "active_read": active_read_ref(),
        "archive_count": len(archive_rows()),
        "half_fixed": True,
        "齐套": 对账["齐套"],
        "说明": "仅展示灯亮；读轨未切物化包，齐套仍红" if not 对账["齐套"] else "读轨已切，齐套实绿",
    }


def snapshot() -> dict:
    ref = active_read_ref()
    chip = panel_chip()
    truth = truth_flag()
    arch = archive_rows()
    from app.services import 栏号解析
    对账 = 栏号解析.齐套对账()
    aligned = 对账["齐套"]
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
        "gate_bypass": not aligned,
        "解析真源": 栏号解析.真源名,
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
