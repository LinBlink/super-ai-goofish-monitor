"""
统一配置管理模块
使用 Pydantic 进行类型安全的配置管理
"""
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _USING_PYDANTIC_SETTINGS = True
except ImportError:
    from pydantic import BaseSettings
    _USING_PYDANTIC_SETTINGS = False
from pydantic import Field
from typing import Optional, List, Dict, Any
import os
import json

DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
DEFAULT_SMTP_PORT = 465


def _env_field(default, env_name: str, **kwargs):
    if _USING_PYDANTIC_SETTINGS:
        return Field(default, validation_alias=env_name, **kwargs)
    return Field(default, env=env_name, **kwargs)


if _USING_PYDANTIC_SETTINGS:
    class _EnvSettings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
            protected_namespaces=(),
        )
else:
    class _EnvSettings(BaseSettings):
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"
            protected_namespaces = ()


class AISettings(_EnvSettings):
    """AI模型配置

    支持配置多个模型：第一个模型为主模型，其余模型用于兜底。
    多模型通过环境变量 ``AI_MODELS`` (JSON 数组) 配置；若未配置 AI_MODELS，
    则退化使用传统的 OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL_NAME 作为唯一主模型。
    """
    api_key: Optional[str] = _env_field(None, "OPENAI_API_KEY")
    base_url: str = _env_field("", "OPENAI_BASE_URL")
    model_name: str = _env_field("", "OPENAI_MODEL_NAME")
    proxy_url: Optional[str] = _env_field(None, "PROXY_URL")
    debug_mode: bool = _env_field(False, "AI_DEBUG_MODE")
    enable_response_format: bool = _env_field(True, "ENABLE_RESPONSE_FORMAT")
    enable_thinking: bool = _env_field(False, "ENABLE_THINKING")
    skip_analysis: bool = _env_field(False, "SKIP_AI_ANALYSIS")
    call_timeout: int = _env_field(300, "AI_CALL_TIMEOUT_SECONDS")
    ai_models_json: Optional[str] = _env_field(None, "AI_MODELS")

    def _normalize_model_config(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """将原始字典规整为统一模型配置结构。"""
        def _as_bool(value, default: bool) -> bool:
            if isinstance(value, bool):
                return value
            if value is None:
                return default
            return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

        return {
            "api_key": raw.get("api_key") or None,
            "base_url": (raw.get("base_url") or "").strip(),
            "model_name": (raw.get("model_name") or "").strip(),
            "proxy_url": raw.get("proxy_url") or None,
            "enable_response_format": _as_bool(raw.get("enable_response_format"), True),
            "enable_thinking": _as_bool(raw.get("enable_thinking"), False),
        }

    def models(self) -> List[Dict[str, Any]]:
        """返回有序模型配置列表，第一个为主模型，其余为兜底模型。

        若 AI_MODELS 已配置且可解析，优先使用；否则回退到传统的单模型环境变量。
        """
        if self.ai_models_json:
            try:
                parsed = json.loads(self.ai_models_json)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, list) and parsed:
                result = []
                for item in parsed:
                    if not isinstance(item, dict):
                        continue
                    cfg = self._normalize_model_config(item)
                    if not cfg["base_url"] or not cfg["model_name"]:
                        continue
                    result.append(cfg)
                if result:
                    return result

        # 回退：使用传统单模型环境变量
        if self.base_url and self.model_name:
            return [self._normalize_model_config({
                "api_key": self.api_key,
                "base_url": self.base_url,
                "model_name": self.model_name,
                "proxy_url": self.proxy_url,
                "enable_response_format": self.enable_response_format,
                "enable_thinking": self.enable_thinking,
            })]
        return []

    def is_configured(self) -> bool:
        """检查AI是否已正确配置（至少存在一个可用模型）"""
        return bool(self.models())


