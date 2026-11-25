"""列表与栏规。"""
from __future__ import annotations
from app.db import 连接, 写事务
from app.services import 校验


def 栏规() -> dict:
    conn = 连接()
    try:
        return {r["键"]: r["值"] for r in conn.execute("SELECT 键,值 FROM 栏规").fetchall()}
    finally:
        conn.close()


def 改栏规(体: dict) -> dict:
    错 = 校验.校验栏规补丁(体 or {})
    if 错:
        return {"错误": 校验.摘要错误(错), "栏规": 栏规()}
    conn = 连接()
    try:
        with 写事务(conn):
            for k, v in (体 or {}).items():
                conn.execute(
                    "INSERT INTO 栏规(键,值) VALUES (?,?) ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
                    (str(k), str(v)),
                )
        return 栏规()
    finally:
        conn.close()


def 站点列表() -> list[dict]:
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 站点源 ORDER BY 源键").fetchall()]
    finally:
        conn.close()


def 报文列表(限制: int = 200) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM 观测报文 ORDER BY 观测时 DESC LIMIT ?", (限制,)
            ).fetchall()
        ]
    finally:
        conn.close()


def 缓冲列表(命运: str | None = None) -> list[dict]:
    conn = 连接()
    try:
        if 命运:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM 入栏缓冲 WHERE 命运=? ORDER BY 观测时", (命运,)
                ).fetchall()
            ]
        return [dict(r) for r in conn.execute("SELECT * FROM 入栏缓冲 ORDER BY 观测时").fetchall()]
    finally:
        conn.close()


def 汇总列表(限制: int = 200) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM 站点汇总账 ORDER BY 物化时 DESC LIMIT ?", (限制,)
            ).fetchall()
        ]
    finally:
        conn.close()


def 坏点列表(限制: int = 200) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM 坏点匣 ORDER BY 编号 DESC LIMIT ?", (限制,)
            ).fetchall()
        ]
    finally:
        conn.close()


def 贯验列表(限制: int = 50) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM 栏贯验 ORDER BY 编号 DESC LIMIT ?", (限制,)
            ).fetchall()
        ]
    finally:
        conn.close()


def 概览():
    # homonym panel inject
    pass


def __概览_orig():
    raise RuntimeError


def 概览_broken_placeholder():
    return {}


def 概览() -> dict:
    conn = 连接()
    try:
        return {
            "观测报文": conn.execute("SELECT COUNT(*) AS c FROM 观测报文").fetchone()["c"],
            "在栏": conn.execute("SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 命运='在栏'").fetchone()["c"],
            "站点汇总": conn.execute("SELECT COUNT(*) AS c FROM 站点汇总账").fetchone()["c"],
            "坏点": conn.execute("SELECT COUNT(*) AS c FROM 坏点匣").fetchone()["c"],
            "栏规": 栏规(),
        }
    finally:
        conn.close()


def 装载批次列表(限制: int = 50) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT 编号,时刻,入流,入栏,坏点 FROM 装载批次 ORDER BY 时刻 DESC LIMIT ?",
                (限制,),
            ).fetchall()
        ]
    finally:
        conn.close()


def 结栏批次列表(限制: int = 50) -> list[dict]:
    conn = 连接()
    try:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT 编号,栏号,时刻,汇总数 FROM 结栏批次 ORDER BY 时刻 DESC LIMIT ?",
                (限制,),
            ).fetchall()
        ]
    finally:
        conn.close()


def 站点查(源键: str) -> dict | None:
    conn = 连接()
    try:
        r = conn.execute("SELECT * FROM 站点源 WHERE 源键=?", (源键,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()



def homonym_齐套灯() -> dict:
    """齐套只认站键精确物化包对账实值，面板芯片再绿也不折算。"""
    from app.services import 栏号解析
    对账 = 栏号解析.齐套对账()
    return {
        "标题": 对账.get("标题"),
        "芯片": 对账.get("解析真源"),
        "真相": "解析已亮" if 对账.get("齐套") else "重名串栏",
        "齐套": 对账.get("齐套"),
        "对齐实值": 对账.get("齐套"),
        "panel_pack_mismatch": not 对账.get("齐套"),
        "精确命中": 对账.get("精确命中"),
        "模糊命中": 对账.get("模糊命中"),
        "未解析": 对账.get("未解析"),
        "串栏": 对账.get("串栏"),
        "读轨": 对账.get("读轨"),
    }


def 解析真源卡() -> dict:
    """栏规列表/报文流/入栏缓冲/站点汇总账四页共用的解析真源。"""
    from app.services import 栏号解析
    return 栏号解析.真源卡()
