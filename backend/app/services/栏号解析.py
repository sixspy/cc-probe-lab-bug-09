"""栏号解析真源：站键精确物化包。

工程形态择定：**物化包**。
- 封包把 ``站点键 -> 栏号`` 的映射固化为不可变版本，带 sha256 指纹；
- 装载写库与页侧回读都走同一份站键解析，重名站（同名不同源键）各落各栏；
- 站名模糊解析的结果只准进只读归档，``按站名模糊回刷`` 永远拒；
- 改名只动站点名称、不动源键，改名即换版，旧批可按旧指纹回放，绝不双解析串栏。
"""
from __future__ import annotations

import contextlib
import hashlib
import json

from app.db import 连接, 写事务
from app.seed import 此刻
from app.services import 目录

_SLUG = "homonym"
真源名 = "站键精确"
_OK = "解析已亮"
_BAD = "重名串栏"
_OLD = "old_track"
_CUTOVER = "cutover_book"


def _ensure(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS 解析包(
          版本 INTEGER PRIMARY KEY,
          指纹 TEXT NOT NULL,
          时刻 TEXT NOT NULL,
          备注 TEXT NOT NULL DEFAULT '',
          状态 TEXT NOT NULL DEFAULT '现行'
        );
        CREATE TABLE IF NOT EXISTS 站点栏映射(
          版本 INTEGER NOT NULL,
          站点键 TEXT NOT NULL,
          站点名称 TEXT NOT NULL,
          栏号 TEXT NOT NULL,
          PRIMARY KEY(版本, 站点键)
        );
        CREATE TABLE IF NOT EXISTS 模糊归档(
          编号 INTEGER PRIMARY KEY AUTOINCREMENT,
          时刻 TEXT NOT NULL,
          站名 TEXT NOT NULL,
          候选栏 TEXT NOT NULL,
          模糊落点 TEXT NOT NULL
        );
        """
    )


def _meta_get(conn, key: str, default: str = "") -> str:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS 探栏元(键 TEXT PRIMARY KEY, 值 TEXT NOT NULL)"
    )
    r = conn.execute("SELECT 值 FROM 探栏元 WHERE 键=?", (key,)).fetchone()
    return r["值"] if r else default


def _meta_set(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO 探栏元(键,值) VALUES (?,?) "
        "ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
        (key, value),
    )


def _算指纹(版本: int, 行: list[dict]) -> str:
    体 = json.dumps(
        [[r["站点键"], r["栏号"], r["站点名称"]] for r in sorted(行, key=lambda x: x["站点键"])],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(f"{版本}|{体}".encode("utf-8")).hexdigest()[:16]


def 当前版本(conn=None) -> int:
    关 = conn is None
    conn = conn or 连接()
    try:
        return int(_meta_get(conn, f"{_SLUG}_pack_version", "0") or "0")
    finally:
        if 关:
            conn.close()


def 当前指纹(conn=None) -> str:
    关 = conn is None
    conn = conn or 连接()
    try:
        版本 = 当前版本(conn)
        if 版本 == 0:
            return ""
        r = conn.execute("SELECT 指纹 FROM 解析包 WHERE 版本=?", (版本,)).fetchone()
        return r["指纹"] if r else ""
    finally:
        if 关:
            conn.close()


def 封包(备注: str = "", conn=None) -> dict:
    """按现行站点源封一版站键→栏号物化包。

    未显式绑定的站点全部落到栏规当前栏号；上一版的显式（非默认）绑定随版续存。
    """
    关 = conn is None
    conn = conn or 连接()
    try:
        _ensure(conn)
        with contextlib.ExitStack() as 栈:
            if 关:
                栈.enter_context(写事务(conn))
            规 = 目录.栏规()
            默认栏 = 规.get("当前栏号", "B-demo")
            站点 = 目录.站点列表()
            旧版 = 当前版本(conn)
            旧绑定: dict[str, str] = {}
            if 旧版:
                for r in conn.execute(
                    "SELECT 站点键,栏号 FROM 站点栏映射 WHERE 版本=?", (旧版,)
                ).fetchall():
                    if r["栏号"] != 默认栏:
                        旧绑定[r["站点键"]] = r["栏号"]
            新版 = 旧版 + 1
            行 = [
                {
                    "站点键": s["源键"],
                    "站点名称": s["名称"],
                    "栏号": 旧绑定.get(s["源键"], 默认栏),
                }
                for s in 站点
            ]
            指纹 = _算指纹(新版, 行)
            时刻 = 此刻()
            conn.execute(
                "INSERT INTO 解析包(版本,指纹,时刻,备注,状态) VALUES (?,?,?,?,?)",
                (新版, 指纹, 时刻, 备注 or "", "现行"),
            )
            if 旧版:
                conn.execute("UPDATE 解析包 SET 状态='历史' WHERE 版本=?", (旧版,))
            conn.executemany(
                "INSERT INTO 站点栏映射(版本,站点键,站点名称,栏号) VALUES (?,?,?,?)",
                [(新版, r["站点键"], r["站点名称"], r["栏号"]) for r in 行],
            )
            _meta_set(conn, f"{_SLUG}_pack_version", str(新版))
            _meta_set(conn, f"{_SLUG}_cutover_fp", 指纹)
        return {
            "版本": 新版,
            "指纹": 指纹,
            "时刻": 时刻,
            "备注": 备注 or "",
            "解析真源": 真源名,
            "站点数": len(行),
        }
    finally:
        if 关:
            conn.close()


def _取现行(conn) -> tuple[int, str]:
    版本 = 当前版本(conn)
    if 版本 == 0:
        包 = 封包(conn=conn)
        return 包["版本"], 包["指纹"]
    r = conn.execute("SELECT 指纹 FROM 解析包 WHERE 版本=?", (版本,)).fetchone()
    return 版本, (r["指纹"] if r else "")


def 绑定站点栏(站点键: str, 栏号: str) -> dict:
    """显式绑定只认源键；物化包不可变，绑定即换版封新包。

    改名后同名站也不会被带走；旧版指纹保留，旧批可按旧包回放。
    """
    conn = 连接()
    try:
        _ensure(conn)
        with 写事务(conn):
            旧版 = 当前版本(conn)
            if 旧版 == 0:
                raise RuntimeError("尚无物化包，先封包")
            旧行 = [dict(r) for r in conn.execute(
                "SELECT 站点键,站点名称,栏号 FROM 站点栏映射 WHERE 版本=?", (旧版,)
            ).fetchall()]
            if not any(r["站点键"] == 站点键 for r in 旧行):
                raise KeyError(f"未知站点键: {站点键}")
            名称 = next(r["站点名称"] for r in 旧行 if r["站点键"] == 站点键)
            新版 = 旧版 + 1
            新行 = [
                {"站点键": r["站点键"], "站点名称": r["站点名称"],
                 "栏号": 栏号 if r["站点键"] == 站点键 else r["栏号"]}
                for r in 旧行
            ]
            新指纹 = _算指纹(新版, 新行)
            时刻 = 此刻()
            conn.execute("UPDATE 解析包 SET 状态='历史' WHERE 版本=?", (旧版,))
            conn.execute(
                "INSERT INTO 解析包(版本,指纹,时刻,备注,状态) VALUES (?,?,?,?,?)",
                (新版, 新指纹, 时刻, f"绑定:{站点键}->{栏号}", "现行"),
            )
            conn.executemany(
                "INSERT INTO 站点栏映射(版本,站点键,站点名称,栏号) VALUES (?,?,?,?)",
                [(新版, r["站点键"], r["站点名称"], r["栏号"]) for r in 新行],
            )
            _meta_set(conn, f"{_SLUG}_pack_version", str(新版))
            _meta_set(conn, f"{_SLUG}_cutover_fp", 新指纹)
        return {"版本": 新版, "指纹": 新指纹, "站点键": 站点键,
                "站点名称": 名称, "栏号": 栏号}
    finally:
        conn.close()


def 改站名(源键: str, 新名称: str) -> dict:
    """改名不动源键；换版封包，旧版保留供旧指纹回放。"""
    conn = 连接()
    try:
        with 写事务(conn):
            if not conn.execute("SELECT 1 FROM 站点源 WHERE 源键=?", (源键,)).fetchone():
                raise KeyError(f"未知站点键: {源键}")
            conn.execute("UPDATE 站点源 SET 名称=? WHERE 源键=?", (新名称, 源键))
    finally:
        conn.close()
    return 封包(备注=f"改名:{源键}")


def 验指纹(指纹: str, conn=None) -> int:
    """未知指纹直接拒，禁止静默回退站名模糊。"""
    if not 指纹:
        raise KeyError("空解析指纹")
    关 = conn is None
    conn = conn or 连接()
    try:
        _ensure(conn)
        r = conn.execute("SELECT 版本 FROM 解析包 WHERE 指纹=?", (指纹,)).fetchone()
        if not r:
            raise KeyError(f"未知解析指纹: {指纹}")
        return r["版本"]
    finally:
        if 关:
            conn.close()


def 按包解析(版本: int, 站点键: str, conn=None) -> str:
    关 = conn is None
    conn = conn or 连接()
    try:
        r = conn.execute(
            "SELECT 栏号 FROM 站点栏映射 WHERE 版本=? AND 站点键=?",
            (版本, 站点键),
        ).fetchone()
        if not r:
            raise KeyError(f"包版本{版本}无站点键: {站点键}")
        return r["栏号"]
    finally:
        if 关:
            conn.close()


def 解析(站点键: str, 指纹: str | None = None) -> tuple[str, str]:
    """写读同一站键解析入口：返回(栏号, 实际指纹)。"""
    conn = 连接()
    try:
        _ensure(conn)
        if 指纹 is None:
            版本, 实际指纹 = _取现行(conn)
        else:
            版本 = 验指纹(指纹, conn)
            实际指纹 = 指纹
        return 按包解析(版本, 站点键, conn), 实际指纹
    finally:
        conn.close()


def 记模糊归档(站名: str, 候选栏: list[str], 模糊落点: str) -> dict:
    """站名模糊命中只准落只读归档，永不参与精确齐套。"""
    conn = 连接()
    try:
        _ensure(conn)
        with 写事务(conn):
            时刻 = 此刻()
            cur = conn.execute(
                "INSERT INTO 模糊归档(时刻,站名,候选栏,模糊落点) VALUES (?,?,?,?)",
                (时刻, 站名, json.dumps(候选栏, ensure_ascii=False), 模糊落点),
            )
        return {"编号": cur.lastrowid, "时刻": 时刻, "站名": 站名,
                "候选栏": 候选栏, "模糊落点": 模糊落点, "来源": "模糊归档"}
    finally:
        conn.close()


def 按站名模糊回刷(站名到栏: dict) -> dict:
    """硬拒：物化包不接受任何站名模糊回刷。"""
    raise ValueError("站键精确物化包拒站名模糊回刷，模糊结果仅可记只读归档")


def 模糊归档列表() -> list[dict]:
    conn = 连接()
    try:
        _ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM 模糊归档 ORDER BY 编号 DESC"
        ).fetchall()]
    finally:
        conn.close()


def 站点栏映射(版本: int | None = None) -> list[dict]:
    conn = 连接()
    try:
        _ensure(conn)
        版本 = 当前版本(conn) if 版本 is None else 版本
        return [dict(r) for r in conn.execute(
            "SELECT 版本,站点键,站点名称,栏号 FROM 站点栏映射 WHERE 版本=? ORDER BY 站点键",
            (版本,),
        ).fetchall()]
    finally:
        conn.close()


def 历史包列表() -> list[dict]:
    conn = 连接()
    try:
        _ensure(conn)
        return [dict(r) for r in conn.execute(
            "SELECT 版本,指纹,时刻,备注,状态 FROM 解析包 ORDER BY 版本 DESC"
        ).fetchall()]
    finally:
        conn.close()


def 切流() -> dict:
    """读轨切到物化账册：锁指纹、拒模糊回刷，灯与真相对齐。"""
    conn = 连接()
    try:
        _ensure(conn)
        with 写事务(conn):
            版本, 指纹 = _取现行(conn)
            if not 指纹:
                raise RuntimeError("无可切流的物化包")
            _meta_set(conn, f"{_SLUG}_active_read", _CUTOVER)
            _meta_set(conn, f"{_SLUG}_reject_refresh", "1")
            _meta_set(conn, f"{_SLUG}_cutover_fp", 指纹)
            _meta_set(conn, f"{_SLUG}_truth", _OK)
            _meta_set(conn, f"{_SLUG}_panel_chip", _OK)
        return {"读轨": _CUTOVER, "版本": 版本, "指纹": 指纹, "拒模糊回刷": True,
                "解析真源": 真源名}
    finally:
        conn.close()


def 齐套对账() -> dict:
    """齐套只认站键精确物化包；模糊归档单列，绝不折算精确。"""
    from app.services import homonym
    conn = 连接()
    try:
        _ensure(conn)
        版本 = 当前版本(conn)
        现指纹 = 当前指纹(conn)
        指纹到版本 = {r["指纹"]: r["版本"] for r in conn.execute(
            "SELECT 版本,指纹 FROM 解析包"
        ).fetchall()}
        精确 = 未解析 = 串栏 = 0
        明细: list[dict] = []
        for r in conn.execute("SELECT * FROM 入栏缓冲 ORDER BY 报文编号").fetchall():
            d = dict(r)
            fp = d.get("解析指纹") or ""
            落 = {"报文编号": d["报文编号"], "站点键": d["站点键"],
                  "栏号": d["栏号"], "解析指纹": fp}
            包版本 = 指纹到版本.get(fp)
            if 包版本 is None:
                未解析 += 1
                落["来源"] = "指纹漂移"
            else:
                期望 = conn.execute(
                    "SELECT 栏号 FROM 站点栏映射 WHERE 版本=? AND 站点键=?",
                    (包版本, d["站点键"]),
                ).fetchone()
                if 期望 is None:
                    未解析 += 1
                    落["来源"] = "未解析"
                elif 期望["栏号"] != d["栏号"]:
                    串栏 += 1
                    落["来源"] = "串栏"
                elif fp == 现指纹:
                    精确 += 1
                    落["来源"] = "精确"
                else:
                    未解析 += 1
                    落["来源"] = "指纹漂移"
            明细.append(落)
        模糊数 = conn.execute("SELECT COUNT(*) AS c FROM 模糊归档").fetchone()["c"]
        读轨 = homonym.active_read_ref()
        拒刷 = homonym.reject_refresh()
        锁指纹 = homonym.cutover_fp()
        齐 = (
            读轨 == _CUTOVER
            and 拒刷
            and 锁指纹 not in ("", "stale-fp")
            and 未解析 == 0
            and 串栏 == 0
        )
        return {
            "标题": "栏号解析",
            "解析真源": 真源名,
            "齐套": 齐,
            "精确命中": 精确,
            "模糊命中": 模糊数,
            "未解析": 未解析,
            "串栏": 串栏,
            "读轨": 读轨,
            "拒模糊回刷": 拒刷,
            "当前版本": 版本,
            "当前指纹": 现指纹,
            "锁定指纹": 锁指纹,
            "明细": 明细,
        }
    finally:
        conn.close()


def 真源卡() -> dict:
    """供四个策略页回读的解析真源卡。"""
    from app.services import homonym
    conn = 连接()
    try:
        _ensure(conn)
        版本, 指纹 = _取现行(conn)
        return {
            "解析真源": 真源名,
            "版本": 版本,
            "指纹": 指纹,
            "读轨": homonym.active_read_ref(),
            "拒模糊回刷": homonym.reject_refresh(),
            "齐套": 齐套对账()["齐套"],
            "映射条数": conn.execute(
                "SELECT COUNT(*) AS c FROM 站点栏映射 WHERE 版本=?", (版本,)
            ).fetchone()["c"],
            "模糊归档数": conn.execute(
                "SELECT COUNT(*) AS c FROM 模糊归档"
            ).fetchone()["c"],
        }
    finally:
        conn.close()
