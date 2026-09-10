"""
SQLite 连接与 schema 初始化。
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.infrastructure.persistence.storage_names import DEFAULT_DATABASE_PATH


BUSY_TIMEOUT_MS = 5000

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS app_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        task_name TEXT NOT NULL,
        enabled INTEGER NOT NULL,
        keyword TEXT NOT NULL,
        description TEXT,
        analyze_images INTEGER NOT NULL,
        max_pages INTEGER NOT NULL,
        personal_only INTEGER NOT NULL,
        min_price TEXT,
        max_price TEXT,
        cron TEXT,
        ai_prompt_base_file TEXT NOT NULL,
        ai_prompt_criteria_file TEXT NOT NULL,
        account_state_file TEXT,
        account_strategy TEXT NOT NULL,
        free_shipping INTEGER NOT NULL,
        new_publish_option TEXT,
        region TEXT,
        decision_mode TEXT NOT NULL,
        keyword_rules_json TEXT NOT NULL,
        is_running INTEGER NOT NULL,
        blacklist_keywords_json TEXT NOT NULL DEFAULT '[]',
        execution_status TEXT NOT NULL DEFAULT 'idle',
        ai_title_screening INTEGER,
        notify_enabled INTEGER,
        ai_analysis_concurrency INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS result_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        result_filename TEXT NOT NULL,
        keyword TEXT NOT NULL,
        task_name TEXT NOT NULL,
        crawl_time TEXT NOT NULL,
        publish_time TEXT,
        price REAL,
        price_display TEXT,
        item_id TEXT,
        title TEXT,
        link TEXT,
        link_unique_key TEXT NOT NULL,
        seller_nickname TEXT,
        is_recommended INTEGER NOT NULL,
        analysis_source TEXT,
        keyword_hit_count INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        raw_json TEXT NOT NULL,
        UNIQUE(result_filename, link_unique_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword_slug TEXT NOT NULL,
        keyword TEXT NOT NULL,
        task_name TEXT NOT NULL,
        snapshot_time TEXT NOT NULL,
        snapshot_day TEXT NOT NULL,
        run_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        title TEXT,
        price REAL NOT NULL,
        price_display TEXT,
        tags_json TEXT NOT NULL,
        region TEXT,
        seller TEXT,
        publish_time TEXT,
        link TEXT,
        UNIQUE(keyword_slug, run_id, item_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS global_blacklist_rules (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        blacklist_keywords_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notified_items (
        item_key TEXT PRIMARY KEY,
        notified_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_analysis_cache (
        cache_key TEXT PRIMARY KEY,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_inflight_calls (
        call_id TEXT PRIMARY KEY,
        started_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tasks_name ON tasks(task_name)",
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_crawl
    ON result_items(result_filename, crawl_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_publish
    ON result_items(result_filename, publish_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_price
    ON result_items(result_filename, price DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_results_filename_recommended
    ON result_items(result_filename, is_recommended, analysis_source, crawl_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_time
    ON price_snapshots(keyword_slug, snapshot_time DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_keyword_item_time
    ON price_snapshots(keyword_slug, item_id, snapshot_time DESC)
    """,
)


def get_database_path() -> str:
    return os.getenv("APP_DATABASE_FILE", DEFAULT_DATABASE_PATH)


def _prepare_database_file(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")


def init_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    _migrate_result_items_status(conn)
    _migrate_tasks_blacklist_keywords(conn)
    _migrate_tasks_execution_status(conn)
    _migrate_tasks_title_screening(conn)
    _migrate_tasks_notify_enabled(conn)
    _migrate_tasks_ai_analysis_concurrency(conn)
    conn.commit()


def _migrate_tasks_execution_status(conn: sqlite3.Connection) -> None:
    """为 tasks 表添加 execution_status 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_execution_status'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "execution_status" not in cols:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN execution_status TEXT NOT NULL DEFAULT 'idle'"
        )
    # 清洗早期把枚举 str()（如 'ExecutionStatus.IDLE'）写入的列值
    conn.execute(
        "UPDATE tasks SET execution_status = 'idle' "
        "WHERE execution_status NOT IN ('idle', 'queued', 'running')"
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:tasks_execution_status', 'done')"
    )


def _migrate_tasks_title_screening(conn: sqlite3.Connection) -> None:
    """为 tasks 表添加 ai_title_screening 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_title_screening'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "ai_title_screening" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN ai_title_screening INTEGER")
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:tasks_title_screening', 'done')"
    )


def _migrate_tasks_notify_enabled(conn: sqlite3.Connection) -> None:
    """为 tasks 表添加 notify_enabled 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_notify_enabled'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "notify_enabled" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN notify_enabled INTEGER")
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:tasks_notify_enabled', 'done')"
    )


def _migrate_tasks_ai_analysis_concurrency(conn: sqlite3.Connection) -> None:
    """为 tasks 表添加 ai_analysis_concurrency 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_ai_analysis_concurrency'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "ai_analysis_concurrency" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN ai_analysis_concurrency INTEGER DEFAULT 1")
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:tasks_ai_analysis_concurrency', 'done')"
    )


def _migrate_result_items_status(conn: sqlite3.Connection) -> None:
    """为 result_items 表添加 status 列（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:result_items_status'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(result_items)").fetchall()]
    if "status" not in cols:
        conn.execute(
            "ALTER TABLE result_items ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
        )
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:result_items_status', 'done')"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_results_filename_status_crawl"
        " ON result_items(result_filename, status, crawl_time DESC)"
    )


def _migrate_tasks_blacklist_keywords(conn: sqlite3.Connection) -> None:
    """为每个任务加入独立黑名单，替换旧的按结果文件事后过滤的黑名单规则（仅执行一次）。"""
    row = conn.execute(
        "SELECT value FROM app_metadata WHERE key = 'migration:tasks_blacklist_keywords'"
    ).fetchone()
    if row is not None:
        return
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "blacklist_keywords_json" not in cols:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN blacklist_keywords_json TEXT NOT NULL DEFAULT '[]'"
        )
    conn.execute("DROP TABLE IF EXISTS result_blacklist_rules")
    conn.execute(
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES ('migration:tasks_blacklist_keywords', 'done')"
    )


@contextmanager
def sqlite_connection(
    db_path: str | None = None,
) -> Iterator[sqlite3.Connection]:
    path = db_path or get_database_path()
    _prepare_database_file(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        _apply_pragmas(conn)
        yield conn
    finally:
        conn.close()
