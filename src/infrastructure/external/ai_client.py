"""
AI 客户端封装
提供统一的 AI 调用接口
"""
import asyncio
import ipaddress
import os
import json
import base64
import random
from typing import Dict, List, Optional
from datetime import datetime
from dotenv import load_dotenv
import openai
from openai import AsyncOpenAI
from src.ai_message_builder import (
    build_analysis_text_prompt,
    build_user_message_content,
)
from src.infrastructure.config.settings import AISettings
from src.infrastructure.config.env_manager import env_manager
from src.services.ai_request_compat import (
    CHAT_COMPLETIONS_API_MODE,
    RESPONSES_API_MODE,
    build_ai_request_params,
    create_ai_response_async,
    is_chat_completions_api_unsupported_error,
    is_json_output_unsupported_error,
    is_rate_limit_error,
    is_responses_api_unsupported_error,
    is_temperature_unsupported_error,
    build_thinking_disable_extra,
    remove_temperature_param,
)

# 单次退避上限：5 小时。速率限制/调用失败时按指数增长，最久退避到该值。
AI_RATE_LIMIT_BASE_SECONDS = 5
AI_RATE_LIMIT_MAX_SECONDS = 5 * 60 * 60
from src.services.ai_response_parser import (
    EmptyAIResponseError,
    extract_ai_response_content,
    parse_ai_response_json,
)


def _sanitize_no_proxy_env() -> None:
    """Strip CIDR prefix lengths from IPv6 entries in NO_PROXY / no_proxy.

    httpx <= 0.28.1 wraps NO_PROXY IPv6 entries in brackets *including* the
    CIDR mask (e.g. ``[::1/128]``), which the URL parser rejects as an invalid
    port.  Stripping the ``/prefix`` part is safe because httpx doesn't
    support CIDR range matching anyway — it only does exact-host comparison.

    See https://github.com/encode/httpx/pull/3741
    """
    for key in ("NO_PROXY", "no_proxy"):
        value = os.environ.get(key)
        if not value:
            continue
        parts = [h.strip() for h in value.split(",")]
        cleaned: list[str] = []
        changed = False
        for part in parts:
            if "/" in part:
                host, _, prefix = part.partition("/")
                try:
                    ipaddress.IPv6Address(host)
                    cleaned.append(host)
                    changed = True
                    continue
                except ValueError:
                    pass
            cleaned.append(part)
        if changed:
            os.environ[key] = ",".join(cleaned)


