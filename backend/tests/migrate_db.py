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
    # P1 风险项人工处置状态
    # 注意：SQLAlchemy 的 SQLEnum 默认按枚举「name」（大写）落库，
    # 因此这里必须写 'PENDING' 而不是 value 'pending'，否则读回时会 LookupError。
    ("risk_items", "status",
     "ALTER TABLE risk_items ADD COLUMN status ENUM('PENDING','CONFIRMED','IGNORED','TODO') "
     "NOT NULL DEFAULT 'PENDING'"),
    ("risk_items", "handled_at", "ALTER TABLE risk_items ADD COLUMN handled_at DATETIME NULL"),
    # 异步审查：失败原因回流给前端
    ("reviews", "error_message", "ALTER TABLE reviews ADD COLUMN error_message TEXT NULL"),
    # 合同版本（同一份合同反复修改后重新上传）
    ("contracts", "version", "ALTER TABLE contracts ADD COLUMN version INT NOT NULL DEFAULT 1"),
    ("contracts", "root_contract_id", "ALTER TABLE contracts ADD COLUMN root_contract_id INT NULL"),
    ("contracts", "parent_contract_id", "ALTER TABLE contracts ADD COLUMN parent_contract_id INT NULL"),
    # 审查模板 + 报告定稿
    ("reviews", "template_id", "ALTER TABLE reviews ADD COLUMN template_id INT NULL"),
    ("reviews", "template_name", "ALTER TABLE reviews ADD COLUMN template_name VARCHAR(128) NULL"),
    ("reviews", "finalized_at", "ALTER TABLE reviews ADD COLUMN finalized_at DATETIME NULL"),
    ("reviews", "finalized_by", "ALTER TABLE reviews ADD COLUMN finalized_by INT NULL"),
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


def enum_has_value(cur, database: str, table: str, column: str, value: str) -> bool:
    """判断 ENUM 列是否已包含某个取值（用于给已有 ENUM 追加成员）"""
    cur.execute(
        """
        SELECT COLUMN_TYPE FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (database, table, column),
    )
    row = cur.fetchone()
    return bool(row) and f"'{value}'" in (row[0] or "")


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

            # reviews.status 需要追加 RUNNING（异步审查进行中）；同样按枚举 name 落库
            if enum_has_value(cur, s.MYSQL_DATABASE, "reviews", "status", "RUNNING"):
                print("[skip] reviews.status already has 'RUNNING'")
            else:
                cur.execute(
                    "ALTER TABLE reviews MODIFY COLUMN status "
                    "ENUM('RUNNING','DONE','FAILED') NOT NULL DEFAULT 'DONE'"
                )
                print("[ok]   reviews.status extended with 'RUNNING'")
        conn.commit()
    finally:
        conn.close()
    print("[done] migrations applied")


if __name__ == "__main__":
    main()