class NotificationSettings(_EnvSettings):
    """通知服务配置"""
    ntfy_topic_url: Optional[str] = _env_field(None, "NTFY_TOPIC_URL")
    ntfy_enabled: bool = _env_field(True, "NTFY_ENABLED")
    gotify_url: Optional[str] = _env_field(None, "GOTIFY_URL")
    gotify_token: Optional[str] = _env_field(None, "GOTIFY_TOKEN")
    gotify_enabled: bool = _env_field(True, "GOTIFY_ENABLED")
    bark_url: Optional[str] = _env_field(None, "BARK_URL")
    bark_enabled: bool = _env_field(True, "BARK_ENABLED")
    wx_bot_url: Optional[str] = _env_field(None, "WX_BOT_URL")
    wx_bot_enabled: bool = _env_field(True, "WX_BOT_ENABLED")
    telegram_bot_token: Optional[str] = _env_field(None, "TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = _env_field(None, "TELEGRAM_CHAT_ID")
    telegram_api_base_url: Optional[str] = _env_field(
        DEFAULT_TELEGRAM_API_BASE_URL,
        "TELEGRAM_API_BASE_URL",
    )
    telegram_enabled: bool = _env_field(True, "TELEGRAM_ENABLED")
    webhook_url: Optional[str] = _env_field(None, "WEBHOOK_URL")
    webhook_method: str = _env_field("POST", "WEBHOOK_METHOD")
    webhook_headers: Optional[str] = _env_field(None, "WEBHOOK_HEADERS")
    webhook_content_type: str = _env_field("JSON", "WEBHOOK_CONTENT_TYPE")
    webhook_query_parameters: Optional[str] = _env_field(None, "WEBHOOK_QUERY_PARAMETERS")
    webhook_body: Optional[str] = _env_field(None, "WEBHOOK_BODY")
    webhook_enabled: bool = _env_field(True, "WEBHOOK_ENABLED")
    smtp_host: Optional[str] = _env_field(None, "SMTP_HOST")
    smtp_port: int = _env_field(DEFAULT_SMTP_PORT, "SMTP_PORT")
    smtp_username: Optional[str] = _env_field(None, "SMTP_USERNAME")
    smtp_password: Optional[str] = _env_field(None, "SMTP_PASSWORD")
    smtp_from_address: Optional[str] = _env_field(None, "SMTP_FROM_ADDRESS")
    smtp_to_address: Optional[str] = _env_field(None, "SMTP_TO_ADDRESS")
    smtp_use_ssl: bool = _env_field(True, "SMTP_USE_SSL")
    email_enabled: bool = _env_field(True, "EMAIL_ENABLED")
    pcurl_to_mobile: bool = _env_field(True, "PCURL_TO_MOBILE")

    def has_any_notification_enabled(self) -> bool:
        """检查是否配置了任何通知服务"""
        return any([
            self.ntfy_topic_url and self.ntfy_enabled,
            self.wx_bot_url and self.wx_bot_enabled,
            self.gotify_url and self.gotify_token and self.gotify_enabled,
            self.bark_url and self.bark_enabled,
            self.telegram_bot_token and self.telegram_chat_id and self.telegram_enabled,
            self.webhook_url and self.webhook_enabled,
            self.smtp_host and self.smtp_username and self.smtp_password and self.smtp_to_address and self.email_enabled,
        ])


class ScraperSettings(_EnvSettings):
    """爬虫相关配置"""
    run_headless: bool = _env_field(True, "RUN_HEADLESS")
    login_is_edge: bool = _env_field(False, "LOGIN_IS_EDGE")
    running_in_docker: bool = _env_field(False, "RUNNING_IN_DOCKER")
    use_system_chrome: bool = _env_field(True, "USE_SYSTEM_CHROME")
    state_file: str = _env_field("xianyu_state.json", "STATE_FILE")


class AppSettings(_EnvSettings):
    """应用主配置"""
    server_port: int = _env_field(8000, "SERVER_PORT")
    web_username: str = _env_field("admin", "WEB_USERNAME")
    web_password: str = _env_field("admin123", "WEB_PASSWORD")
    task_log_retention_days: int = _env_field(7, "TASK_LOG_RETENTION_DAYS", ge=1)
    price_snapshot_retention_days: int = _env_field(
        30, "PRICE_SNAPSHOT_RETENTION_DAYS", ge=0
    )
    result_item_retention_days: int = _env_field(
        90, "RESULT_ITEM_RETENTION_DAYS", ge=0
    )

    # 文件路径配置
    config_file: str = "config.json"
    image_save_dir: str = "images"
    task_image_dir_prefix: str = "task_images_"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 创建必要的目录
        os.makedirs(self.image_save_dir, exist_ok=True)


# 全局配置实例（单例模式）
_settings_instance = None

def get_settings() -> AppSettings:
    """获取全局配置实例"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AppSettings()
    return _settings_instance


def reload_settings() -> None:
    """重新加载全局配置实例"""
    global _settings_instance, settings, ai_settings, notification_settings, scraper_settings
    from dotenv import load_dotenv
    from src.infrastructure.config.env_manager import env_manager

    load_dotenv(dotenv_path=env_manager.env_file, override=True)
    _settings_instance = None
    settings = get_settings()
    ai_settings = AISettings()
    notification_settings = NotificationSettings()
    scraper_settings = ScraperSettings()


# 导出便捷访问的配置实例
settings = get_settings()
ai_settings = AISettings()
notification_settings = NotificationSettings()
scraper_settings = ScraperSettings()
