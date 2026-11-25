"""栏号解析切流账册：真切到物化包，锁指纹、拒站名模糊回刷。"""
from __future__ import annotations

from app.services import homonym as core
from app.services import 栏号解析


def append_cutover(ref_id: int, note: str = "") -> dict:
    切 = 栏号解析.切流()
    return {
        "ref_id": ref_id,
        "note": note or 切.get("读轨", ""),
        "panel": core.panel_chip(),
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "cutover_fp": core.cutover_fp(),
        "reject_refresh": core.reject_refresh(),
    }


def board() -> dict:
    dash = core.dashboard()
    dash["fate"] = "cutover_book"
    dash["panel_pack_mismatch"] = not dash.get("aligned")
    return dash
