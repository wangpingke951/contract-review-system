"""幂等的轻量数据库迁移 —— 为已存在的表补齐后加的字段

背景：项目用 `Base.metadata.create_all()` 建表，SQLAlchemy 只创建缺失的**表**，
不会修改已存在表的**列定义**。因此只要表已经建过，之后在模型上新增的字段
都不会自动生效，插入时会报 Unknown column。

用法（在 backend 目录下执行）：
    python tests/migrate_db.py

脚本可重复执行：已存在的列会跳过。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import backend_on_path  # noqa: E402

backend_on_path()

import pymysql  # noqa: E402
from app.config import get_settings  # noqa: E402


# (表名, 列名, DDL)
MIGRATIONS: list[tuple[str, str, str]] = [
    ("contracts", "parse_error", "ALTER TABLE contracts ADD COLUMN parse_error TEXT NULL"),
]


def column_exists(cur, database: str, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (database, table, column),
    )
    return cur.fetchone()[0] > 0


def main() -> None:
    s = get_settings()
    conn = pymysql.connect(
        host=s.MYSQL_HOST, port=s.MYSQL_PORT, user=s.MYSQL_USER,
        password=s.MYSQL_PASSWORD, database=s.MYSQL_DATABASE, charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            for table, column, ddl in MIGRATIONS:
                if column_exists(cur, s.MYSQL_DATABASE, table, column):
                    print(f"[skip] {table}.{column} already exists")
                else:
                    cur.execute(ddl)
                    print(f"[ok]   {table}.{column} added")
        conn.commit()
    finally:
        conn.close()
    print("[done] migrations applied")


if __name__ == "__main__":
    main()
