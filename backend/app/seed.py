from datetime import datetime, timezone
from app.db import 连接

建表 = """
CREATE TABLE IF NOT EXISTS 栏规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 站点源 (
  源键 TEXT PRIMARY KEY,
  名称 TEXT NOT NULL,
  介质 TEXT NOT NULL DEFAULT '大气',
  区域 TEXT NOT NULL DEFAULT '',
  说明 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 观测报文 (
  报文编号 TEXT PRIMARY KEY,
  站点键 TEXT NOT NULL,
  指标键 TEXT NOT NULL,
  读数 REAL NOT NULL,
  观测时 TEXT NOT NULL,
  处理时 TEXT NOT NULL,
  命运 TEXT NOT NULL DEFAULT '已装载',
  批次编号 TEXT NOT NULL DEFAULT '',
  解析指纹 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 入栏缓冲 (
  报文编号 TEXT PRIMARY KEY,
  站点键 TEXT NOT NULL,
  指标键 TEXT NOT NULL,
  读数 REAL NOT NULL,
  观测时 TEXT NOT NULL,
  栏号 TEXT NOT NULL,
  命运 TEXT NOT NULL DEFAULT '在栏',
  入栏时 TEXT NOT NULL,
  解析指纹 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 站点汇总账 (
  汇总编号 TEXT PRIMARY KEY,
  栏号 TEXT NOT NULL,
  站点键 TEXT NOT NULL,
  指标键 TEXT NOT NULL,
  报文数 INTEGER NOT NULL,
  均值 REAL NOT NULL,
  物化时 TEXT NOT NULL,
  命运 TEXT NOT NULL DEFAULT '已汇总',
  解析指纹 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 坏点匣 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  报文编号 TEXT NOT NULL,
  站点键 TEXT NOT NULL,
  原因 TEXT NOT NULL,
  读数 REAL NOT NULL,
  观测时 TEXT NOT NULL,
  入匣时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 栏贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  在栏笔数 INTEGER NOT NULL,
  汇总报文数 INTEGER NOT NULL,
  坏点笔数 INTEGER NOT NULL,
  是否对齐 INTEGER NOT NULL,
  说明 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  入流 INTEGER NOT NULL DEFAULT 0,
  入栏 INTEGER NOT NULL DEFAULT 0,
  坏点 INTEGER NOT NULL DEFAULT 0,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 探栏元 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 结栏批次 (
  编号 TEXT PRIMARY KEY,
  栏号 TEXT NOT NULL,
  时刻 TEXT NOT NULL,
  汇总数 INTEGER NOT NULL DEFAULT 0,
  报告 TEXT NOT NULL DEFAULT '{}'
);
"""


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 初始化库() -> None:
    # seed homonym display chip

    conn = 连接()
    conn.executescript(建表)
    _seed_homonym_chip(conn)
    if conn.execute("SELECT COUNT(*) AS c FROM 栏规").fetchone()["c"] == 0:
        for k, v in {
            "当前栏号": "B-demo",
            "PM25上限": "75",
            "PM25下限": "0",
            "标定偏移上限": "5",
            "栏策略": "按站点指标汇总均值",
        }.items():
            conn.execute("INSERT INTO 栏规(键,值) VALUES (?,?)", (k, v))
    if conn.execute("SELECT COUNT(*) AS c FROM 站点源").fetchone()["c"] == 0:
        for row in [
            ("站-河东", "河东大气站", "大气", "城区", "示范站"),
            ("站-湖西", "湖西水质站", "水质", "湖区", "示范站"),
            ("站-北岭", "北岭大气站", "大气", "近郊", "示范站"),
            ("站-江口", "江口大气站", "大气", "河口", "示范站"),
            ("站-林场", "林场微站", "大气", "林区", "示范站"),
            ("站-同名甲", "重名监测站", "大气", "城区", "重名站甲"),
            ("站-同名乙", "重名监测站", "大气", "近郊", "重名站乙"),
        ]:
            conn.execute(
                "INSERT INTO 站点源(源键,名称,介质,区域,说明) VALUES (?,?,?,?,?)",
                row,
            )
    conn.commit()
    conn.close()
    _迁移加解析指纹()
    _封首版解析包()


def _迁移加解析指纹() -> None:
    """老库补列：CREATE TABLE IF NOT EXISTS 不会改既有表结构。"""
    conn = 连接()
    try:
        既有 = {r["name"] for r in conn.execute("PRAGMA table_info(观测报文)").fetchall()}
        for 表 in ("观测报文", "入栏缓冲", "站点汇总账"):
            列 = {r["name"] for r in conn.execute(f"PRAGMA table_info({表})").fetchall()}
            if "解析指纹" not in 列:
                conn.execute(f"ALTER TABLE {表} ADD COLUMN 解析指纹 TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def _封首版解析包() -> None:
    from app.services import 栏号解析
    conn = 连接()
    try:
        栏号解析._ensure(conn)
        if 栏号解析.当前版本(conn) == 0:
            conn.commit()
    finally:
        conn.close()
    # 封包自开连接，避免事务嵌套
    if 栏号解析.当前版本() == 0:
        栏号解析.封包(备注="首版站键精确包")



def _seed_homonym_chip(conn) -> None:
    conn.execute(
        "INSERT INTO 探栏元(键,值) VALUES (?,?) ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
        ("homonym_panel_chip", "解析已亮"),
    )
    conn.execute(
        "INSERT INTO 探栏元(键,值) VALUES (?,?) ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
        ("homonym_truth", "重名串栏"),
    )
    conn.execute(
        "INSERT INTO 探栏元(键,值) VALUES (?,?) ON CONFLICT(键) DO UPDATE SET 值=excluded.值",
        ("homonym_active_read", "old_track"),
    )
