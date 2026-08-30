"""
设置管理路由
"""
import json
import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.dependencies import get_process_service, get_scheduler_service
from src.infrastructure.config.env_manager import env_manager
from src.infrastructure.config.settings import (
    AISettings,
    reload_settings,
    scraper_settings,
)
from src.services.ai_request_compat import (
    CHAT_COMPLETIONS_API_MODE,
    RESPONSES_API_MODE,
    build_ai_request_params,
    create_ai_response_sync,
    is_chat_completions_api_unsupported_error,
    is_responses_api_unsupported_error,
    model_requires_thinking_disabled,
)
from src.services.ai_response_parser import extract_ai_response_content
from src.services.notification_config_service import (
    NotificationSettingsValidationError,
    build_configured_channels,
    build_notification_settings_response,
    build_notification_status_flags,
    load_notification_settings,
    model_dump,
    prepare_notification_test_settings,
    prepare_notification_settings_update,
)
from src.services.notification_service import build_notification_service
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService
from src.services.result_storage_service import (
    load_global_blacklist_keywords,
    save_global_blacklist_keywords,
)


router = APIRouter(prefix="/api/settings", tags=["settings"])
AI_TEST_PROMPT = "Reply with OK only."
AI_TEST_MAX_OUTPUT_TOKENS = 1024


def _reload_env() -> None:
    load_dotenv(dotenv_path=env_manager.env_file, override=True)
    reload_settings()


def _env_bool(key: str, default: bool = False) -> bool:
    value = env_manager.get_value(key)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    value = env_manager.get_value(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_bool_value(value: bool) -> str:
    return "true" if value else "false"


class NotificationSettingsModel(BaseModel):
    """通知设置模型"""

    NTFY_TOPIC_URL: Optional[str] = None
    NTFY_ENABLED: Optional[bool] = None
    GOTIFY_URL: Optional[str] = None
    GOTIFY_TOKEN: Optional[str] = None
    GOTIFY_ENABLED: Optional[bool] = None
    BARK_URL: Optional[str] = None
    BARK_ENABLED: Optional[bool] = None
    WX_BOT_URL: Optional[str] = None
    WX_BOT_ENABLED: Optional[bool] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_API_BASE_URL: Optional[str] = None
    TELEGRAM_ENABLED: Optional[bool] = None
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_METHOD: Optional[str] = None
    WEBHOOK_HEADERS: Optional[str] = None
    WEBHOOK_CONTENT_TYPE: Optional[str] = None
    WEBHOOK_QUERY_PARAMETERS: Optional[str] = None
    WEBHOOK_BODY: Optional[str] = None
    WEBHOOK_ENABLED: Optional[bool] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_ADDRESS: Optional[str] = None
    SMTP_TO_ADDRESS: Optional[str] = None
    SMTP_USE_SSL: Optional[bool] = None
    EMAIL_ENABLED: Optional[bool] = None
    PCURL_TO_MOBILE: Optional[bool] = None


class NotificationTestRequest(BaseModel):
    """通知测试请求"""

    channel: Optional[str] = None
    settings: NotificationSettingsModel = Field(default_factory=NotificationSettingsModel)


class AIModelConfigModel(BaseModel):
    """单个 AI 模型配置（有序列表中的一项）。第一个为主模型，其余为兜底模型。"""

    api_key: Optional[str] = None
    base_url: str
    model_name: str
    enable_response_format: Optional[bool] = True
    proxy_url: Optional[str] = None


class AISettingsModel(BaseModel):
    """AI设置模型（支持多模型，第一个为主模型）"""

    models: List[AIModelConfigModel] = Field(default_factory=list)
    SKIP_AI_ANALYSIS: Optional[bool] = None


class GlobalBlacklistRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list)


class RotationSettingsModel(BaseModel):
    ACCOUNT_ROTATION_ENABLED: Optional[bool] = None
    ACCOUNT_ROTATION_MODE: Optional[str] = None
    ACCOUNT_ROTATION_RETRY_LIMIT: Optional[int] = None
    ACCOUNT_BLACKLIST_TTL: Optional[int] = None
    ACCOUNT_STATE_DIR: Optional[str] = None
    PROXY_ROTATION_ENABLED: Optional[bool] = None
    PROXY_ROTATION_MODE: Optional[str] = None
    PROXY_POOL: Optional[str] = None
    PROXY_ROTATION_RETRY_LIMIT: Optional[int] = None
    PROXY_BLACKLIST_TTL: Optional[int] = None


