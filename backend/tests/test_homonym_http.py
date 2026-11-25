"""HTTP 层回归：四页真源可见、模糊回刷/未知指纹硬拒、重名不串栏。"""
import pytest
import pytest_asyncio

from app.main import app
from app.db import 连接


@pytest_asyncio.fixture()
async def 客户端():
    async with app.test_app() as qa:
        yield qa.test_client()


async def _造重名(client):
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
    await client.post("/api/栏规", json={"解析策略": "站名", "邻站栏号": "B-邻站"})
    await client.post("/api/栏号解析/封包", json={"备注": "http"})
    await client.post("/api/栏号解析/绑定", json={"站点键": "站-同名甲", "栏号": "B-甲栏"})
    await client.post("/api/栏号解析/绑定", json={"站点键": "站-同名乙", "栏号": "B-乙栏"})
    await client.post("/api/栏号解析/切流")


@pytest.mark.asyncio
async def test_四页可见解析真源(客户端):
    for 页 in ("/栏规.html", "/报文流.html", "/入栏缓冲.html", "/站点汇总账.html"):
        r = await 客户端.get(页)
        assert r.status_code == 200
        assert "解析真源条" in await r.get_data(as_text=True)
    r = await 客户端.get("/api/栏号解析/真源卡")
    j = await r.get_json()
    assert j["解析真源"] == "站键精确" and j["指纹"]


@pytest.mark.asyncio
async def test_http重名不串栏_模糊回刷与幽灵指纹硬拒(客户端):
    await _造重名(客户端)
    r = await 客户端.post("/api/观测报文/装载", json={
        "批次编号": "http重名",
        "报文": [
            {"报文编号": "H-a", "站点键": "站-同名甲", "指标键": "PM25", "读数": 30.1, "观测时": "2026-11-25T08:00:00Z"},
            {"报文编号": "H-b", "站点键": "站-同名乙", "指标键": "PM25", "读数": 33.2, "观测时": "2026-11-25T08:05:00Z"},
        ],
    })
    assert (await r.get_json())["入栏"] == 2
    r = await 客户端.get("/api/入栏缓冲")
    落 = {x["报文编号"]: x["栏号"] for x in await r.get_json()}
    assert 落 == {"H-a": "B-甲栏", "H-b": "B-乙栏"}

    r = await 客户端.post("/api/栏号解析/模糊回刷", json={"重名监测站": "B-劫持"})
    assert r.status_code == 400
    assert (await r.get_json())["拒绝"] is True

    r = await 客户端.post("/api/观测报文/装载", json={
        "批次编号": "幽灵", "解析指纹": "fp-幽灵",
        "报文": [{"报文编号": "H-x", "站点键": "站-同名甲", "指标键": "PM25", "读数": 1, "观测时": "2026-11-25T09:00:00Z"}],
    })
    assert r.status_code == 400
    r = await 客户端.get("/api/观测报文")
    assert all(x["报文编号"] != "H-x" for x in await r.get_json())

    r = await 客户端.get("/api/栏号解析/齐套对账")
    对账 = await r.get_json()
    assert 对账["齐套"] is True and 对账["串栏"] == 0 and 对账["精确命中"] == 2
