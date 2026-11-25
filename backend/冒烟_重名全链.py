#!/usr/bin/env python3
"""端到端冒烟：ASGI 内打 HTTP，验重名站全链与四页真源可见。"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))


async def 主(数据目录: str) -> int:
    os.environ["数据目录"] = 数据目录
    os.environ["夹具目录"] = str(_BACKEND.parent / "fixtures")
    import app.db as db
    db.数据目录 = Path(数据目录)
    db.库路径 = db.数据目录 / "探栏.db"
    from app import seed
    seed.初始化库()
    from app.main import app
    import httpx

    红: list[str] = []

    async with app.test_app() as qa:
        c = qa.test_client()

        async def get(url):
            r = await c.get(url)
            assert r.status_code == 200, (url, r.status_code)
            return await r.get_json()

        async def post(url, body=None):
            r = await c.post(url, json=body or {})
            return r.status_code, await r.get_json()

        # 1. 造重名站 + 站名模糊陷阱栏规
        from app.db import 连接
        conn = 连接()
        conn.execute("DELETE FROM 站点源 WHERE 源键 IN ('站-同名甲','站-同名乙')")
        conn.execute("INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
                     ("站-同名甲", "重名监测站", "大气", "城区", "甲"))
        conn.execute("INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
                     ("站-同名乙", "重名监测站", "大气", "近郊", "乙"))
        conn.commit()
        conn.close()
        await post("/api/栏规", {"解析策略": "站名", "邻站栏号": "B-邻站"})

        # 2. 封包绑定，切流
        await post("/api/栏号解析/封包", {"备注": "冒烟"})
        sc, 绑甲 = await post("/api/栏号解析/绑定", {"站点键": "站-同名甲", "栏号": "B-甲栏"})
        sc, 绑乙 = await post("/api/栏号解析/绑定", {"站点键": "站-同名乙", "栏号": "B-乙栏"})
        assert sc == 200
        await post("/api/栏号解析/切流")

        # 3. HTTP 装载重名夹具
        sc, 报告 = await post("/api/观测报文/装载", {
            "批次编号": "冒烟重名",
            "报文": [
                {"报文编号": "E-a", "站点键": "站-同名甲", "指标键": "PM25", "读数": 30.1, "观测时": "2026-11-25T08:00:00Z"},
                {"报文编号": "E-b", "站点键": "站-同名乙", "指标键": "PM25", "读数": 33.2, "观测时": "2026-11-25T08:05:00Z"},
            ],
        })
        assert 报告["入栏"] == 2, 报告
        缓冲 = await get("/api/入栏缓冲")
        落 = {r["报文编号"]: r["栏号"] for r in 缓冲}
        if 落 != {"E-a": "B-甲栏", "E-b": "B-乙栏"}:
            红.append(f"串栏: {落}")
        if any(v == "B-邻站" for v in 落.values()):
            红.append("邻站栏吃入")

        # 4. 结栏 + 贯验
        sc, 结 = await post("/api/结栏/跑")
        汇总 = await get("/api/站点汇总账")
        汇落 = {(r["栏号"], r["站点键"]) for r in 汇总}
        if ("B-甲栏", "站-同名甲") not in 汇落 or ("B-乙栏", "站-同名乙") not in 汇落:
            红.append(f"汇总账落位错: {汇落}")
        sc, 贯 = await post("/api/栏贯验/跑")
        if not 贯["是否对齐"]:
            红.append("贯验撕裂")

        # 5. 齐套对账实绿，模糊归档不算精确
        对账 = await get("/api/栏号解析/齐套对账")
        if not 对账["齐套"] or 对账["精确命中"] != 2 or 对账["串栏"] != 0:
            红.append(f"对账异常: {对账}")
        await post("/api/栏号解析/模糊归档", {"站名": "重名监测站", "候选栏": ["B-甲栏", "B-乙栏"], "模糊落点": "B-邻站"})
        对账2 = await get("/api/栏号解析/齐套对账")
        if not 对账2["齐套"] or 对账2["模糊命中"] < 1 or 对账2["精确命中"] != 2:
            红.append(f"模糊归档污染齐套: {对账2}")

        # 6. 模糊回刷硬拒
        sc, 拒 = await post("/api/栏号解析/模糊回刷", {"重名监测站": "B-劫持"})
        if sc != 400 or not 拒.get("拒绝"):
            红.append(f"模糊回刷未拒: {sc} {拒}")

        # 7. 未知指纹装载硬拒
        sc, 幽灵 = await post("/api/观测报文/装载", {
            "批次编号": "幽灵", "解析指纹": "fp-幽灵",
            "报文": [{"报文编号": "E-x", "站点键": "站-同名甲", "指标键": "PM25", "读数": 1, "观测时": "2026-11-25T09:00:00Z"}],
        })
        if sc != 400 or not 幽灵.get("拒绝"):
            红.append(f"幽灵指纹未硬拒: {sc} {幽灵}")
        报文 = await get("/api/观测报文")
        if any(r["报文编号"] == "E-x" for r in 报文):
            红.append("幽灵指纹行落库")

        # 8. 四页 HTML 含真源挂载点
        for 页 in ("/栏规.html", "/报文流.html", "/入栏缓冲.html", "/站点汇总账.html"):
            r = await c.get(页)
            文本 = await r.get_data(as_text=True)
            if "解析真源条" not in 文本:
                红.append(f"{页} 缺真源卡")

        # 9. 真源卡 API
        卡 = await get("/api/栏号解析/真源卡")
        if 卡["解析真源"] != "站键精确" or not 卡["指纹"] or not 卡["齐套"]:
            红.append(f"真源卡异常: {卡}")

    print("冒烟红项:", 红 if 红 else "无")
    print("SMOKE", "RED" if 红 else "GREEN")
    return 1 if 红 else 0


if __name__ == "__main__":
    数据 = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="probe-冒烟-")
    raise SystemExit(asyncio.run(主(数据)))
