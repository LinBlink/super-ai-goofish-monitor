"""AI 请求兼容性辅助逻辑。"""

import copy
from typing import Any, Dict, Iterable, List


RESPONSES_API_MODE = "responses"
CHAT_COMPLETIONS_API_MODE = "chat_completions"
INPUT_TEXT_TYPE = "input_text"
INPUT_IMAGE_TYPE = "input_image"
IMAGE_DETAIL_AUTO = "auto"
JSON_OUTPUT_TYPE = "json_object"
UNSUPPORTED_JSON_OUTPUT_MARKERS = (
    "not supported by this model",
    "json_object",
    "json_schema",
    "text.format",
    "response_format.type",
)
RESPONSES_API_UNSUPPORTED_MARKERS = (
    "404 page not found",
    "page not found",
    "/responses",
    "/v1/responses",
)
CHAT_COMPLETIONS_API_UNSUPPORTED_MARKERS = (
    "404 page not found",
    "page not found",
    "/chat/completions",
    "/v1/chat/completions",
)
UNSUPPORTED_TEMPERATURE_MARKERS = (
    "temperature",
    "sampling temperature",
)
# 这些模型默认开启思考模式，且支持通过 enable_thinking=False 关闭。
THINKING_DISABLED_MODEL_MARKERS = ("minimax",)


def model_requires_thinking_disabled(model_name: str) -> bool:
    """识别默认需要关闭思考模式的模型（如 MiniMax）。"""
    name = (model_name or "").lower()
    return any(marker in name for marker in THINKING_DISABLED_MODEL_MARKERS)


def build_thinking_disable_extra(model_name: str, base_url: str = "") -> Dict[str, Any] | None:
    """按模型/MSP 返回关闭思考所需的 extra_body 参数；无需关闭时返回 None。

    - MiniMax（实测 M2.7-highspeed）：必须同时发送 OpenAI 兼容的 thinking.type=disabled
      与 enable_thinking=False——只发其一模型仍会进入推理模式并把整个 token 预算消耗在
      <think>... 上，导致正文为空/JSON 解析失败。
    - 腾讯 Hunyuan（hy3 / lkeap）：enable_thinking=False（enable_thinking=True 时模型会把
      输出几乎全部写入 reasoning_content 而让 content 为空，导致取不到答案）。
    """
    name = (model_name or "").lower()
    url = (base_url or "").lower()
    if "minimax" in name:
        return {
            "thinking": {"type": "disabled"},
            "enable_thinking": False,
        }
    is_tencent = ("lkeap" in url) or ("tencent" in url) or ("hunyuan" in name) or name.startswith("hy")
    if is_tencent:
        return {"enable_thinking": False}
    return None


