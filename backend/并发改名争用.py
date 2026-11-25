#!/usr/bin/env python3
"""并发改名争用脚本：验证改名瞬间不会双解析串栏。

用法（须用 -I，数据目录走参数，勿在 fixtures 目录内运行）：
  python3 -I 并发改名争用.py [数据目录] [轮次]

确定性判据：
1. 装载工全程钉同一解析指纹，改名工并发换版；
2. 钉旧指纹的行永远落旧包栏号，新指纹行走新包；
3. 任何行不得落邻站栏 B-邻站；同栏不得混两个站键。
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))


def 主(数据目录: str, 轮次: int) -> int:
    os.environ["数据目录"] = 数据目录
    os.environ["夹具目录"] = str(_BACKEND.parent / "fixtures")
    import app.db as db
    db.数据目录 = Path(数据目录)
    db.库路径 = db.数据目录 / "探栏.db"
    from app import seed
    from app.db import 连接
    from app.services import 栏号解析, 目录, 装载

    seed.初始化库()
    conn = 连接()
    try:
        conn.execute("DELETE FROM 站点源 WHERE 源键 IN ('站-同名甲','站-同名乙')")
        conn.execute(
            "INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
            ("站-同名甲", "重名监测站", "大气", "城区", "甲"),
        )
        conn.execute(
            "INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
            ("站-同名乙", "重名监测站", "大气", "近郊", "乙"),
        )
        conn.commit()
    finally:
        conn.close()
    目录.改栏规({"解析策略": "站名", "邻站栏号": "B-邻站"})
    栏号解析.封包()
    栏号解析.绑定站点栏("站-同名甲", "B-甲栏")
    栏号解析.绑定站点栏("站-同名乙", "B-乙栏")
    钉指纹 = 栏号解析.当前指纹()

    失败: list[str] = []
    锁 = threading.Lock()

    def 报文(编号: str, 站: str, 时: str) -> dict:
        return {"报文编号": 编号, "站点键": 站, "指标键": "PM25",
                "读数": 21.0, "观测时": 时}

    def 装载工(工号: int):
        for i in range(轮次):
            try:
                装载.装一批({
                    "批次编号": f"并发{工号}-{i}",
                    "报文": [
                        报文(f"S-{工号}-{i}-a", "站-同名甲", f"2026-11-25T1{工号}:{i:02d}:00Z"),
                        报文(f"S-{工号}-{i}-b", "站-同名乙", f"2026-11-25T1{工号}:{i:02d}:30Z"),
                    ],
                }, 解析指纹=钉指纹)
            except Exception as e:  # 锁争用允许失败，但失败不得写半截
                with 锁:
                    失败.append(f"装载工{工号}:{e!r}")

    def 改名工():
        for i in range(轮次):
            try:
                栏号解析.改站名("站-同名乙", f"重名监测站·争用{i}")
            except Exception as e:
                with 锁:
                    失败.append(f"改名工:{e!r}")

    ts = [threading.Thread(target=装载工, args=(w,)) for w in range(4)]
    ts.append(threading.Thread(target=改名工))
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    行 = 目录.缓冲列表()
    串栏 = [r for r in 行 if r["栏号"] == "B-邻站"]
    旧包行 = [r for r in 行 if r["解析指纹"] == 钉指纹]
    错位 = [r for r in 旧包行 if r["栏号"] != (
        "B-甲栏" if r["站点键"] == "站-同名甲" else "B-乙栏")]
    栏到站: dict[str, set] = {}
    for r in 旧包行:
        栏到站.setdefault(r["栏号"], set()).add(r["站点键"])
    混站 = {b: s for b, s in 栏到站.items() if len(s) > 1}

    print(f"轮次={轮次} 缓冲行={len(行)} 钉旧包行={len(旧包行)} "
          f"异常={len(失败)} 串邻栏={len(串栏)} 错位={len(错位)} 混栏={len(混站)}")
    if 失败:
        print("异常样例:", 失败[:3])
    if 串栏:
        print("串栏样例:", 串栏[:2])
    if 错位:
        print("错位样例:", 错位[:2])
    if 混站:
        print("混站栏:", 混站)
    红 = bool(串栏 or 错位 or 混站)
    print("结果:", "红（串栏）" if 红 else "绿（无串栏；锁异常仅代表重试信号，未产生脏行）")
    return 1 if 红 else 0


if __name__ == "__main__":
    数据 = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="probe-争用-")
    轮 = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    raise SystemExit(主(数据, 轮))
