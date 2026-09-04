import asyncio
import time


def test_rename_task_migrates_results_and_price_history(
    api_client, api_context, sample_task_payload, monkeypatch, tmp_path
):
    # 结果/价格历史走的是独立的全局 sqlite_connection()（跟 api_context 的任务库路径无关），
    # 必须单独用 APP_DATABASE_FILE 隔离，否则会污染仓库根目录下的真实 data/app.sqlite3。
    monkeypatch.setenv("APP_DATABASE_FILE", str(tmp_path / "results.sqlite3"))

    from src.infrastructure.persistence.storage_names import build_result_filename
    from src.services.price_history_service import (
        load_price_snapshots,
        record_market_snapshots,
    )
    from src.services.result_storage_service import (
        query_result_records,
        save_result_record,
    )

    response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert response.status_code == 200

    old_keyword = sample_task_payload["keyword"]
    old_task_name = sample_task_payload["task_name"]
    old_filename = build_result_filename(old_keyword)

    item = {
        "商品ID": "cam-1",
        "商品标题": "Sony A7M4 95新",
        "商品链接": "https://www.goofish.com/item?id=cam-1",
        "当前售价": "¥9000",
    }
    record = {
        "爬取时间": "2026-03-10T10:00:00",
        "搜索关键字": old_keyword,
        "任务名称": old_task_name,
        "商品信息": item,
        "ai_analysis": {"analysis_source": "keyword", "is_recommended": False},
    }
    asyncio.run(save_result_record(record, old_keyword))
    record_market_snapshots(
        keyword=old_keyword,
        task_name=old_task_name,
        items=[item],
        run_id="run-1",
        snapshot_time="2026-03-10T10:00:00",
    )

    new_keyword = "sony a7m4 pro"
    new_task_name = "索尼 A7M4（已改名）"
    new_filename = build_result_filename(new_keyword)

    response = api_client.patch(
        "/api/tasks/0",
        json={"keyword": new_keyword, "task_name": new_task_name},
    )
    assert response.status_code == 200

    # 旧 filename/keyword 下不应再残留结果或价格快照……
    old_total, _ = asyncio.run(query_result_records(
        old_filename,
        ai_recommended_only=False,
        keyword_recommended_only=False,
        sort_by="crawl_time",
        sort_order="desc",
        page=1,
        limit=20,
    ))
    assert old_total == 0
    assert load_price_snapshots(old_keyword) == []

    # ……而是迁移到了新 filename/keyword 下，且 task_name 字段也一并更新。
    new_total, new_items = asyncio.run(query_result_records(
        new_filename,
        ai_recommended_only=False,
        keyword_recommended_only=False,
        sort_by="crawl_time",
        sort_order="desc",
        page=1,
        limit=20,
    ))
    assert new_total == 1
    assert new_items[0]["商品信息"]["商品ID"] == "cam-1"

    new_snapshots = load_price_snapshots(new_keyword)
    assert len(new_snapshots) == 1
    assert new_snapshots[0]["task_name"] == new_task_name