@router.get("/notifications")
async def get_notification_settings():
    return build_notification_settings_response(load_notification_settings())


@router.put("/notifications")
async def update_notification_settings(settings: NotificationSettingsModel):
    try:
        updates, deletions, merged_settings = prepare_notification_settings_update(
            model_dump(settings, exclude_unset=True),
            load_notification_settings(),
        )
    except NotificationSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    success = env_manager.apply_changes(updates=updates, deletions=deletions)
    if not success:
        raise HTTPException(status_code=500, detail="更新通知设置失败")

    _reload_env()
    return {
        "message": "通知设置已成功更新",
        "configured_channels": build_configured_channels(merged_settings),
    }


@router.post("/notifications/test")
async def test_notification_settings(payload: NotificationTestRequest):
    try:
        merged_settings = prepare_notification_test_settings(
            model_dump(payload.settings, exclude_unset=True),
            load_notification_settings(),
            channel=payload.channel,
        )
    except NotificationSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    service = build_notification_service(merged_settings)
    if not service.clients:
        if payload.channel:
            raise HTTPException(
                status_code=422,
                detail=f"渠道 {payload.channel} 未配置或不受支持",
            )
        raise HTTPException(status_code=422, detail="请至少配置一个可用的通知渠道")

    results = await service.send_test_notification()
    if payload.channel:
        if payload.channel not in results:
            raise HTTPException(
                status_code=422,
                detail=f"渠道 {payload.channel} 未配置或不受支持",
            )
        results = {payload.channel: results[payload.channel]}

    return {
        "message": "测试通知已执行",
        "results": results,
    }


@router.get("/rotation")
async def get_rotation_settings():
    return {
        "ACCOUNT_ROTATION_ENABLED": _env_bool("ACCOUNT_ROTATION_ENABLED", False),
        "ACCOUNT_ROTATION_MODE": env_manager.get_value("ACCOUNT_ROTATION_MODE", "per_task"),
        "ACCOUNT_ROTATION_RETRY_LIMIT": _env_int("ACCOUNT_ROTATION_RETRY_LIMIT", 2),
        "ACCOUNT_BLACKLIST_TTL": _env_int("ACCOUNT_BLACKLIST_TTL", 300),
        "ACCOUNT_STATE_DIR": env_manager.get_value("ACCOUNT_STATE_DIR", "state"),
        "PROXY_ROTATION_ENABLED": _env_bool("PROXY_ROTATION_ENABLED", False),
        "PROXY_ROTATION_MODE": env_manager.get_value("PROXY_ROTATION_MODE", "per_task"),
        "PROXY_POOL": env_manager.get_value("PROXY_POOL", ""),
        "PROXY_ROTATION_RETRY_LIMIT": _env_int("PROXY_ROTATION_RETRY_LIMIT", 2),
        "PROXY_BLACKLIST_TTL": _env_int("PROXY_BLACKLIST_TTL", 300),
    }


@router.put("/rotation")
async def update_rotation_settings(settings: RotationSettingsModel):
    updates = {}
    payload = model_dump(settings, exclude_unset=True)
    for key, value in payload.items():
        if isinstance(value, bool):
            updates[key] = _normalize_bool_value(value)
        else:
            updates[key] = str(value)
    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新轮换设置失败")
    _reload_env()
    return {"message": "轮换设置已成功更新"}


class BrowserSettingsModel(BaseModel):
    """浏览器相关设置"""

    USE_SYSTEM_CHROME: Optional[bool] = None


class SchedulerSettingsModel(BaseModel):
    """调度相关设置"""

    paused: Optional[bool] = None


@router.get("/browser")
async def get_browser_settings():
    return {
        "USE_SYSTEM_CHROME": _env_bool("USE_SYSTEM_CHROME", True),
    }


@router.put("/browser")
async def update_browser_settings(settings: BrowserSettingsModel):
    updates = {}
    payload = model_dump(settings, exclude_unset=True)
    for key, value in payload.items():
        if isinstance(value, bool):
            updates[key] = _normalize_bool_value(value)
        else:
            updates[key] = str(value)
    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新浏览器设置失败")
    _reload_env()
    return {"message": "浏览器设置已成功更新"}


