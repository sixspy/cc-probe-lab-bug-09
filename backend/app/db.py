import contextlib
import os
import sqlite3
import time
from pathlib import Path

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
库路径 = 数据目录 / "探栏.db"


def 连接() -> sqlite3.Connection:
    数据目录.mkdir(parents=True, exist_ok=True)
    # autocommit：每条语句立即生效，读连接不会因 deferred 事务持有旧快照，
    # 改名换版后其它线程/请求立刻可见，避免并发改名下的双解析。
    c = sqlite3.connect(库路径, isolation_level=None, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 30000")
    return c


def 提交重试(conn, 次数: int = 5, 等待: float = 0.05):
    """并发写争用（改名/封包与装载并行）下指数退避重试。"""
    延迟 = 等待
    for i in range(次数):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < 次数 - 1:
                time.sleep(延迟)
                延迟 *= 2
                continue
            raise


@contextlib.contextmanager
def 写事务(conn):
    """autocommit 模式下显式开事务；锁争用退避重试，异常回滚。"""
    延迟 = 0.05
    for i in range(5):
        try:
            conn.execute("BEGIN IMMEDIATE")
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < 4:
                time.sleep(延迟)
                延迟 *= 2
                continue
            raise
    try:
        yield
        提交重试(conn)
    except Exception:
        conn.rollback()
        raise