def test_create_list_update_delete_task(api_client, api_context, sample_task_payload):
    response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert response.status_code == 200
    created = response.json()["task"]
    assert created["task_name"] == sample_task_payload["task_name"]
    assert created["analyze_images"] is True
    assert created["next_run_at"] == "2026-03-19T08:15:00+08:00"

    response = api_client.get("/api/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["keyword"] == sample_task_payload["keyword"]
    assert tasks[0]["analyze_images"] is True
    assert tasks[0]["next_run_at"] == "2026-03-19T08:15:00+08:00"

    response = api_client.patch("/api/tasks/0", json={"enabled": False, "analyze_images": False})
    assert response.status_code == 200
    updated = response.json()["task"]
    assert updated["enabled"] is False
    assert updated["analyze_images"] is False
    assert updated["next_run_at"] is None

    response = api_client.delete("/api/tasks/0")
    assert response.status_code == 200

    response = api_client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_batch_update_supports_ai_title_screening(api_client, sample_task_payload):
    assert api_client.post("/api/tasks/", json=sample_task_payload).status_code == 200

    response = api_client.post(
        "/api/tasks/batch-update",
        json={"task_ids": [0], "updates": {"ai_title_screening": False}},
    )

    assert response.status_code == 200
    assert response.json()["succeeded"] == [0]
    task = api_client.get("/api/tasks/0").json()
    assert task["ai_title_screening"] is False


def test_start_stop_task_updates_status(api_client, api_context, sample_task_payload):
    response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert response.status_code == 200

    response = api_client.post("/api/tasks/start/0")
    assert response.status_code == 200

    response = api_client.get("/api/tasks/0")
    assert response.status_code == 200
    assert response.json()["is_running"] is True

    response = api_client.post("/api/tasks/stop/0")
    assert response.status_code == 200

    response = api_client.get("/api/tasks/0")
    assert response.status_code == 200
    assert response.json()["is_running"] is False

    process_service = api_context["process_service"]
    assert process_service.started == [(0, sample_task_payload["task_name"])]
    assert process_service.stopped == [0]


def test_start_tasks_without_data_today_only_starts_missing_enabled_tasks(
    api_client, api_context, sample_task_payload, monkeypatch
):
    payload_with_data = {**sample_task_payload, "task_name": "已有数据", "keyword": "has-data"}
    payload_missing = {**sample_task_payload, "task_name": "今日无数据", "keyword": "missing-data"}
    payload_disabled = {
        **sample_task_payload,
        "task_name": "已禁用且无数据",
        "keyword": "disabled-missing",
        "enabled": False,
    }
    for payload in (payload_with_data, payload_missing, payload_disabled):
        assert api_client.post("/api/tasks/", json=payload).status_code == 200

    async def fake_keywords_with_results(_day: str) -> set[str]:
        return {"has-data"}

    monkeypatch.setattr(
        "src.api.routes.tasks.list_keywords_with_results_on_day",
        fake_keywords_with_results,
    )
    process_service = api_context["process_service"]
    monkeypatch.setattr(process_service, "is_queued", lambda _task_id: False, raising=False)

    async def fake_enqueue(task_id: int, task_name: str) -> bool:
        return await process_service.start_task(task_id, task_name)

    monkeypatch.setattr(process_service, "enqueue_task", fake_enqueue, raising=False)

    response = api_client.post("/api/tasks/start-without-data-today")
    assert response.status_code == 200
    payload = response.json()
    assert payload["enqueued"] == 1
    assert payload["skipped_with_data"] == 1
    assert payload["skipped_unavailable"] == 1
    assert process_service.started == [(1, "今日无数据")]


def test_generate_keyword_mode_task_without_ai_criteria(api_client):
    payload = {
        "task_name": "A7M4 关键词筛选",
        "keyword": "sony a7m4",
        "description": "",
        "decision_mode": "keyword",
        "keyword_rules": ["a7m4", "验货宝"],
        "max_pages": 2,
        "personal_only": True,
    }

    response = api_client.post("/api/tasks/generate", json=payload)
    assert response.status_code == 200
    created = response.json()["task"]
    assert created["decision_mode"] == "keyword"
    assert created["ai_prompt_criteria_file"] == ""
    assert created["keyword_rules"] == ["a7m4", "验货宝"]


def test_generate_ai_task_returns_job_and_completes_async(api_client, api_context, monkeypatch):
    payload = {
        "task_name": "Apple Watch S10",
        "keyword": "apple watch s10",
        "description": "只看国行蜂窝版，电池健康高于 95%，拒绝维修机。",
        "analyze_images": False,
        "decision_mode": "ai",
        "max_pages": 2,
        "personal_only": True,
    }

    async def fake_generate_criteria(*_args, **_kwargs):
        await asyncio.sleep(0.05)
        return "[V6.3 核心升级]\\nApple Watch criteria"

    monkeypatch.setattr(
        "src.services.task_generation_runner.generate_criteria",
        fake_generate_criteria,
    )

    response = api_client.post("/api/tasks/generate", json=payload)

    assert response.status_code == 202
    job = response.json()["job"]
    assert isinstance(job["job_id"], str)
    assert job["status"] in {"queued", "running"}
    assert job["task"] is None

    status_response = api_client.get(f"/api/tasks/generate-jobs/{job['job_id']}")
    assert status_response.status_code == 200

    for _ in range(50):
        status_response = api_client.get(f"/api/tasks/generate-jobs/{job['job_id']}")
        latest_job = status_response.json()["job"]
        if latest_job["status"] == "completed":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("任务生成作业未在预期时间内完成")

    assert latest_job["task"]["task_name"] == payload["task_name"]
    assert latest_job["task"]["ai_prompt_criteria_file"].endswith("_criteria.txt")
    assert latest_job["task"]["analyze_images"] is False
    assert api_context["scheduler_service"].reload_calls == 1


def test_create_task_accepts_cron_alias(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["cron"] = "@daily"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 200
    assert response.json()["task"]["cron"] == "0 0 * * *"


def test_create_task_rejects_fixed_account_strategy_without_state_file(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["account_strategy"] = "fixed"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 422


def test_create_task_accepts_rotate_account_strategy(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["account_strategy"] = "rotate"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["account_strategy"] == "rotate"


def test_update_task_accepts_six_field_cron_expression(api_client, sample_task_payload):
    create_response = api_client.post("/api/tasks/", json=sample_task_payload)
    assert create_response.status_code == 200

    response = api_client.patch("/api/tasks/0", json={"cron": "0 0 8 * * *"})

    assert response.status_code == 200

    task_response = api_client.get("/api/tasks/0")
    assert task_response.status_code == 200
    assert task_response.json()["cron"] == "0 0 8 * * *"


def test_create_task_rejects_invalid_cron_expression(api_client, sample_task_payload):
    payload = dict(sample_task_payload)
    payload["cron"] = "every day at 8"

    response = api_client.post("/api/tasks/", json=payload)

    assert response.status_code == 422


def test_delete_task_stops_runtime_and_reindexes_process_state(
    api_client,
    api_context,
    sample_task_payload,
):
    second_payload = dict(sample_task_payload)
    second_payload["task_name"] = "Sony A7CR"
    second_payload["keyword"] = "sony a7cr"
    second_payload["ai_prompt_criteria_file"] = "prompts/sony_a7cr_criteria.txt"

    assert api_client.post("/api/tasks/", json=sample_task_payload).status_code == 200
    assert api_client.post("/api/tasks/", json=second_payload).status_code == 200
    assert api_client.post("/api/tasks/start/0").status_code == 200

    response = api_client.delete("/api/tasks/0")

    assert response.status_code == 200
    process_service = api_context["process_service"]
    assert process_service.stopped == [0]
