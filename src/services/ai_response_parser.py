"""
AI 响应解析工具
"""
import json
import re
from typing import Any

_THINK_TAG_PATTERN = re.compile(r"\s*thinking.*? response", re.IGNORECASE | re.DOTALL)
# 覆盖未封闭或带属性的思考标记（<thinking attr>…<answer> 等）。
_THINK_TAG_LOOSE_PATTERN = re.compile(
    r"<\s*(thinking|reasoning|analysis)\b[^>]*>.*?(?:<\s*/\s*\1\s*>|<\s*(answer|response)\b[^>]*>)",
    re.IGNORECASE | re.DOTALL,
)
# 删除残留的各种思考标签本身（如 <thinking>、</thinking>、<reasoning> …）。
_THINK_TAG_STRIP_PATTERN = re.compile(
    r"<\s*/\s*(thinking|reasoning|analysis)\s*>|<\s*(thinking|reasoning|analysis)\b[^>]*>",
    re.IGNORECASE,
)


class EmptyAIResponseError(ValueError):
    """AI 返回了空内容。"""


class ModelRepeatedParseError(Exception):
    """同一模型对同一 prompt 多次解析失败，触发上层切换到兜底模型。"""


def extract_ai_response_content(response: Any) -> str:
    """从不同形态的 AI 响应中提取文本内容。"""
    if response is None:
        raise EmptyAIResponseError("AI响应对象为空。")

    if isinstance(response, (bytes, bytearray)):
        text = response.decode("utf-8", errors="replace")
        return _normalize_text_content(text)

    if isinstance(response, str):
        return _normalize_text_content(response)

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return _normalize_text_content(output_text)

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is None:
            raise EmptyAIResponseError("AI响应缺少 message。")
        content = getattr(message, "content", None)

        # 彻底忽略思考：reasoning_content 是模型的思考过程，不作为答案返回。
        # 若 output 的 content 缺失，抛 EmptyAIResponseError 触发重试/兜底，而非用思考内容充当答案。
        return _normalize_text_content(_coerce_content_parts(content))

    raise ValueError(f"无法识别的AI响应类型: {type(response).__name__}")


def parse_ai_response_json(content: str) -> dict:
    """解析 AI 文本响应中的 JSON。若模型误输出为数组，取首个对象元素。"""
    cleaned = _strip_code_fences(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        parsed = _extract_first_json_value(cleaned, exc)

    # 部分模型会误把单个对象包在数组里返回，如 [{...}]，取首个对象元素。
    if isinstance(parsed, list):
        if parsed and isinstance(parsed[0], dict):
            return parsed[0]
        # [] 或 [scalar,...] 不是有效对象，按"无响应"处理，触发上层快速重试/兜底模型，
        # 而不是被外层通用异常捕获后做数小时指数退避。
        raise EmptyAIResponseError("AI 响应为空数组或非对象数组。")
    if not isinstance(parsed, dict):
        raise EmptyAIResponseError(f"AI 响应非预期类型: {type(parsed).__name__}")
    return parsed


def _coerce_content_parts(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        return content.decode("utf-8", errors="replace")
    if not isinstance(content, list):
        raise ValueError(f"AI响应内容类型不受支持: {type(content).__name__}")

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if isinstance(item, dict):
            # 彻底忽略思考类内容块（如 OpenAI 兼容的 type=reasoning/thinking/analysis），
            # 避免思考过程混入答案、影响解析。
            part_type = item.get("type")
            if isinstance(part_type, str) and part_type.lower() in {
                "reasoning",
                "thinking",
                "analysis",
            }:
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
            continue
        text = getattr(item, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _normalize_text_content(content: str) -> str:
    text = str(content).strip()
    if not text:
        raise EmptyAIResponseError("AI响应内容为空。")
    text = _strip_thinking_tags(text)
    if not text:
        raise EmptyAIResponseError("AI响应内容为空。")
    return text


def _strip_thinking_tags(text: str) -> str:
    """彻底移除模型中输出的思考过程，避免其影响答案解析。

    不同推理模型的思考格式各不相同（如 thinking/…/response 块、
    <thinking>…</thinking>、<reasoning>…</reasoning>、<analysis>…</analysis>）。
    这里用多组正则做防御性剥离：先去掉块状思考，再去掉残留的思考标签。
    JSON 等结构化输出本身不含思考标签，剥离后不影响其内容。
    """
    if not text:
        return text
    stripped = _THINK_TAG_PATTERN.sub("", text)
    stripped = _THINK_TAG_LOOSE_PATTERN.sub("", stripped)
    stripped = _THINK_TAG_STRIP_PATTERN.sub("", stripped)
    return stripped.strip()


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _extract_first_json_value(
    content: str,
    fallback_error: json.JSONDecodeError,
):
    decoder = json.JSONDecoder()
    last_error: json.JSONDecodeError | None = None

    for start_index, char in enumerate(content):
        if char not in "{[":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[start_index:])
            return parsed
        except json.JSONDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise fallback_error
