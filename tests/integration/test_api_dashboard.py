import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.routes import dashboard
from src.domain.models.task import TaskCreate
from src.infrastructure.persistence.sqlite_task_repository import SqliteTaskRepository
from src.services.task_service import TaskService


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def test_dashboard_summary_aggregates_tasks_and_results(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    jsonl_dir = tmp_path / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)

    repository = SqliteTaskRepository(
        db_path=str(tmp_path / "app.sqlite3"),
        legacy_config_file=None,
    )
    task_service = TaskService(repository)
    app = FastAPI()
    app.include_router(dashboard.router)
    app.dependency_overrides[deps.get_task_service] = lambda: task_service

    client = TestClient(app)

    first = TaskCreate(
      task_name="Apple Watch 任务",
      keyword="apple watch",
      description="只关注价格合适且成色好的 Apple Watch。",
      max_pages=3,
      personal_only=True,
    )
    second = TaskCreate(
      task_name="iPad 任务",
      keyword="ipad pro",
      description="关注 2024 款 iPad Pro。",
      max_pages=2,
      personal_only=True,
    )

    created_first = task_service.create_task(first)
    created_second = task_service.create_task(second)
    import asyncio
    created_first = asyncio.run(created_first)
    created_second = asyncio.run(created_second)
    asyncio.run(task_service.update_task_status(created_second.id, True))

    records = [
        {
            "爬取时间": "2026-03-10T10:00:00",
            "搜索关键字": "apple watch",
            "任务名称": "Apple Watch 任务",
            "商品信息": {
                "商品ID": "watch-1",
                "商品标题": "Apple Watch S10",
                "商品链接": "https://www.goofish.com/item?id=watch-1",
                "当前售价": "¥1800",
            },
            "ai_analysis": {
                "analysis_source": "ai",
                "is_recommended": True,
                "reason": "价格低于均价",
            },
        },
        {
            "爬取时间": "2026-03-10T11:00:00",
            "搜索关键字": "apple watch",
            "任务名称": "Apple Watch 任务",
            "商品信息": {
                "商品ID": "watch-2",
                "商品标题": "Apple Watch S10 蜂窝版",
                "商品链接": "https://www.goofish.com/item?id=watch-2",
                "当前售价": "¥2100",
            },
            "ai_analysis": {
                "analysis_source": "keyword",
                "is_recommended": False,
                "reason": "未命中规则",
            },
        },
    ]
    _write_jsonl(jsonl_dir / "apple_watch_full_data.jsonl", records)

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["enabled_tasks"] == 2
    assert payload["summary"]["running_tasks"] == 1
    assert payload["summary"]["result_files"] == 1
    assert payload["summary"]["scanned_items"] == 2
    assert payload["summary"]["recommended_items"] == 1
    assert payload["summary"]["ai_recommended_items"] == 1
    assert payload["summary"]["keyword_recommended_items"] == 0
    assert payload["focus_file"] == "apple_watch_full_data.jsonl"

    watch_summary = next(
        item for item in payload["task_summaries"] if item["task_name"] == "Apple Watch 任务"
    )
    assert watch_summary["filename"] == "apple_watch_full_data.jsonl"
    assert watch_summary["total_items"] == 2
    assert watch_summary["latest_recommended_title"] == "Apple Watch S10"

    ipad_summary = next(
        item for item in payload["task_summaries"] if item["task_name"] == "iPad 任务"
    )
    assert ipad_summary["filename"] is None
    assert ipad_summary["is_running"] is True

    statuses = {item["status"] for item in payload["recent_activities"]}
    assert "AI 推荐" in statuses
    assert "结果已更新" in statuses
    assert "运行中" in statuses

    # 没有历史价格快照时，均价字段应为空而不是报错。
    assert watch_summary["history_avg_price"] is None
    assert ipad_summary["history_avg_price"] is None


def test_dashboard_summary_stream_emits_cards_before_complete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository = SqliteTaskRepository(
        db_path=str(tmp_path / "app.sqlite3"),
        legacy_config_file=None,
    )
    task_service = TaskService(repository)
    app = FastAPI()
    app.include_router(dashboard.router)
    app.dependency_overrides[deps.get_task_service] = lambda: task_service

    import asyncio

    asyncio.run(
        task_service.create_task(
            TaskCreate(
                task_name="流式任务",
                keyword="streaming",
                description="验证概览卡片逐条返回。",
                max_pages=1,
                personal_only=True,
            )
        )
    )

    events = [
        json.loads(line)
        for line in TestClient(app).get("/api/dashboard/summary/stream").text.splitlines()
        if line
    ]

    assert events[0]["type"] == "task_summary"
    assert events[0]["data"]["task_name"] == "流式任务"
    assert events[-1]["type"] == "complete"
    assert events[-1]["data"]["task_summaries"][0]["task_name"] == "流式任务"


def test_dashboard_summary_includes_latest_history_avg_price(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    jsonl_dir = tmp_path / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)

    repository = SqliteTaskRepository(
        db_path=str(tmp_path / "app.sqlite3"),
        legacy_config_file=None,
    )
    task_service = TaskService(repository)
    app = FastAPI()
    app.include_router(dashboard.router)
    app.dependency_overrides[deps.get_task_service] = lambda: task_service

    client = TestClient(app)

    task = TaskCreate(
        task_name="索尼 A7R4 相机",
        keyword="索尼 A7R4 相机",
        description="只关注95新以上的机身。",
        max_pages=3,
        personal_only=True,
    )
    import asyncio

    created = asyncio.run(task_service.create_task(task))

    record = {
        "爬取时间": "2026-03-10T10:00:00",
        "搜索关键字": created.keyword,
        "任务名称": created.task_name,
        "商品信息": {
            "商品ID": "cam-1",
            "商品标题": "索尼 A7R4 95新",
            "商品链接": "https://www.goofish.com/item?id=cam-1",
            "当前售价": "¥12000",
        },
        "ai_analysis": {
            "analysis_source": "ai",
            "is_recommended": True,
            "reason": "价格低于市场均价",
        },
    }
    _write_jsonl(jsonl_dir / "sony_a7r4_full_data.jsonl", [record])

    from src.services.price_history_service import record_market_snapshots

    # 价格趋势只统计 AI 推荐的商品价格，因此上面的记录必须是 is_recommended=True。
    record_market_snapshots(
        keyword=created.keyword,
        task_name=created.task_name,
        items=[record["商品信息"]],
        run_id="run-1",
        snapshot_time="2026-03-10T10:00:00",
    )

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()

    summary = next(
        item for item in payload["task_summaries"] if item["task_name"] == "索尼 A7R4 相机"
    )
    assert summary["history_avg_price"] == 12000
    assert summary["history_sample_count"] == 1
    assert summary["history_snapshot_at"] == "2026-03-10T10:00:00"
    assert summary["history_daily_trend"] == [
        {
            "day": "2026-03-10",
            "sample_count": 1,
            "avg_price": 12000,
            "median_price": 12000,
            "min_price": 12000,
            "max_price": 12000,
        }
    ]
