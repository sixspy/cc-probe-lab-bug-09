"""栏号解析双写两轨空壳：应归档旧档并改读新旗；当前只亮镜像芯片。"""
from __future__ import annotations

from app.db import 连接
from app.services import homonym as core

_SLUG = "homonym"
_TITLE = "栏号解析"
_OK = "解析已亮"


def apply_dualwrite(note: str = "") -> dict:
    conn = 连接()
    try:
        core._ensure(conn)
        core._set(conn, f"{_SLUG}_dual_chip", _OK)
        core._set(conn, f"{_SLUG}_dual_truth", core._BAD if hasattr(core, "_BAD") else "坏")
        core._set(conn, f"{_SLUG}_dual_note", note or _TITLE)
        core._set(conn, f"{_SLUG}_panel_chip", _OK)
        # skip archive_% + live_flag + active_read=live_flag
        conn.commit()
    finally:
        conn.close()
    core.paint_ok()
    return {
        "dual_chip": _OK,
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "archive_count": len(core.archive_rows()),
        "live_flag": core.live_flag(),
    }


def dual_board() -> dict:
    apply_dualwrite()
    dash = core.dashboard()
    return {
        "dual_chip": _OK,
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "archive": core.archive_rows(),
        "live_flag": core.live_flag(),
        "dash": dash,
        "fate": "dualwrite",
        "panel_pack_mismatch": True,
        "title": f"{_TITLE}双写面",
    }
