"""
Dashboard 聚合服务
统一汇总任务、结果文件和最近活动，供首页概览使用。
"""
from __future__ import annotations

import asyncio
from typing import Any

from src.domain.models.task import Task
from src.services.dashboard_payloads import (
    build_empty_summary,
    build_task_state_activities,
    normalize_text,
    serialize_timestamp,
    sort_key_by_activity_time,
    sort_key_by_latest_time,
    summarize_result_file,
)
from src.services.price_history_service import (
    collect_keyword_to_ai_ids,
    find_declining_dip_tasks,
)
from src.services.result_storage_service import list_result_filenames

MAX_RECENT_ACTIVITIES = 8


def _build_summary_metrics(tasks: list[Task], summary_list: list[dict[str, Any]], last_updated_at: Any) -> dict[str, Any]:
    return {
        "enabled_tasks": sum(1 for task in tasks if task.enabled),
        "running_tasks": sum(1 for task in tasks if task.is_running),
        "queued_tasks": sum(
            1
            for task in tasks
            if getattr(task, "execution_status", "idle") == "queued"
        ),
        "result_files": sum(1 for item in summary_list if item.get("filename")),
        "scanned_items": sum(int(item["total_items"]) for item in summary_list),
        "recommended_items": sum(int(item["recommended_items"]) for item in summary_list),
        "ai_recommended_items": sum(int(item["ai_recommended_items"]) for item in summary_list),
        "keyword_recommended_items": sum(int(item["keyword_recommended_items"]) for item in summary_list),
        "last_updated_at": serialize_timestamp(last_updated_at),
    }


async def build_dashboard_snapshot(tasks: list[Task]) -> dict[str, Any]:
    task_lookup = {normalize_text(task.keyword): task for task in tasks}
    task_summaries: dict[str, dict[str, Any]] = {
        task.task_name: build_empty_summary(task) for task in tasks
    }
    recent_activities = build_task_state_activities(tasks)
    latest_updated_at = None

    for filename in await list_result_filenames():
        summary, activities, file_latest_time = await summarize_result_file(filename, task_lookup)
        if summary:
            task_summaries[summary["task_name"]] = summary
        recent_activities.extend(activities)
        if file_latest_time and (latest_updated_at is None or file_latest_time > latest_updated_at):
            latest_updated_at = file_latest_time

    summary_list = sorted(task_summaries.values(), key=sort_key_by_latest_time, reverse=True)
    focus_file = next((item["filename"] for item in summary_list if item.get("filename")), None)
    declining_dip_tasks = await _collect_declining_dip_tasks(task_lookup)
    return {
        "summary": _build_summary_metrics(tasks, summary_list, latest_updated_at),
        "task_summaries": summary_list,
        "recent_activities": sorted(
            recent_activities,
            key=sort_key_by_activity_time,
            reverse=True,
        )[:MAX_RECENT_ACTIVITIES],
        "declining_dip_tasks": declining_dip_tasks,
        "focus_file": focus_file,
    }


async def _collect_declining_dip_tasks(task_lookup: dict[str, "Task"]) -> list[dict]:
    """收集按任务聚合的「持续下跌可抄底」数据，并补充 task_id / task_name。"""
    keyword_to_ai_ids = await collect_keyword_to_ai_ids()
    if not keyword_to_ai_ids:
        return []
    entries = await asyncio.to_thread(find_declining_dip_tasks, keyword_to_ai_ids)
    enriched: list[dict] = []
    for entry in entries:
        keyword = entry.get("keyword") or ""
        task = task_lookup.get(normalize_text(keyword)) if keyword else None
        if task is not None:
            entry["task_id"] = task.id
            entry["task_name"] = task.task_name
        enriched.append(entry)
    return enriched
