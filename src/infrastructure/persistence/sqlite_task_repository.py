"""
基于 SQLite 的任务仓储实现。
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Optional

from src.domain.models.task import Task
from src.domain.repositories.task_repository import TaskRepository
from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection


def _coerce_optional_bool(value, default: bool = False) -> Optional[bool]:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("", "null", "none", "undefined"):
        return default
    return text in {"1", "true", "yes", "y", "on"}


def _row_to_task(row) -> Task:
    payload = dict(row)
    payload["enabled"] = bool(payload["enabled"])
    payload["analyze_images"] = bool(payload["analyze_images"])
    payload["personal_only"] = bool(payload["personal_only"])
    payload["free_shipping"] = bool(payload["free_shipping"])
    payload["is_running"] = bool(payload["is_running"])
    payload["ai_title_screening"] = _coerce_optional_bool(payload.get("ai_title_screening"), default=True)
    payload["notify_enabled"] = _coerce_optional_bool(payload.get("notify_enabled"), default=True)
    raw_status = payload.get("execution_status") or "idle"
    payload["execution_status"] = raw_status if raw_status in ("idle", "queued", "running") else "idle"
    payload["keyword_rules"] = json.loads(payload.pop("keyword_rules_json") or "[]")
    payload["blacklist_keywords"] = json.loads(payload.pop("blacklist_keywords_json", None) or "[]")
    return Task(**payload)


def find_task_by_name_sync(task_name: str) -> Task | None:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE task_name = ? ORDER BY id ASC LIMIT 1",
            (task_name,),
        ).fetchone()
    return _row_to_task(row) if row else None


class SqliteTaskRepository(TaskRepository):
    """基于 SQLite 的任务仓储"""

    def __init__(
        self,
        db_path: str | None = None,
        legacy_config_file: str | None = "config.json",
    ):
        self.db_path = db_path
        self.legacy_config_file = legacy_config_file

    async def find_all(self) -> List[Task]:
        return await asyncio.to_thread(self._find_all_sync)

    async def find_by_id(self, task_id: int) -> Optional[Task]:
        return await asyncio.to_thread(self._find_by_id_sync, task_id)

    async def save(self, task: Task) -> Task:
        return await asyncio.to_thread(self._save_sync, task)

    async def delete(self, task_id: int) -> bool:
        return await asyncio.to_thread(self._delete_sync, task_id)

    def _find_all_sync(self) -> List[Task]:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
        return [_row_to_task(row) for row in rows]

    def _find_by_id_sync(self, task_id: int) -> Optional[Task]:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def _save_sync(self, task: Task) -> Task:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            task_id = task.id
            if task_id is None:
                task_id = self._next_task_id(conn)
            payload = self._task_values(task.model_copy(update={"id": task_id}))
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, task_name, enabled, keyword, description, analyze_images,
                    max_pages, personal_only, min_price, max_price, cron,
                    ai_prompt_base_file, ai_prompt_criteria_file, account_state_file,
                    account_strategy, free_shipping, new_publish_option, region,
                    decision_mode, keyword_rules_json, is_running, blacklist_keywords_json,
                    execution_status, ai_title_screening, notify_enabled,
                    ai_analysis_concurrency
                ) VALUES (
                    :id, :task_name, :enabled, :keyword, :description, :analyze_images,
                    :max_pages, :personal_only, :min_price, :max_price, :cron,
                    :ai_prompt_base_file, :ai_prompt_criteria_file, :account_state_file,
                    :account_strategy, :free_shipping, :new_publish_option, :region,
                    :decision_mode, :keyword_rules_json, :is_running, :blacklist_keywords_json,
                    :execution_status, :ai_title_screening, :notify_enabled,
                    :ai_analysis_concurrency
                )
                """,
                payload,
            )
            conn.commit()
        return task.model_copy(update={"id": task_id})

    def _delete_sync(self, task_id: int) -> bool:
        bootstrap_sqlite_storage(
            self.db_path,
            legacy_config_file=self.legacy_config_file,
        )
        with sqlite_connection(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return cursor.rowcount > 0

    def _next_task_id(self, conn) -> int:
        row = conn.execute("SELECT COALESCE(MAX(id), -1) AS max_id FROM tasks").fetchone()
        return int(row["max_id"]) + 1

    def _task_values(self, task: Task) -> dict:
        values = task.model_dump()
        values["enabled"] = int(task.enabled)
        values["analyze_images"] = int(task.analyze_images)
        values["personal_only"] = int(task.personal_only)
        values["free_shipping"] = int(task.free_shipping)
        values["is_running"] = int(task.is_running)
        values["ai_title_screening"] = (
            None if task.ai_title_screening is None else int(task.ai_title_screening)
        )
        values["notify_enabled"] = (
            None if task.notify_enabled is None else int(task.notify_enabled)
        )
        values["ai_analysis_concurrency"] = max(1, int(task.ai_analysis_concurrency or 1))
        exec_status = task.execution_status
        values["execution_status"] = getattr(exec_status, "value", exec_status)
        values["keyword_rules_json"] = json.dumps(task.keyword_rules or [], ensure_ascii=False)
        values["blacklist_keywords_json"] = json.dumps(task.blacklist_keywords or [], ensure_ascii=False)
        values.pop("keyword_rules", None)
        values.pop("blacklist_keywords", None)
        return values