def build_responses_input(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 Chat Completions 风格的消息转换为 Responses API 输入。"""
    input_items: List[Dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        input_items.append(
            {
                "role": role,
                "content": _build_input_content(message.get("content")),
            }
        )
    return input_items


def add_json_text_format(
    request_params: Dict[str, Any],
    enabled: bool,
) -> Dict[str, Any]:
    """按需附加 Responses API 的结构化 JSON 输出参数。"""
    next_params = dict(request_params)
    if not enabled:
        return next_params

    text_config = dict(next_params.get("text") or {})
    text_config["format"] = {"type": JSON_OUTPUT_TYPE}
    next_params["text"] = text_config
    return next_params


def add_json_response_format(
    request_params: Dict[str, Any],
    enabled: bool,
) -> Dict[str, Any]:
    """按需附加 Chat Completions 的 JSON 输出参数。"""
    next_params = dict(request_params)
    if enabled:
        next_params["response_format"] = {"type": JSON_OUTPUT_TYPE}
    return next_params


def is_json_output_unsupported_error(error: Exception) -> bool:
    """识别模型或网关不支持结构化 JSON 输出参数的错误。"""
    body = getattr(error, "body", None)
    if isinstance(body, dict) and body.get("param") in (
        "response_format",
        "response_format.type",
    ):
        return True

    message = str(error)
    return (
        "not supported" in message.lower()
        and any(marker in message for marker in UNSUPPORTED_JSON_OUTPUT_MARKERS)
    )


def is_responses_api_unsupported_error(error: Exception) -> bool:
    """识别 OpenAI 兼容服务未实现 Responses API 的错误。"""
    return _is_api_unsupported_error(error, RESPONSES_API_UNSUPPORTED_MARKERS)


def is_chat_completions_api_unsupported_error(error: Exception) -> bool:
    """识别 OpenAI 兼容服务未实现 Chat Completions API 的错误。"""
    return _is_api_unsupported_error(error, CHAT_COMPLETIONS_API_UNSUPPORTED_MARKERS)


def build_ai_request_params(
    api_mode: str,
    *,
    model: str,
    messages: Iterable[Dict[str, Any]],
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    enable_json_output: bool = False,
) -> Dict[str, Any]:
    """根据 API 模式构建请求参数。"""
    request_params = {"model": model}
    if api_mode == RESPONSES_API_MODE:
        request_params["input"] = build_responses_input(messages)
        if max_output_tokens is not None:
            request_params["max_output_tokens"] = max_output_tokens
        if temperature is not None:
            request_params["temperature"] = temperature
        return add_json_text_format(request_params, enable_json_output)

    if api_mode == CHAT_COMPLETIONS_API_MODE:
        request_params["messages"] = copy.deepcopy(list(messages))
        if max_output_tokens is not None:
            request_params["max_tokens"] = max_output_tokens
        if temperature is not None:
            request_params["temperature"] = temperature
        return add_json_response_format(request_params, enable_json_output)

    raise ValueError(f"不支持的 AI API 模式: {api_mode}")


async def create_ai_response_async(
    client: Any,
    api_mode: str,
    request_params: Dict[str, Any],
) -> Any:
    """根据 API 模式发起异步请求。"""
    if api_mode == RESPONSES_API_MODE:
        return await client.responses.create(**request_params)
    if api_mode == CHAT_COMPLETIONS_API_MODE:
        return await client.chat.completions.create(**request_params)
    raise ValueError(f"不支持的 AI API 模式: {api_mode}")


def create_ai_response_sync(
    client: Any,
    api_mode: str,
    request_params: Dict[str, Any],
) -> Any:
    """根据 API 模式发起同步请求。"""
    if api_mode == RESPONSES_API_MODE:
        return client.responses.create(**request_params)
    if api_mode == CHAT_COMPLETIONS_API_MODE:
        return client.chat.completions.create(**request_params)
    raise ValueError(f"不支持的 AI API 模式: {api_mode}")


def is_rate_limit_error(error: Exception) -> bool:
    """识别触发限流(HTTP 429)的错误，包括中转网关自定义的限流错误体。"""
    status_code = getattr(error, "status_code", None)
    if status_code == 429:
        return True
    message = str(error).lower()
    return "429" in message or "rate_limit" in message or "rate limit" in message


def get_retry_after_seconds(error: Exception) -> float | None:
    """尝试从限流错误的响应头中提取服务端建议的重试等待秒数，取不到则返回 None。"""
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None or not hasattr(headers, "get"):
        return None
    for key in ("retry-after", "Retry-After", "x-ratelimit-reset"):
        value = headers.get(key)
        if value is None:
            continue
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if seconds >= 0:
            return seconds
    return None


def is_temperature_unsupported_error(error: Exception) -> bool:
    """识别模型或中转站不支持 temperature 参数的错误。"""
    message = str(error).lower()
    return (
        "not supported" in message
        or "unsupported" in message
        or "invalid" in message
        or "参数错误" in message
    ) and any(marker in message for marker in UNSUPPORTED_TEMPERATURE_MARKERS)


def remove_temperature_param(request_params: Dict[str, Any]) -> Dict[str, Any]:
    """移除 temperature 参数，适配不支持采样温度的模型网关。"""
    next_params = dict(request_params)
    next_params.pop("temperature", None)
    return next_params


def _is_api_unsupported_error(
    error: Exception,
    markers: tuple[str, ...],
) -> bool:
    message = str(error).lower()
    if any(marker in message for marker in markers):
        return True

    status_code = getattr(error, "status_code", None)
    body = getattr(error, "body", None)
    response = getattr(error, "response", None)
    response_text = getattr(response, "text", None) if response else None
    return (
        status_code == 404
        and message.strip() == "error code: 404"
        and not body
        and not response_text
    )


def _build_input_content(content: Any) -> List[Dict[str, Any]]:
    if isinstance(content, str):
        return [{"type": INPUT_TEXT_TYPE, "text": content}]
    if not isinstance(content, list):
        raise ValueError(f"AI消息内容类型不受支持: {type(content).__name__}")

    return [_coerce_content_item(item) for item in content]


def _coerce_content_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"AI消息片段类型不受支持: {type(item).__name__}")

    item_type = item.get("type")
    if item_type in {"text", INPUT_TEXT_TYPE}:
        text = item.get("text")
        if not isinstance(text, str):
            raise ValueError("文本消息片段缺少 text 字段。")
        return {"type": INPUT_TEXT_TYPE, "text": text}

    if item_type in {"image_url", INPUT_IMAGE_TYPE}:
        return _build_image_input_item(item)

    raise ValueError(f"不支持的 AI 消息片段类型: {item_type}")


def _build_image_input_item(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_image = item.get("image_url")
    if isinstance(raw_image, dict):
        image_url = raw_image.get("url")
    else:
        image_url = raw_image

    if not isinstance(image_url, str) or not image_url.strip():
        raise ValueError("图片消息片段缺少有效的 image_url。")

    return {
        "type": INPUT_IMAGE_TYPE,
        "image_url": image_url,
        "detail": item.get("detail", IMAGE_DETAIL_AUTO),
    }
