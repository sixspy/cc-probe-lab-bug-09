"""栏号解析切流账册空壳：应锁指纹拒回刷；当前只记软笔记。"""
from __future__ import annotations

from app.db import 连接
from app.services import homonym as core

_SLUG = "homonym"
_TITLE = "栏号解析"
_OK = "解析已亮"


def append_cutover(ref_id: int, note: str = "") -> dict:
    conn = 连接()
    try:
        core._ensure(conn)
        core._set(conn, f"{_SLUG}_cutover_note_{ref_id}", note or _TITLE)
        core._set(conn, f"{_SLUG}_panel_chip", _OK)
        # missing durable fp + reject_refresh + active_read rewrite
        conn.commit()
    finally:
        conn.close()
    return {
        "ref_id": ref_id,
        "note": note,
        "panel": core.panel_chip(),
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "cutover_fp": core.cutover_fp(),
        "reject_refresh": core.reject_refresh(),
    }


def board() -> dict:
    dash = core.dashboard()
    dash["fate"] = "cutover_book"
    dash["panel_pack_mismatch"] = True
    return dash