class SchedulerSettingsResponse(BaseModel):
    paused: bool
    scheduler_running: bool


@router.get("/scheduler")
async def get_scheduler_settings(
    scheduler: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerSettingsResponse:
    return SchedulerSettingsResponse(
        paused=_env_bool("SCHEDULER_PAUSED", False),
        scheduler_running=scheduler.scheduler.running,
    )


@router.put("/scheduler")
async def update_scheduler_settings(
    settings: SchedulerSettingsModel,
    scheduler: SchedulerService = Depends(get_scheduler_service),
):
    if settings.paused is None:
        raise HTTPException(status_code=422, detail="缺少 paused 字段")

    success = env_manager.update_values(
        {"SCHEDULER_PAUSED": _normalize_bool_value(settings.paused)}
    )
    if not success:
        raise HTTPException(status_code=500, detail="更新调度设置失败")

    scheduler.set_paused(settings.paused)
    return {"message": "调度暂停状态已更新", "paused": settings.paused}


@router.get("/global-blacklist")
async def get_global_blacklist():
    keywords = await load_global_blacklist_keywords()
    return {"keywords": keywords}


@router.put("/global-blacklist")
async def put_global_blacklist(body: GlobalBlacklistRequest):
    keywords = await save_global_blacklist_keywords(body.keywords)
    return {"message": "全局黑名单已更新", "keywords": keywords}


@router.get("/status")
async def get_system_status(
    process_service: ProcessService = Depends(get_process_service),
):
    state_file = scraper_settings.state_file
    login_state_exists = os.path.exists(state_file)
    env_file_exists = os.path.exists(env_manager.env_file)
    ai_settings = AISettings()
    model_configs = ai_settings.models()
    primary_model = model_configs[0] if model_configs else {}
    openai_api_key = primary_model.get("api_key") or env_manager.get_value("OPENAI_API_KEY", "")
    openai_base_url = primary_model.get("base_url") or env_manager.get_value("OPENAI_BASE_URL", "")
    openai_model_name = primary_model.get("model_name") or env_manager.get_value("OPENAI_MODEL_NAME", "")
    notification_settings = load_notification_settings()
    running_task_ids = [
        task_id
        for task_id, process in process_service.processes.items()
        if process and process.returncode is None
    ]

    return {
        "ai_configured": ai_settings.is_configured(),
        "notification_configured": notification_settings.has_any_notification_enabled(),
        "headless_mode": scraper_settings.run_headless,
        "running_in_docker": scraper_settings.running_in_docker,
        "scraper_running": len(running_task_ids) > 0,
        "running_task_ids": running_task_ids,
        "login_state_file": {
            "exists": login_state_exists,
            "path": state_file,
        },
        "env_file": {
            "exists": env_file_exists,
            "openai_api_key_set": bool(openai_api_key),
            "openai_base_url_set": bool(openai_base_url),
            "openai_model_name_set": bool(openai_model_name),
            **build_notification_status_flags(notification_settings),
        },
        "configured_notification_channels": build_configured_channels(notification_settings),
    }


@router.get("/ai")
async def get_ai_settings():
    ai_settings = AISettings()
    models = []
    for cfg in ai_settings.models():
        models.append({
            # 出于安全考虑不回显密钥；前端留空表示"不修改"。
            "api_key": None,
            "base_url": cfg.get("base_url"),
            "model_name": cfg.get("model_name"),
            "enable_response_format": cfg.get("enable_response_format", True),
            "proxy_url": cfg.get("proxy_url"),
        })
    return {
        "models": models,
        "SKIP_AI_ANALYSIS": env_manager.get_value("SKIP_AI_ANALYSIS", "false").lower() == "true",
    }


@router.put("/ai")
async def update_ai_settings(settings: AISettingsModel):
    updates: Dict[str, str] = {}
    if settings.SKIP_AI_ANALYSIS is not None:
        updates["SKIP_AI_ANALYSIS"] = _normalize_bool_value(settings.SKIP_AI_ANALYSIS)

    # 读取已存在的密钥，便于前端留空时保留原值（不回显、不覆盖）。
    existing_models: List[Dict[str, Any]] = []
    raw_existing = env_manager.get_value("AI_MODELS", "")
    if raw_existing:
        try:
            parsed = json.loads(raw_existing)
            if isinstance(parsed, list):
                existing_models = [m for m in parsed if isinstance(m, dict)]
        except (json.JSONDecodeError, TypeError):
            existing_models = []

    cleaned_models: List[Dict[str, Any]] = []
    for idx, m in enumerate(settings.models):
        if not m.base_url or not m.model_name:
            continue
        # 若本次未提供密钥（前端留空），沿用同序号已存密钥。
        api_key = m.api_key or None
        if not api_key and idx < len(existing_models):
            api_key = existing_models[idx].get("api_key") or None
        cleaned_models.append({
            "api_key": api_key,
            "base_url": m.base_url,
            "model_name": m.model_name,
            "enable_response_format": bool(m.enable_response_format),
            "proxy_url": m.proxy_url or None,
        })

    if cleaned_models:
        updates["AI_MODELS"] = json.dumps(cleaned_models, ensure_ascii=False)
        # 同步主模型到传统 OPENAI_* 变量，兼容旧代码/脚本
        primary = cleaned_models[0]
        updates["OPENAI_API_KEY"] = primary.get("api_key") or ""
        updates["OPENAI_BASE_URL"] = primary.get("base_url") or ""
        updates["OPENAI_MODEL_NAME"] = primary.get("model_name") or ""
        updates["ENABLE_RESPONSE_FORMAT"] = _normalize_bool_value(
            primary.get("enable_response_format", True)
        )
        updates["PROXY_URL"] = primary.get("proxy_url") or ""
    else:
        updates["AI_MODELS"] = ""
        updates["OPENAI_API_KEY"] = ""
        updates["OPENAI_BASE_URL"] = ""
        updates["OPENAI_MODEL_NAME"] = ""
        updates["ENABLE_RESPONSE_FORMAT"] = "true"
        updates["PROXY_URL"] = ""

    success = env_manager.update_values(updates)
    if not success:
        raise HTTPException(status_code=500, detail="更新AI设置失败")
    _reload_env()
    return {"message": "AI设置已成功更新"}


@router.post("/ai/test")
async def test_ai_settings(model: AIModelConfigModel):
    """测试指定 AI 模型连接是否可用（每个模型均可单独测试）。"""
    try:
        from openai import OpenAI
        import httpx

        client_params = {
            "api_key": model.api_key or env_manager.get_value("OPENAI_API_KEY", ""),
            "base_url": model.base_url,
            "timeout": httpx.Timeout(30.0),
        }
        proxy_url = model.proxy_url
        if proxy_url:
            client_params["http_client"] = httpx.Client(proxy=proxy_url)

        model_name = model.model_name
        client = OpenAI(**client_params)
        messages = [{"role": "user", "content": AI_TEST_PROMPT}]
        api_mode = CHAT_COMPLETIONS_API_MODE
        disable_thinking = model_requires_thinking_disabled(model_name)

        try:
            request_params = build_ai_request_params(
                api_mode,
                model=model_name,
                messages=messages,
                max_output_tokens=AI_TEST_MAX_OUTPUT_TOKENS,
                enable_json_output=bool(model.enable_response_format),
            )
            if disable_thinking:
                request_params["extra_body"] = {"thinking": {"type": "disabled"}}
            response = create_ai_response_sync(client, api_mode, request_params)
        except Exception as exc:
            if not is_chat_completions_api_unsupported_error(exc):
                raise
            api_mode = RESPONSES_API_MODE
            request_params = build_ai_request_params(
                api_mode,
                model=model_name,
                messages=messages,
                max_output_tokens=AI_TEST_MAX_OUTPUT_TOKENS,
                enable_json_output=bool(model.enable_response_format),
            )
            if disable_thinking:
                request_params["extra_body"] = {"thinking": {"type": "disabled"}}
            response = create_ai_response_sync(client, api_mode, request_params)

        return {
            "success": True,
            "message": "AI模型连接测试成功！",
            "response": extract_ai_response_content(response),
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"AI模型连接测试失败: {exc}",
        }
