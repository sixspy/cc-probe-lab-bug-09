"""栏号解析读轨审计。"""
from __future__ import annotations

from app.services import homonym as core
from app.services import homonym_cutover as cutover
from app.services import homonym_dualwrite as dual


def audit_summary() -> dict:
    return {
        "title": "栏号解析审计",
        "core": core.dashboard(),
        "cutover": cutover.board(),
        "dualwrite": dual.dual_board(),
        "half": core.half_fix_display(),
    }
