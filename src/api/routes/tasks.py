"""
任务管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from datetime import datetime
import os
import aiofiles
from src.api.dependencies import (
    get_process_service,
    get_scheduler_service,
    get_task_generation_service,
    get_task_service,
)
from src.services.task_service import TaskService
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService
from src.services.task_generation_service import TaskGenerationService
from src.services.task_generation_runner import (
    build_task_create,
    run_ai_generation_job,
)
from src.services.task_payloads import serialize_task, serialize_tasks
from src.domain.models.task import (
    TaskBatchUpdate,
    TaskBatchUpdateRequest,
    TaskCreate,
    TaskGenerateRequest,
    TaskUpdate,
)
from src.prompt_utils import generate_criteria
from src.utils import resolve_task_log_path
from src.services.account_strategy_service import normalize_account_strategy
from src.infrastructure.persistence.storage_names import build_result_filename
from src.services.price_history_service import delete_price_snapshots, rename_price_history
from src.services.result_storage_service import (
    delete_result_file_records,
    list_keywords_with_results_on_day,
    rename_result_records,
)
from src.api.routes import websocket
from src.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

async def _reload_scheduler_if_needed(
    task_service: TaskService,
    scheduler_service: SchedulerService,
):
    tasks = await task_service.get_all_tasks()
    await scheduler_service.reload_jobs(tasks)


def _has_keyword_rules(rules) -> bool:
    return bool(rules and len(rules) > 0)


def _validate_final_account_strategy(existing_task, task_update: TaskUpdate) -> None:
    account_state_file = (
        task_update.account_state_file
        if task_update.account_state_file is not None
        else existing_task.account_state_file
    )
    account_strategy = normalize_account_strategy(
        task_update.account_strategy,
        account_state_file,
    )
    task_update.account_strategy = account_strategy
    if account_strategy == "fixed" and not account_state_file:
        raise HTTPException(status_code=400, detail="固定账号模式下必须选择账号。")
@router.get("", response_model=List[dict])
async def get_tasks(
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """获取所有任务"""
    tasks = await service.get_all_tasks()
    return serialize_tasks(tasks, scheduler_service)
@router.get("/queue", response_model=dict)
async def get_task_queue(
    process_service: ProcessService = Depends(get_process_service),
):
    """获取串行执行队列状态（运行中 + 排队顺序）"""
    return process_service.get_queue_state()
@router.post("/start-all", response_model=dict)
async def start_all_tasks(
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """一键将全部已启用且空闲的任务加入串行执行队列"""
    tasks = [t for t in await task_service.get_all_tasks() if t.enabled]
    enqueued = 0
    skipped = 0
    for task in tasks:
        if task.is_running or process_service.is_queued(task.id):
            skipped += 1
            continue
        if await process_service.enqueue_task(task.id, task.task_name):
            enqueued += 1
        else:
            skipped += 1
    return {"message": f"已加入执行队列 {enqueued} 个任务", "enqueued": enqueued, "skipped": skipped}


@router.post("/start-without-data-today", response_model=dict)
async def start_tasks_without_data_today(
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """将今日尚无结果数据的已启用空闲任务加入执行队列。"""
    today = datetime.now().astimezone().date().isoformat()
    keywords_with_data = await list_keywords_with_results_on_day(today)
    tasks = await task_service.get_all_tasks()
    enqueued = 0
    skipped_with_data = 0
    skipped_unavailable = 0

    for task in tasks:
        normalized_keyword = (task.keyword or "").strip().lower()
        if normalized_keyword in keywords_with_data:
            skipped_with_data += 1
            continue
        if not task.enabled or task.is_running or process_service.is_queued(task.id):
            skipped_unavailable += 1
            continue
        if await process_service.enqueue_task(task.id, task.task_name):
            enqueued += 1
        else:
            skipped_unavailable += 1

    return {
        "message": f"已加入执行队列 {enqueued} 个今日无数据任务",
        "date": today,
        "enqueued": enqueued,
        "skipped_with_data": skipped_with_data,
        "skipped_unavailable": skipped_unavailable,
    }
@router.post("/stop-all", response_model=dict)
async def stop_all_tasks(
    process_service: ProcessService = Depends(get_process_service),
):
    """一键停止所有运行中的任务并清空执行队列"""
    await process_service.stop_all()
    return {"message": "已停止全部任务并清空执行队列"}
@router.get("/{task_id}", response_model=dict)
async def get_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """获取单个任务"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    return serialize_task(task, scheduler_service)
@router.post("/", response_model=dict)
async def create_task(
    task_create: TaskCreate,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """创建新任务"""
    task = await service.create_task(task_create)
    await _reload_scheduler_if_needed(service, scheduler_service)
    await websocket.broadcast_message("tasks_updated", {"task_id": task.id})
    return {"message": "任务创建成功", "task": serialize_task(task, scheduler_service)}
@router.post("/generate", response_model=dict)
async def generate_task(
    req: TaskGenerateRequest,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
    generation_service: TaskGenerationService = Depends(get_task_generation_service),
):
    """创建任务。AI模式会生成分析标准，关键词模式直接保存规则。"""
    logger.info(f"收到任务生成请求: {req.task_name}，模式: {req.decision_mode}")

    try:
        mode = req.decision_mode or "ai"
        if mode == "ai":
            job = await generation_service.create_job(req.task_name)
            generation_service.track(
                run_ai_generation_job(
                    job_id=job.job_id,
                    req=req,
                    task_service=service,
                    scheduler_service=scheduler_service,
                    generation_service=generation_service,
                )
            )
            return JSONResponse(
                status_code=202,
                content={
                    "message": "AI 任务生成已开始。",
                    "job": job.model_dump(mode="json"),
                },
            )

        task = await service.create_task(build_task_create(req, ""))
        await _reload_scheduler_if_needed(service, scheduler_service)
        await websocket.broadcast_message("tasks_updated", {"task_id": task.id})
        return {"message": "任务创建成功。", "task": serialize_task(task, scheduler_service)}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"AI任务生成API发生未知错误: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)
@router.get("/generate-jobs/{job_id}", response_model=dict)
async def get_task_generation_job(
    job_id: str,
    generation_service: TaskGenerationService = Depends(get_task_generation_service),
):
    """获取任务生成作业状态"""
    job = await generation_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务生成作业未找到")
    return {"job": job.model_dump(mode="json")}
@router.post("/batch-update", response_model=dict)
async def batch_update_tasks(
    payload: TaskBatchUpdateRequest,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """批量修改任务的指定字段。"""
    raw_ids = payload.task_ids
    update_payload = payload.updates.model_dump(exclude_unset=True)
    # notify_enabled / ai_title_screening / max_pages 在 Task 上是必填字段，
    # null 视作「不修改」；new_publish_option 是 Optional[str]，null 表示「清空」。
    for non_optional_field in ("notify_enabled", "ai_title_screening", "max_pages"):
        if (
            non_optional_field in update_payload
            and update_payload[non_optional_field] is None
        ):
            update_payload.pop(non_optional_field)
    if not update_payload:
        raise HTTPException(status_code=400, detail="至少需要指定一个修改字段。")

    succeeded: List[int] = []
    failed: List[dict] = []
    seen: set[int] = set()
    for tid in raw_ids:
        if tid in seen:
            continue
        seen.add(tid)
        try:
            existing = await service.get_task(tid)
            if not existing:
                failed.append({"task_id": tid, "reason": "任务不存在"})
                continue
            task_update = TaskUpdate(**update_payload)
            await service.update_task(tid, task_update)
            succeeded.append(tid)
        except Exception as e:
            failed.append({"task_id": tid, "reason": str(e)})

    if succeeded:
        await _reload_scheduler_if_needed(service, scheduler_service)
        await websocket.broadcast_message(
            "tasks_updated", {"task_ids": succeeded}
        )

    return {
        "message": f"已批量修改 {len(succeeded)} 个任务，{len(failed)} 个失败",
        "succeeded": succeeded,
        "failed": failed,
    }


@router.patch("/{task_id}", response_model=dict)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    service: TaskService = Depends(get_task_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """更新任务"""
    try:
        existing_task = await service.get_task(task_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail="任务未找到")
        _validate_final_account_strategy(existing_task, task_update)

        current_mode = getattr(existing_task, "decision_mode", "ai") or "ai"
        target_mode = task_update.decision_mode or current_mode
        description_changed = (
            task_update.description is not None
            and task_update.description != existing_task.description
        )
        switched_to_ai = current_mode != "ai" and target_mode == "ai"

        if target_mode == "keyword":
            final_rules = (
                task_update.keyword_rules
                if task_update.keyword_rules is not None
                else getattr(existing_task, "keyword_rules", [])
            )
            if not _has_keyword_rules(final_rules):
                raise HTTPException(status_code=400, detail="关键词模式下至少需要一个关键词。")
        if target_mode == "ai" and (description_changed or switched_to_ai):
            logger.info(f"检测到任务 {task_id} 需要刷新 AI 标准文件，开始重新生成...")
            try:
                description_for_ai = (
                    task_update.description
                    if task_update.description is not None
                    else existing_task.description
                )
                if not str(description_for_ai or "").strip():
                    raise HTTPException(status_code=400, detail="AI 模式下详细需求不能为空。")
                safe_keyword = "".join(
                    c for c in existing_task.keyword.lower().replace(' ', '_')
                    if c.isalnum() or c in "_-"
                ).rstrip()
                output_filename = f"prompts/{safe_keyword}_criteria.txt"
                logger.info(f"目标文件路径: {output_filename}")
                logger.info("开始调用 AI 生成新的分析标准...")
                generated_criteria = await generate_criteria(
                    user_description=description_for_ai,
                    reference_file_path="prompts/macbook_criteria.txt"
                )
                if not generated_criteria or len(generated_criteria.strip()) == 0:
                    logger.warning("AI 返回的内容为空")
                    raise HTTPException(status_code=500, detail="AI 未能生成分析标准，返回内容为空。")
                logger.info(f"保存新的分析标准到: {output_filename}")
                os.makedirs("prompts", exist_ok=True)
                async with aiofiles.open(output_filename, 'w', encoding='utf-8') as f:
                    await f.write(generated_criteria)
                logger.info("新的分析标准已保存")
                task_update.ai_prompt_criteria_file = output_filename
                logger.info(f"已更新 ai_prompt_criteria_file 字段为: {output_filename}")
            except HTTPException:
                raise
            except Exception as e:
                error_msg = f"重新生成 criteria 文件时出错: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise HTTPException(status_code=500, detail=error_msg)
        old_keyword = existing_task.keyword
        old_task_name = existing_task.task_name

        task = await service.update_task(task_id, task_update)
        await _reload_scheduler_if_needed(service, scheduler_service)

        if (old_keyword or "").strip() != (task.keyword or "").strip() or old_task_name != task.task_name:
            try:
                old_filename = build_result_filename(old_keyword)
                new_filename = build_result_filename(task.keyword)
                migrated = await rename_result_records(
                    old_filename, new_filename, task.keyword, task.task_name
                )
                if not migrated:
                    logger.warning(
                        f"结果迁移被跳过：关键词 '{task.keyword}' 对应的结果文件已被其他任务占用。"
                    )
                rename_price_history(old_keyword, task.keyword, task.task_name)
            except Exception as e:
                logger.error(f"迁移任务结果/价格历史时出错: {e}")

        await websocket.broadcast_message("tasks_updated", {"task_id": task.id})
        return {"message": "任务更新成功", "task": serialize_task(task, scheduler_service)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
@router.delete("/{task_id}", response_model=dict)
async def delete_task(
    task_id: int,
    service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
    scheduler_service: SchedulerService = Depends(get_scheduler_service),
):
    """删除任务"""
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")

    await process_service.stop_task(task_id)
    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务未找到")
    await _reload_scheduler_if_needed(service, scheduler_service)
    try:
        keyword = (task.keyword or "").strip()
        if keyword:
            remaining_tasks = await service.get_all_tasks()
            keyword_still_in_use = any(
                (remaining_task.keyword or "").strip() == keyword
                for remaining_task in remaining_tasks
            )
            if not keyword_still_in_use:
                await delete_result_file_records(build_result_filename(keyword))
                delete_price_snapshots(keyword)
    except Exception as e:
        logger.error(f"删除任务结果文件时出错: {e}")

    try:
        log_file_path = resolve_task_log_path(task_id, task.task_name)
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
    except Exception as e:
        logger.error(f"删除任务日志文件时出错: {e}")
    await websocket.broadcast_message("tasks_updated", {"task_id": task_id})
    return {"message": "任务删除成功"}
@router.post("/start/{task_id}", response_model=dict)
async def start_task(
    task_id: int,
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """启动单个任务（加入串行执行队列）"""
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    if not task.enabled:
        raise HTTPException(status_code=400, detail="任务已被禁用，无法启动")
    if task.is_running:
        raise HTTPException(status_code=400, detail="任务已在运行中")
    if process_service.is_queued(task_id):
        raise HTTPException(status_code=400, detail="任务已在执行队列中")
    success = await process_service.enqueue_task(task_id, task.task_name)
    if not success:
        raise HTTPException(status_code=500, detail="任务入队失败")
    return {"message": f"任务 '{task.task_name}' 已加入执行队列"}
@router.post("/stop/{task_id}", response_model=dict)
async def stop_task(
    task_id: int,
    task_service: TaskService = Depends(get_task_service),
    process_service: ProcessService = Depends(get_process_service),
):
    """停止单个任务（或将其从执行队列中移除）"""
    task = await task_service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务未找到")
    await process_service.stop_task(task_id)
    return {"message": f"任务ID {task_id} 已发送停止信号"}
