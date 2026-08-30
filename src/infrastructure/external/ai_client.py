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
    get_retry_after_seconds,
    is_chat_completions_api_unsupported_error,
    is_json_output_unsupported_error,
    is_rate_limit_error,
    is_responses_api_unsupported_error,
    is_temperature_unsupported_error,
    model_requires_thinking_disabled,
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

    async def _call_ai(
        self,
        messages: List[Dict],
        *,
        temperature: float = 0.1,
        max_output_tokens: int = 4000,
        enable_json_output: Optional[bool] = None,
    ) -> str:
        """调用 AI API"""
        api_mode = CHAT_COMPLETIONS_API_MODE
        use_response_format = (
            self._primary.get("enable_response_format", True)
            if enable_json_output is None
            else enable_json_output
        )
        use_temperature = True
        # 退避按指数增长，单次最长 AI_RATE_LIMIT_MAX_SECONDS(5h)，此处重试次数需足够多才能逼近上限。
        max_attempts = 12

        for attempt in range(max_attempts):
            request_params = build_ai_request_params(
                api_mode,
                model=self._primary.get("model_name"),
                messages=messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                enable_json_output=use_response_format,
            )
            if not use_temperature:
                request_params = remove_temperature_param(request_params)

            if self._primary.get("enable_thinking") or model_requires_thinking_disabled(
                self._primary.get("model_name")
            ):
                # MiniMax（含 M3）通过 thinking.type=disabled 关闭思考；M2.x 会忽略。
                request_params["extra_body"] = {"thinking": {"type": "disabled"}}

            try:
                response = await create_ai_response_async(
                    self.client,
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
                # 速率限制(429)或一般调用失败：指数退避（带抖动），单次最长 5 小时。
                if attempt < max_attempts - 1 and is_rate_limit_error(exc):
                    wait = get_retry_after_seconds(exc)
                    if wait is None:
                        wait = min(
                            AI_RATE_LIMIT_MAX_SECONDS,
                            AI_RATE_LIMIT_BASE_SECONDS * (2 ** attempt),
                        )
                    wait += random.uniform(0, wait * 0.2)
                    print(
                        f"AI 调用触发速率限制(429)，将在 {wait:.0f} 秒后重试 ({attempt + 2}/{max_attempts})"
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
