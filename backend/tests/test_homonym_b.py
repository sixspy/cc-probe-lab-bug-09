"""失败测乙：栏规对账不得把模糊命中当精确齐套；半修展示不得转绿。

假绿分属目录与装载：目录 homonym_齐套灯 只看面板芯片，装载写库走另一解析函数。
本文件钉死：齐套只认站键精确物化包，模糊命中单列只读归档。
"""
from app.db import 连接
from app.services import 装载, 目录, 夹具
from app.services import homonym
from app.services import 栏号解析


def _造重名两站():
    conn = 连接()
    try:
        conn.execute("DELETE FROM 站点源 WHERE 源键 IN ('站-同名甲','站-同名乙')")
        conn.execute(
            "INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
            ("站-同名甲", "重名监测站", "大气", "城区", "重名夹具甲"),
        )
        conn.execute(
            "INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
            ("站-同名乙", "重名监测站", "大气", "近郊", "重名夹具乙"),
        )
        conn.commit()
    finally:
        conn.close()


def test_半修只亮展示灯_齐套仍红():
    半 = homonym.half_fix_display()
    assert 半["panel_chip"] == "解析已亮"  # 面板可以绿
    对账 = 栏号解析.齐套对账()
    assert 对账["解析真源"] == "站键精确"
    assert 对账["齐套"] is False  # 读轨仍是 old_track，不得假绿
    # 目录页齐套灯必须取对账实值，不得只看面板芯片
    灯 = 目录.homonym_齐套灯()
    assert 灯["齐套"] is False
    assert 灯["对齐实值"] is False


def test_模糊命中只进只读归档_不算精确齐套():
    _造重名两站()
    目录.改栏规({"解析策略": "站名", "邻站栏号": "B-邻站"})
    栏号解析.封包()
    栏号解析.绑定站点栏("站-同名甲", "B-甲栏")
    栏号解析.绑定站点栏("站-同名乙", "B-乙栏")
    装载.装一批(夹具.读取("重名站样例"))

    # 模拟页侧站名模糊解析：只能落只读归档
    栏号解析.记模糊归档("重名监测站", ["B-甲栏", "B-乙栏"], "B-邻站")
    对账 = 栏号解析.齐套对账()
    assert 对账["模糊命中"] >= 1
    assert 对账["精确命中"] == 2          # 精确只认站键物化包
    assert 对账["模糊命中"] != 0
    # 模糊行绝不计入精确，齐套不因模糊归档变绿（读轨未切）
    assert 对账["齐套"] is False
    assert all("B-邻站" not in str(m) or m.get("来源") != "精确" for m in 对账["明细"])


def test_切流后精确齐套才转绿_且指纹拒回刷():
    _造重名两站()
    包 = 栏号解析.封包()
    绑甲 = 栏号解析.绑定站点栏("站-同名甲", "B-甲栏")
    绑乙 = 栏号解析.绑定站点栏("站-同名乙", "B-乙栏")
    # 物化包不可变：绑定换版，现行指纹为最后一版
    现行 = 栏号解析.当前指纹()
    assert 现行 == 绑乙["指纹"]
    assert 包["指纹"] != 现行
    装载.装一批(夹具.读取("重名站样例"))

    切 = 栏号解析.切流()
    assert 切["读轨"] == "cutover_book"
    assert 切["指纹"] == 现行
    assert 切["拒模糊回刷"] is True
    对账 = 栏号解析.齐套对账()
    assert 对账["齐套"] is True
    assert 对账["精确命中"] == 2
    assert 对账["未解析"] == 0
    assert homonym.active_read_ref() == "cutover_book"
    assert homonym.reject_refresh() is True
    assert homonym.cutover_fp() == 现行
    assert homonym.cutover_fp() not in ("", "stale-fp")
    assert homonym.truth_flag() == "解析已亮"
    # 目录灯随之实绿
    assert 目录.homonym_齐套灯()["齐套"] is True


def test_改名产生新包_旧指纹行被对账抓红():
    _造重名两站()
    包1 = 栏号解析.封包()
    装载.装一批(夹具.读取("重名站样例"))
    栏号解析.切流()
    # 改名瞬间：物化包换版，新指纹与缓冲行钉住的旧指纹不一致
    包2 = 栏号解析.改站名("站-同名乙", "重名监测站·改")
    assert 包2["指纹"] != 包1["指纹"]
    对账 = 栏号解析.齐套对账()
    assert 对账["齐套"] is False
    assert 对账["未解析"] >= 1
    # 旧包仍可回读，历史行能对上旧版指纹
    历史 = 栏号解析.历史包列表()
    assert 包1["版本"] in [p["版本"] for p in 历史]
    assert 栏号解析.按包解析(包1["版本"], "站-同名乙") == 目录.栏规()["当前栏号"]