class AIClient:
    """AI 客户端封装"""

    def __init__(self):
        self.settings: Optional[AISettings] = None
        self.client: Optional[AsyncOpenAI] = None
        self.refresh()

    def _load_settings(self) -> None:
        load_dotenv(dotenv_path=env_manager.env_file, override=True)
        self.settings = AISettings()
        self._model_configs = self.settings.models()
        self._primary = self._model_configs[0] if self._model_configs else None

    def refresh(self) -> None:
        self._load_settings()
        self.client = self._initialize_client()

    def _initialize_client(self) -> Optional[AsyncOpenAI]:
        """初始化 OpenAI 客户端（使用主模型配置）"""
        if not self._primary:
            print("警告：AI 配置不完整，AI 功能将不可用")
            return None

        try:
            proxy_url = self._primary.get("proxy_url")
            if proxy_url:
                print(f"正在为 AI 请求使用代理: {proxy_url}")
                os.environ['HTTP_PROXY'] = proxy_url
                os.environ['HTTPS_PROXY'] = proxy_url

            _sanitize_no_proxy_env()

            return AsyncOpenAI(
                api_key=self._primary.get("api_key"),
                base_url=self._primary.get("base_url")
            )
        except Exception as e:
            print(f"初始化 AI 客户端失败: {e}")
            return None

    def is_available(self) -> bool:
        """检查 AI 客户端是否可用"""
        return self.client is not None

    async def close(self) -> None:
        """关闭底层异步客户端，避免事件循环结束后再触发清理。"""
        client = self.client
        self.client = None
        if client is None:
            return

        close = getattr(client, "close", None)
        if close is None:
            return
        await close()

    @staticmethod
    def encode_image(image_path: str) -> Optional[str]:
        """将图片编码为 Base64"""
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"编码图片失败: {e}")
            return None

    async def analyze(
        self,
        product_data: Dict,
        image_paths: List[str],
        prompt_text: str
    ) -> Optional[Dict]:
        """
        分析商品数据

        Args:
            product_data: 商品数据
            image_paths: 图片路径列表
            prompt_text: 分析提示词

        Returns:
            分析结果
        """
        if not self.is_available():
            print("AI 客户端不可用")
            return None

        try:
            messages = self._build_messages(product_data, image_paths, prompt_text)
            response = await self._call_ai(messages)
            return self._parse_response(response)
        except Exception as e:
            print(f"AI 分析失败: {e}")
            return None

    def _build_messages(self, product_data: Dict, image_paths: List[str], prompt_text: str) -> List[Dict]:
        """构建 AI 消息"""
        product_json = json.dumps(product_data, ensure_ascii=False, indent=2)
        image_data_urls: List[str] = []
        for path in image_paths:
            base64_img = self.encode_image(path)
            if base64_img:
                image_data_urls.append(f"data:image/jpeg;base64,{base64_img}")

        text_prompt = build_analysis_text_prompt(
            product_json,
            prompt_text,
            include_images=bool(image_data_urls),
        )
        user_content = build_user_message_content(text_prompt, image_data_urls)
        return [{"role": "user", "content": user_content}]

    def _client_for_config(self, config: dict) -> Optional[AsyncOpenAI]:
        """为指定模型配置创建 OpenAI 异步客户端（主模型复用 self.client）。"""
        if config is self._primary:
            return self.client
        try:
            proxy_url = config.get("proxy_url")
            params: dict = {
                "api_key": config.get("api_key"),
                "base_url": config.get("base_url"),
            }
            if proxy_url:
                import httpx

                params["http_client"] = httpx.AsyncClient(proxy=proxy_url)
            return AsyncOpenAI(**params)
        except Exception as exc:  # noqa: BLE001
            print(f"初始化模型客户端失败 ({config.get('model_name')}): {exc}")
            return None

    def _model_runners(self) -> list:
        """返回有序的 (client, config) 列表，第一个为主模型，其余为兜底模型。

        主模型复用 self.client（连接池友好），兜底模型按需新建客户端。
        当未配置模型列表（兼容仅设置 client/settings 的旧调用方式）时，
        退化为单主模型运行器，保证单个主客户端也能正常工作。
        """
        configs = getattr(self, "_model_configs", None) or []
        if not configs and getattr(self, "client", None) is not None:
            settings = getattr(self, "settings", None)
            if settings is not None:
                return [
                    (
                        self.client,
                        {
                            "model_name": getattr(settings, "model_name", None),
                            "enable_response_format": getattr(
                                settings, "enable_response_format", True
                            ),
                            "enable_thinking": getattr(settings, "enable_thinking", False),
                            "api_key": None,
                            "base_url": None,
                            "proxy_url": None,
                        },
                    )
                ]
        runners: list = []
        for config in configs:
            client = self._client_for_config(config)
            if client is not None:
                runners.append((client, config))
        return runners

    async def _call_ai(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.1,
        max_output_tokens: int = 4000,
        enable_json_output: Optional[bool] = None,
    ) -> str:
        """调用 AI API。

        多模型兜底：依次尝试主模型及其余兜底模型。某模型触发速率限制(429)时立即切换
        下一个模型，避免在当前模型上长时间退避重试；API/网络错误也在内部重试耗尽后
        切换到下一模型。空响应/JSON 解析失败不触发兜底，直接作为本次调用失败。
        """
        runners = self._model_runners()
        if not runners:
            print("警告：AI 配置不完整，AI 功能将不可用")
            raise RuntimeError("AI 客户端未初始化，无法生成内容。请检查.env配置。")

        last_exc: Optional[BaseException] = None
        for idx, (client, config) in enumerate(runners):
            model_name = config.get("model_name")
            if client is None:
                continue
            try:
                return await self._call_ai_with_single_model(
                    client,
                    config,
                    messages,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    enable_json_output=enable_json_output,
                )
            except (
                openai.APIConnectionError,
                openai.APITimeoutError,
                openai.APIStatusError,
            ) as exc:
                last_exc = exc
                role = "主模型" if idx == 0 else f"兜底模型#{idx}"
                print(
                    f"{role} ({model_name}) 发生API/网络错误，切换下一模型: {exc}"
                )
                continue
            except Exception as exc:
                last_exc = exc
                role = "主模型" if idx == 0 else f"兜底模型#{idx}"
                print(f"{role} ({model_name}) 调用失败: {exc}")
                continue
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("AI 调用在所有模型上均失败")

    async def _call_ai_with_single_model(
        self,
        client: AsyncOpenAI,
        config: dict,
        messages: List[Dict],
        *,
        temperature: float,
        max_output_tokens: int,
        enable_json_output: Optional[bool],
    ) -> str:
        """使用单一指定模型配置调用 AI（内部函数，不含多模型兜底）。"""
        model_name = config.get("model_name")
        api_mode = CHAT_COMPLETIONS_API_MODE
        use_response_format = (
            config.get("enable_response_format", True)
            if enable_json_output is None
            else enable_json_output
        )
        use_temperature = True
        max_attempts = 12

        for attempt in range(max_attempts):
            request_params = build_ai_request_params(
                api_mode,
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                enable_json_output=use_response_format,
            )
            if not use_temperature:
                request_params = remove_temperature_param(request_params)

            thinking_extra = build_thinking_disable_extra(
                model_name, config.get("base_url", "")
            )
            if thinking_extra is None and config.get("enable_thinking"):
                # 手动开启“禁用思考”开关时的通用兜底
                thinking_extra = {"thinking": {"type": "disabled"}}
            if thinking_extra:
                request_params["extra_body"] = thinking_extra

            try:
                response = await create_ai_response_async(
                    client,
                    api_mode,
                    request_params,
                )
                return extract_ai_response_content(response)
            except EmptyAIResponseError as exc:
                if attempt < max_attempts - 1:
                    print(
                        f"AI响应为空，正在自动重试 ({attempt + 2}/{max_attempts})"
                    )
                    continue
                raise exc
            except Exception as exc:
                changed = False
                if (
                    api_mode == CHAT_COMPLETIONS_API_MODE
                    and is_chat_completions_api_unsupported_error(exc)
                ):
                    api_mode = RESPONSES_API_MODE
                    changed = True
                    print("当前服务未实现 Chat Completions API，正在自动回退到 Responses API")
                elif (
                    api_mode == RESPONSES_API_MODE
                    and is_responses_api_unsupported_error(exc)
                ):
                    api_mode = CHAT_COMPLETIONS_API_MODE
                    changed = True
                    print("当前服务未实现 Responses API，正在自动回退到 Chat Completions API")
                if use_response_format and is_json_output_unsupported_error(exc):
                    use_response_format = False
                    changed = True
                    print("当前模型不支持结构化 JSON 输出，正在自动重试并移除该参数")
                if use_temperature and is_temperature_unsupported_error(exc):
                    use_temperature = False
                    changed = True
                    print("当前模型不支持 temperature 参数，正在自动重试并移除该参数")
                if changed and attempt < max_attempts - 1:
                    continue
                # 速率限制(429)：该模型已到用量上限，立即抛出给外层多模型循环切换兜底模型，
                # 避免在当前模型上长时间退避重试。
                if is_rate_limit_error(exc):
                    print(f"模型 {model_name} 触发速率限制(429)，立即切换兜底模型: {exc}")
                    raise
                if attempt < max_attempts - 1:
                    wait = min(
                        AI_RATE_LIMIT_MAX_SECONDS,
                        AI_RATE_LIMIT_BASE_SECONDS * (2 ** attempt),
                    )
                    wait += random.uniform(0, wait * 0.2)
                    print(
                        f"AI 调用失败，将在 {wait:.0f} 秒后重试 ({attempt + 2}/{max_attempts})"
                    )
                    await asyncio.sleep(wait)
                    continue
                raise

        raise RuntimeError("AI 调用在兼容性重试后仍未返回结果")

    def _parse_response(self, response_text: str) -> Optional[Dict]:
        """解析 AI 响应"""
        try:
            return parse_ai_response_json(response_text)
        except json.JSONDecodeError:
            print(f"无法解析 AI 响应: {response_text[:100]}")
            return None
