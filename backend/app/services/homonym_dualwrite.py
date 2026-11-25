"""栏号解析双写两轨：模糊结果只进只读归档，读轨不翻旗。

工程形态择定物化包路线：站名模糊解析被彻底排除在写库与齐套之外，
仅允许落只读归档；现行装载只读站键精确集。
"""
from __future__ import annotations

from app.services import homonym as core
from app.services import 栏号解析


def apply_dualwrite(note: str = "") -> dict:
    # 模糊轨只做归档演示，绝不改 active_read、绝不回刷物化包
    归 = 栏号解析.记模糊归档(
        站名=note or "未注名模糊命中",
        候选栏=[],
        模糊落点="只读归档",
    )
    return {
        "dual_chip": core._OK,
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "archive_count": len(栏号解析.模糊归档列表()),
        "live_flag": core.live_flag(),
        "归档": 归,
        "读引用": "只读归档",
    }


def dual_board() -> dict:
    dash = core.dashboard()
    return {
        "dual_chip": core._OK,
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "archive": 栏号解析.模糊归档列表(),
        "live_flag": core.live_flag(),
        "dash": dash,
        "fate": "dualwrite-只读归档",
        "panel_pack_mismatch": not dash.get("aligned"),
        "title": "栏号解析双写面（模糊只读）",
    }
