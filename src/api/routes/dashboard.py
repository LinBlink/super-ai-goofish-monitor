"""
Dashboard 概览路由
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_task_service
from src.services.dashboard_service import (
    build_dashboard_snapshot,
    iter_dashboard_snapshot_events,
)
from src.services.task_service import TaskService


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    task_service: TaskService = Depends(get_task_service),
):
    try:
        tasks = await task_service.get_all_tasks()
        return await build_dashboard_snapshot(tasks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"加载 dashboard 数据失败: {exc}")


@router.get("/summary/stream")
async def stream_dashboard_summary(
    task_service: TaskService = Depends(get_task_service),
):
    tasks = await task_service.get_all_tasks()

    async def generate():
        try:
            async for event in iter_dashboard_snapshot_events(tasks):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps(
                {"type": "error", "message": f"加载 dashboard 数据失败: {exc}"},
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
