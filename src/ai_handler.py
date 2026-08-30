import asyncio
import base64
import json
import os
import random
import re
import sys
import shutil
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import openai
import requests

# 设置标准输出编码为UTF-8，解决Windows控制台编码问题
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

from src.config import (
    AI_DEBUG_MODE,
    IMAGE_DOWNLOAD_HEADERS,
    IMAGE_SAVE_DIR,
    TASK_IMAGE_DIR_PREFIX,
    build_model_runners,
)
from src.ai_message_builder import (
    build_analysis_text_prompt,
    build_user_message_content,
)
from src.services.ai_response_parser import (
    EmptyAIResponseError,
    ModelRepeatedParseError,
    extract_ai_response_content,
    parse_ai_response_json,
)
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
from src.services.notification_service import NotificationService, build_notification_service
from src.utils import convert_goofish_link, retry_on_failure


def _positive_int(value, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


DEFAULT_IMAGE_DOWNLOAD_CONCURRENCY = max(
    1,
    _positive_int(os.getenv("IMAGE_DOWNLOAD_CONCURRENCY", "3"), 3),
)

RATE_LIMIT_BASE_DELAY_SECONDS = 5
# 单次退避上限：5 小时。速率限制/调用失败时按指数增长，最久退避到该值。
RATE_LIMIT_MAX_DELAY_SECONDS = 5 * 60 * 60

# 非速率限制类调用失败的单次退避上限（如服务不可用/超时），不应等 5 小时。
GENERAL_FAILURE_MAX_BACKOFF_SECONDS = 60
# 单次 AI 请求超时秒数。超时即视作失败进入重试/兜底分支。
AI_CALL_TIMEOUT_SECONDS = int(os.getenv("AI_CALL_TIMEOUT_SECONDS", "60"))
# 熔断阈值：连续失败 N 次后熔断一段时间，期间直接跳过该模型的调用。
AI_CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("AI_CIRCUIT_FAILURE_THRESHOLD", "3"))
# 熔断冷却时间（秒）：熔断开启后多久进入半开状态。
AI_CIRCUIT_COOLDOWN_SECONDS = int(os.getenv("AI_CIRCUIT_COOLDOWN_SECONDS", "300"))


class ModelCircuitOpenError(Exception):
    """模型熔断开启：跳过当前调用，避免服务不可用期间持续空转。"""


class _ModelCircuitBreaker:
    """按模型名跟踪连续失败次数，超过阈值后熔断一段时间。"""

    def __init__(self, threshold: int, cooldown_seconds: int) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_seconds
        self._state: Dict[str, Dict[str, float]] = {}

    def is_open(self, model_name: str) -> bool:
        info = self._state.get(model_name)
        if not info:
            return False
        failures = info.get("failures", 0)
        if failures < self._threshold:
            return False
        last_failure = info.get("last_failure", 0.0)
        if (time.monotonic() - last_failure) >= self._cooldown:
            # 进入半开：允许下一次调用尝试。
            return False
        return True

    def record_failure(self, model_name: str) -> None:
        info = self._state.setdefault(model_name, {"failures": 0, "last_failure": 0.0})
        info["failures"] = info.get("failures", 0) + 1
        info["last_failure"] = time.monotonic()

    def record_success(self, model_name: str) -> None:
        self._state.pop(model_name, None)


_MODEL_CIRCUIT = _ModelCircuitBreaker(
    threshold=AI_CIRCUIT_FAILURE_THRESHOLD,
    cooldown_seconds=AI_CIRCUIT_COOLDOWN_SECONDS,
)


def safe_print(text, level: str = "INFO"):
    """安全的打印函数，处理编码错误，并附上时间戳与日志等级。"""
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        ts = "--:--:--"
    line = f"[{ts}] [{level}] {text}"
    try:
        print(line)
    except UnicodeEncodeError:
        # 如果遇到编码错误，尝试用ASCII编码并忽略无法编码的字符
        try:
            print(line.encode('ascii', errors='ignore').decode('ascii'))
        except Exception:
            # 如果还是失败，打印一个简化的消息
            print("[输出包含无法显示的字符]")


def _build_debug_request_summary(api_mode: str, request_params: dict) -> dict:
    summary = {
        "api_mode": api_mode,
        "model": request_params.get("model"),
    }
    if "temperature" in request_params:
        summary["temperature"] = request_params["temperature"]
    if "max_output_tokens" in request_params:
        summary["max_output_tokens"] = request_params["max_output_tokens"]
    if "max_tokens" in request_params:
        summary["max_tokens"] = request_params["max_tokens"]
    if "text" in request_params:
        summary["text"] = request_params["text"]
    if "response_format" in request_params:
        summary["response_format"] = request_params["response_format"]
    if "input" in request_params:
        summary["input_content_types"] = [
            [item.get("type") for item in message.get("content", [])]
            for message in request_params["input"]
        ]
    if "messages" in request_params:
        summary["message_content_types"] = [
            _extract_message_content_types(message)
            for message in request_params["messages"]
        ]
    return summary


def _extract_message_content_types(message: dict) -> list[str]:
    content = message.get("content")
    if isinstance(content, str):
        return ["text"]
    if not isinstance(content, list):
        return [type(content).__name__]
    return [str(item.get("type")) for item in content if isinstance(item, dict)]


@retry_on_failure(retries=2, delay=3)
async def _download_single_image(url, save_path):
    """一个带重试的内部函数，用于异步下载单个图片。"""
    loop = asyncio.get_running_loop()
    # 使用 run_in_executor 运行同步的 requests 代码，避免阻塞事件循环
    response = await loop.run_in_executor(
        None,
        lambda: requests.get(url, headers=IMAGE_DOWNLOAD_HEADERS, timeout=20, stream=True)
    )
    response.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return save_path


def _build_image_save_path(
    product_id: str,
    index: int,
    url: str,
    task_image_dir: str,
) -> str:
    clean_url = url.split('.heic')[0] if '.heic' in url else url
    file_name_base = os.path.basename(clean_url).split('?')[0]
    file_name = f"product_{product_id}_{index}_{file_name_base}"
    file_name = re.sub(r'[\\/*?:"<>|]', "", file_name)
    if not os.path.splitext(file_name)[1]:
        file_name += ".jpg"
    return os.path.join(task_image_dir, file_name)


async def download_all_images(product_id, image_urls, task_name="default", concurrency=None):
    """异步下载一个商品的所有图片。如果图片已存在则跳过。支持任务隔离。"""
    if not image_urls:
        return []

    # 为每个任务创建独立的图片目录
    task_image_dir = os.path.join(IMAGE_SAVE_DIR, f"{TASK_IMAGE_DIR_PREFIX}{task_name}")
    os.makedirs(task_image_dir, exist_ok=True)

    urls = [url.strip() for url in image_urls if url.strip().startswith('http')]
    if not urls:
        return []

    max_concurrency = _positive_int(concurrency, DEFAULT_IMAGE_DOWNLOAD_CONCURRENCY)
    semaphore = asyncio.Semaphore(max_concurrency)
    total_images = len(urls)

    async def _download_one(index: int, url: str):
        save_path = _build_image_save_path(product_id, index, url, task_image_dir)
        if os.path.exists(save_path):
            safe_print(
                f"   [图片] 图片 {index}/{total_images} 已存在，跳过下载: {os.path.basename(save_path)}"
            )
            return save_path
        async with semaphore:
            safe_print(f"   [图片] 正在下载图片 {index}/{total_images}: {url}")
            if await _download_single_image(url, save_path):
                safe_print(
                    f"   [图片] 图片 {index}/{total_images} 已成功下载到: {os.path.basename(save_path)}"
                )
                return save_path
        return None

    tasks = [
        asyncio.create_task(_download_one(index, url))
        for index, url in enumerate(urls, start=1)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    saved_paths = []
    for url, result in zip(urls, results):
        try:
            if isinstance(result, Exception):
                raise result
            if result:
                saved_paths.append(result)
        except Exception as e:
            safe_print(f"   [图片] 处理图片 {url} 时发生错误，已跳过此图: {e}")

    return saved_paths


def cleanup_task_images(task_name):
    """清理指定任务的图片目录"""
    task_image_dir = os.path.join(IMAGE_SAVE_DIR, f"{TASK_IMAGE_DIR_PREFIX}{task_name}")
    if os.path.exists(task_image_dir):
        try:
            shutil.rmtree(task_image_dir)
            safe_print(f"   [清理] 已删除任务 '{task_name}' 的临时图片目录: {task_image_dir}")
        except Exception as e:
            safe_print(f"   [清理] 删除任务 '{task_name}' 的临时图片目录时出错: {e}")
    else:
        safe_print(f"   [清理] 任务 '{task_name}' 的临时图片目录不存在: {task_image_dir}")


def cleanup_ai_logs(logs_dir: str, keep_days: int = 1) -> None:
    try:
        cutoff = datetime.now() - timedelta(days=keep_days)
        for filename in os.listdir(logs_dir):
            if not filename.endswith(".log"):
                continue
            try:
                timestamp = datetime.strptime(filename[:15], "%Y%m%d_%H%M%S")
            except ValueError:
                continue
            if timestamp < cutoff:
                os.remove(os.path.join(logs_dir, filename))
    except Exception as e:
        safe_print(f"   [日志] 清理AI日志时出错: {e}")


def encode_image_to_base64(image_path):
    """将本地图片文件编码为 Base64 字符串。"""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        safe_print(f"编码图片时出错: {e}")
        return None


# 分析标准版本；base_prompt.txt 要求模型回显该字段，但部分模型（如 MiniMax）经常漏掉，
# 缺失时直接补默认值，避免因一个自描述字段而反复重试、浪费额度。
EXPECTED_PROMPT_VERSION = "EagleEye-V6.4"


def validate_ai_response_format(parsed_response):
    """验证AI响应的格式是否符合预期结构"""
    required_fields = [
        "is_recommended",
        "reason",
        "risk_tags",
        "criteria_analysis"
    ]

    # 检查顶层字段
    for field in required_fields:
        if field not in parsed_response:
            safe_print(f"   [AI分析] 警告：响应缺少必需字段 '{field}'")
            return False

    # 检查criteria_analysis是否为字典且不为空
    criteria_analysis = parsed_response.get("criteria_analysis", {})
    if not isinstance(criteria_analysis, dict) or not criteria_analysis:
        safe_print("   [AI分析] 警告：criteria_analysis必须是非空字典")
        return False

    # 检查seller_type字段（所有商品都需要）
    if "seller_type" not in criteria_analysis:
        safe_print("   [AI分析] 警告：criteria_analysis缺少必需字段 'seller_type'")
        return False

    # 检查数据类型
    if not isinstance(parsed_response.get("is_recommended"), bool):
        safe_print("   [AI分析] 警告：is_recommended字段不是布尔类型")
        return False

    if not isinstance(parsed_response.get("risk_tags"), list):
        safe_print("   [AI分析] 警告：risk_tags字段不是列表类型")
        return False

    return True


async def send_ntfy_notification(product_data, reason, retries=3, delay=5):
    """兼容旧调用名，内部统一走 NotificationService。

    NotificationService 内部会捕获每个渠道自己的异常并转换为结果字典（不会向外抛异常），
    因此重试只能在这一层针对"发送失败的渠道"显式重试，已经成功的渠道不会被重复发送。
    """
    service = build_notification_service()
    if not service.clients:
        safe_print(
            "警告：未在 .env 文件中配置任何通知服务，跳过通知。"
        )
        return {}

    pending_clients = list(service.clients)
    final_results: dict = {}

    for attempt in range(retries):
        attempt_results = await NotificationService(pending_clients).send_notification(product_data, reason)
        final_results.update(attempt_results)

        pending_clients = [
            client for client in pending_clients
            if not final_results[client.channel_key]["success"]
        ]
        if not pending_clients:
            break
        if attempt < retries - 1:
            safe_print(
                f"   -> {len(pending_clients)} 个通知渠道发送失败，将在 {delay} 秒后重试（第 {attempt + 1}/{retries} 次）..."
            )
            await asyncio.sleep(delay)

    for channel, result in final_results.items():
        if result["success"]:
            safe_print(f"   -> {channel} 通知发送成功。")
            continue
        safe_print(f"   -> {channel} 通知发送失败: {result['message']}")
    return final_results


async def get_ai_analysis(product_data, image_paths=None, prompt_text=""):
    """将完整的商品JSON数据和所有图片发送给 AI 进行分析（异步）。

    多模型兜底：依次尝试主模型及其余兜底模型。API/网络错误或同一模型连续
    多次解析失败都会触发兜底切换，避免在出问题的模型上浪费时间和 token。
    """
    runners = build_model_runners()
    if not runners:
        safe_print("   [AI分析] 错误：AI客户端未初始化，跳过分析。")
        return None
    last_exc = None
    for idx, (client, model_name, enable_response_format) in enumerate(runners):
        # 熔断开启：模型最近连续失败次数过多，冷却期间跳过本次调用。
        if _MODEL_CIRCUIT.is_open(model_name):
            role = "主模型" if idx == 0 else f"兜底模型#{idx}"
            safe_print(
                f"   [AI分析] {role} ({model_name}) 处于熔断冷却中，跳过本次调用",
                level="WARNING",
            )
            raise ModelCircuitOpenError(f"{model_name} 熔断中")
        try:
            return await _analyze_with_single_model(
                client, model_name, enable_response_format, product_data, image_paths, prompt_text
            )
        except (openai.APIConnectionError, openai.APITimeoutError, openai.APIStatusError) as e:
            last_exc = e
            role = "主模型" if idx == 0 else f"兜底模型#{idx}"
            safe_print(f"   [AI分析] {role} ({model_name}) 发生API/网络错误，切换下一模型: {e}", level="WARNING")
            continue
        except ModelRepeatedParseError as e:
            role = "主模型" if idx == 0 else f"兜底模型#{idx}"
            is_last = idx >= len(runners) - 1
            if is_last:
                safe_print(
                    f"   [AI分析] {role} ({model_name}) 连续解析失败且已是最后一个模型，放弃兜底: {e}",
                    level="ERROR",
                )
                raise
            safe_print(
                f"   [AI分析] {role} ({model_name}) 解析连续失败，切换下一模型: {e}",
                level="WARNING",
            )
            continue
    if last_exc is not None:
        raise last_exc
    return None


async def _analyze_with_single_model(client, model_name, enable_response_format, product_data, image_paths=None, prompt_text=""):
    """使用单一指定模型对商品进行分析（内部函数，不含多模型兜底）。"""
    if not client:
        safe_print("   [AI分析] 错误：该模型客户端未初始化，跳过。")
        return None

    item_info = product_data.get('商品信息', {})
    product_id = item_info.get('商品ID', 'N/A')

    safe_print(f"\n   [AI分析][{model_name}] 开始分析商品 #{product_id} (含 {len(image_paths or [])} 张图片)...")
    safe_print(f"   [AI分析] 标题: {item_info.get('商品标题', '无')}")

    if not prompt_text:
        safe_print("   [AI分析] 错误：未提供AI分析所需的prompt文本。")
        return None

    product_details_json = json.dumps(product_data, ensure_ascii=False, indent=2)
    system_prompt = prompt_text

    if AI_DEBUG_MODE:
        safe_print("\n--- [AI DEBUG] ---")
        safe_print("--- PRODUCT DATA (JSON) ---")
        safe_print(product_details_json)
        safe_print("--- PROMPT TEXT (完整内容) ---")
        safe_print(prompt_text)
        safe_print("-------------------\n")

    image_data_urls = []
    if image_paths:
        for path in image_paths:
            base64_image = encode_image_to_base64(path)
            if base64_image:
                image_data_urls.append(f"data:image/jpeg;base64,{base64_image}")

    combined_text_prompt = build_analysis_text_prompt(
        product_details_json,
        system_prompt,
        include_images=bool(image_data_urls),
    )
    user_content = build_user_message_content(combined_text_prompt, image_data_urls)
    messages = [{"role": "user", "content": user_content}]

    # 保存最终传输内容到日志文件
    try:
        # 创建logs文件夹
        logs_dir = os.path.join("logs", "ai")
        os.makedirs(logs_dir, exist_ok=True)
        cleanup_ai_logs(logs_dir, keep_days=1)

        # 生成日志文件名（当前时间）
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{current_time}.log"
        log_filepath = os.path.join(logs_dir, log_filename)

        task_name = product_data.get("任务名称") or product_data.get("任务名") or "unknown"
        log_payload = {
            "timestamp": current_time,
            "task_name": task_name,
            "product_id": product_id,
            "title": item_info.get("商品标题", "无"),
            "image_count": len(image_data_urls),
        }
        log_content = json.dumps(log_payload, ensure_ascii=False)

        # 写入日志文件
        with open(log_filepath, 'w', encoding='utf-8') as f:
            f.write(log_content)

        safe_print(f"   [日志] AI分析请求已保存到: {log_filepath}")

    except Exception as e:
        safe_print(f"   [日志] 保存AI分析日志时出错: {e}")

    # 增强的AI调用，包含更严格的结构化输出控制和重试机制
    # 退避按指数增长，单次最长 RATE_LIMIT_MAX_DELAY_SECONDS(5h)，此处重试次数需足够多才能逼近上限。
    # 退避按指数增长，单次最长 RATE_LIMIT_MAX_DELAY_SECONDS(5h)。这里只需要
    # 几次重试来覆盖瞬时抖动；同一 prompt 反复解析失败时应让上层切到兜底模型。
    max_retries = 5
    parse_failure_threshold = 2  # 连续 N 次解析/格式失败则抛 ModelRepeatedParseError
    api_mode = CHAT_COMPLETIONS_API_MODE
    use_response_format = enable_response_format
    use_temperature = True
    consecutive_parse_failures = 0
    for attempt in range(max_retries):
        try:
            # 根据重试次数调整参数
            current_temperature = 0.1 if attempt == 0 else 0.05  # 重试时使用更低的温度

            request_params = build_ai_request_params(
                api_mode,
                model=model_name,
                messages=messages,
                temperature=current_temperature,
                max_output_tokens=8192,
                enable_json_output=use_response_format,
            )
            if not use_temperature:
                request_params = remove_temperature_param(request_params)

            # 按模型关闭 thinking：MiniMax 用 thinking.type=disabled，腾讯 Hy3 用 enable_thinking=False
            thinking_extra = build_thinking_disable_extra(model_name)
            if thinking_extra:
                request_params["extra_body"] = thinking_extra

            if AI_DEBUG_MODE:
                safe_print(f"\n--- [AI DEBUG] 第{attempt + 1}次尝试 REQUEST ---")
                safe_print(
                    json.dumps(
                        _build_debug_request_summary(api_mode, request_params),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                safe_print("-----------------------------------\n")

            response = await asyncio.wait_for(
                create_ai_response_async(
                    client,
                    api_mode,
                    request_params,
                ),
                timeout=AI_CALL_TIMEOUT_SECONDS,
            )
            ai_response_content = extract_ai_response_content(response)

            if AI_DEBUG_MODE:
                safe_print(f"\n--- [AI DEBUG] 第{attempt + 1}次尝试 ---")
                safe_print("--- RAW AI RESPONSE ---")
                safe_print(ai_response_content)
                safe_print("---------------------\n")

            try:
                parsed_response = parse_ai_response_json(ai_response_content)

                # 部分模型会漏掉自描述的 prompt_version 字段，缺失时补默认值，
                # 避免因为这一非关键字段导致整次分析失败并重试。
                if not parsed_response.get("prompt_version"):
                    parsed_response["prompt_version"] = EXPECTED_PROMPT_VERSION

                # 验证响应格式
                if validate_ai_response_format(parsed_response):
                    safe_print(f"   [AI分析] 第{attempt + 1}次尝试成功，响应格式验证通过")
                    _MODEL_CIRCUIT.record_success(model_name)
                    return parsed_response
                safe_print(f"   [AI分析] 第{attempt + 1}次尝试格式验证失败")
                consecutive_parse_failures += 1
                if consecutive_parse_failures >= parse_failure_threshold:
                    safe_print(
                        f"   [AI分析] 模型 {model_name} 连续 {consecutive_parse_failures} 次解析/格式校验失败，立即切换兜底模型",
                        level="WARNING",
                    )
                    raise ModelRepeatedParseError(
                        f"{model_name} 连续 {consecutive_parse_failures} 次解析失败"
                    )
                if attempt < max_retries - 1:
                    safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                    continue
                raise EmptyAIResponseError("AI响应格式缺少必需字段或字段类型不正确。")
            except json.JSONDecodeError as e:
                safe_print(f"   [AI分析] 第{attempt + 1}次尝试JSON解析失败: {e}")
                consecutive_parse_failures += 1
                if consecutive_parse_failures >= parse_failure_threshold:
                    safe_print(
                        f"   [AI分析] 模型 {model_name} 连续 {consecutive_parse_failures} 次解析失败，立即切换兜底模型",
                        level="WARNING",
                    )
                    raise ModelRepeatedParseError(
                        f"{model_name} 连续 {consecutive_parse_failures} 次解析失败"
                    )
                if attempt < max_retries - 1:
                    safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                    continue
                raise e
            except EmptyAIResponseError as e:
                safe_print(f"   [AI分析] 第{attempt + 1}次尝试返回空响应: {e}")
                consecutive_parse_failures += 1
                if consecutive_parse_failures >= parse_failure_threshold:
                    safe_print(
                        f"   [AI分析] 模型 {model_name} 连续 {consecutive_parse_failures} 次解析失败，立即切换兜底模型",
                        level="WARNING",
                    )
                    raise ModelRepeatedParseError(
                        f"{model_name} 连续 {consecutive_parse_failures} 次解析失败"
                    )
                if attempt < max_retries - 1:
                    safe_print(f"   [AI分析] 准备第{attempt + 2}次重试...")
                    continue
                raise e

        except ModelRepeatedParseError:
            # 解析连续失败的信号应原样抛给外层多模型循环去切兜底模型，
            # 不要被通用 except 当成普通调用失败再走指数退避。
            raise
        except Exception as e:
            if (
                api_mode == CHAT_COMPLETIONS_API_MODE
                and is_chat_completions_api_unsupported_error(e)
            ):
                api_mode = RESPONSES_API_MODE
                safe_print(
                    "   [AI分析] 当前服务未实现 Chat Completions API，后续重试将自动回退到 Responses API。"
                )
            elif api_mode == RESPONSES_API_MODE and is_responses_api_unsupported_error(e):
                api_mode = CHAT_COMPLETIONS_API_MODE
                safe_print(
                    "   [AI分析] 当前服务未实现 Responses API，后续重试将自动回退到 Chat Completions API。"
                )
            if use_response_format and is_json_output_unsupported_error(e):
                use_response_format = False
                safe_print(
                    "   [AI分析] 当前模型不支持结构化 JSON 输出，后续重试将自动禁用该参数。"
                )
            if use_temperature and is_temperature_unsupported_error(e):
                use_temperature = False
                safe_print(
                    "   [AI分析] 当前模型不支持 temperature 参数，后续重试将自动禁用该参数。"
                )
            if AI_DEBUG_MODE:
                safe_print(f"\n--- [AI DEBUG] 第{attempt + 1}次尝试 EXCEPTION ---")
                safe_print(repr(e))
                safe_print(traceback.format_exc())
                safe_print("-------------------------------------\n")
            # 速率限制(429)意味着该模型已到用量上限，原地重试只会长时间卡住
            # （旧行为会指数退避至多 12 次、最长 5 小时），因此首次遇到就立即
            # 抛出给外层多模型循环，切换到兜底模型。
            if is_rate_limit_error(e):
                safe_print(
                    f"   [AI分析] 模型 {model_name} 触发速率限制(429)，立即切换兜底模型: {e}",
                    level="ERROR",
                )
                raise
            safe_print(f"   [AI分析] 第{attempt + 1}次尝试AI调用失败: {e}")
            _MODEL_CIRCUIT.record_failure(model_name)
            if attempt < max_retries - 1:
                # 非速率限制的一般调用失败：指数退避（带抖动），单次最长 GENERAL_FAILURE_MAX_BACKOFF_SECONDS。
                # 与限流 5h 不同：服务不可用/超时不应每次等几小时。
                wait_seconds = min(
                    GENERAL_FAILURE_MAX_BACKOFF_SECONDS,
                    RATE_LIMIT_BASE_DELAY_SECONDS * (2 ** attempt),
                )
                wait_seconds += random.uniform(0, wait_seconds * 0.2)
                safe_print(
                    f"   [AI分析] 已触发调用失败，将在 {wait_seconds:.0f} 秒后进行第{attempt + 2}次重试..."
                )
                await asyncio.sleep(wait_seconds)
                continue
            else:
                raise e


async def screen_product_title(
    title: str, keyword: str, requirements: str
) -> tuple[bool, str]:
    """轻量级标题预筛：用 AI 判断商品标题是否「根本不符合」要求。

    多模型兜底：主模型发生 API/网络错误时切换到兜底模型；其余异常或空响应不触发兜底，
    保守地返回 (True, "") 即「不跳过」，确保预筛失败不会漏掉潜在目标商品。
    """
    if not title or not requirements:
        return True, ""
    runners = build_model_runners()
    if not runners:
        return True, ""
    for idx, (client, model_name, enable_response_format) in enumerate(runners):
        # 熔断开启：冷却期间跳过 AI 预筛，避免大批商品空转。
        if _MODEL_CIRCUIT.is_open(model_name):
            role = "主模型" if idx == 0 else f"兜底模型#{idx}"
            safe_print(
                f"   [AI标题预筛] {role} ({model_name}) 处于熔断冷却中，保守不跳过",
                level="WARNING",
            )
            return True, ""
        try:
            return await _screen_with_single_model(
                client, model_name, enable_response_format, title, keyword, requirements
            )
        except (openai.APIConnectionError, openai.APITimeoutError, openai.APIStatusError) as e:
            role = "主模型" if idx == 0 else f"兜底模型#{idx}"
            safe_print(f"   [AI标题预筛] {role} ({model_name}) 发生API/网络错误，切换下一模型: {e}", level="WARNING")
            continue
        except ModelRepeatedParseError as e:
            role = "主模型" if idx == 0 else f"兜底模型#{idx}"
            is_last = idx >= len(runners) - 1
            if is_last:
                safe_print(
                    f"   [AI标题预筛] {role} ({model_name}) 连续解析失败且已是最后一个模型，保守不跳过: {e}",
                    level="WARNING",
                )
                return True, ""
            safe_print(
                f"   [AI标题预筛] {role} ({model_name}) 解析连续失败，切换下一模型: {e}",
                level="WARNING",
            )
            continue
    # 所有模型均不可用（API/网络错误），保守地不跳过
    return True, ""


async def _screen_with_single_model(
    client, model_name, enable_response_format, title: str, keyword: str, requirements: str
) -> tuple[bool, str]:
    """使用单一指定模型进行标题预筛（内部函数，不含多模型兜底）。"""
    if client is None:
        return True, ""

    system_prompt = (
        "你是一个严格的商品预筛选器。用户会提供一个搜索关键词、一份「商品要求描述」"
        "以及一条来自二手交易平台（闲鱼）的商品标题。\n"
        "请仅根据标题判断：该商品是否「根本不符合」用户要求"
        "（例如品类完全无关、明显不是所求物品、或属于明确排除的类型）。\n"
        "注意：标题信息有限，只要不能断定「根本不符」，就应视为可能相关（match=true）。\n"
        "只输出严格的 JSON，不要输出任何额外文字，格式为：\n"
        '{"match": true/false, "reason": "简短中文理由"}'
    )
    user_text = (
        f"搜索关键词：{keyword}\n"
        f"商品要求描述：\n{requirements}\n\n"
        f"待判断的商品标题：\n{title}\n\n"
        "请判断该标题是否根本不符合要求，并只返回 JSON。"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    api_mode = CHAT_COMPLETIONS_API_MODE
    max_retries = 4
    parse_failure_threshold = 2  # 连续 N 次解析失败则抛 ModelRepeatedParseError
    consecutive_parse_failures = 0
    for attempt in range(max_retries):
        try:
            request_params = build_ai_request_params(
                api_mode,
                model=model_name,
                messages=messages,
                temperature=0.0,
                # MiniMax M2.x 会在正文里输出 思考 过程，1024 给足预算防止 JSON 截断
                max_output_tokens=1024,
                enable_json_output=enable_response_format,
            )
            # 按模型关闭 thinking：MiniMax 用 thinking.type=disabled，腾讯 Hy3 用 enable_thinking=False
            thinking_extra = build_thinking_disable_extra(model_name)
            if thinking_extra:
                request_params["extra_body"] = thinking_extra

            response = await asyncio.wait_for(
                create_ai_response_async(client, api_mode, request_params),
                timeout=AI_CALL_TIMEOUT_SECONDS,
            )
            content = extract_ai_response_content(response)
            try:
                parsed = parse_ai_response_json(content)
            except (EmptyAIResponseError, json.JSONDecodeError, ValueError) as parse_exc:
                consecutive_parse_failures += 1
                if consecutive_parse_failures >= parse_failure_threshold:
                    safe_print(
                        f"   [AI标题预筛] 模型 {model_name} 连续 {consecutive_parse_failures} 次解析失败，立即切换兜底模型: {parse_exc}",
                        level="WARNING",
                    )
                    raise ModelRepeatedParseError(
                        f"{model_name} 连续 {consecutive_parse_failures} 次解析失败"
                    ) from parse_exc
                safe_print(
                    f"   [AI标题预筛] 第{attempt + 1}次解析失败，准备第{attempt + 2}次重试: {parse_exc}"
                )
                continue
            match_val = parsed.get("match")
            if isinstance(match_val, str):
                match_val = str(match_val).strip().lower() in {"true", "1", "是", "yes"}
            match = bool(match_val)
            reason = str(parsed.get("reason", ""))[:200]
            _MODEL_CIRCUIT.record_success(model_name)
            return match, reason
        except Exception as exc:  # noqa: BLE001
            # 速率限制(429)意味着该模型已到用量上限，立即抛出给外层多模型循环切换兜底模型，
            # 避免在这个模型上长时间退避重试。
            if is_rate_limit_error(exc):
                safe_print(
                    f"   [AI标题预筛] 模型 {model_name} 触发速率限制(429)，立即切换兜底模型: {exc}",
                    level="ERROR",
                )
                raise
            if isinstance(exc, ModelRepeatedParseError):
                raise
            _MODEL_CIRCUIT.record_failure(model_name)
            safe_print(f"   [AI标题预筛] 第{attempt + 1}次调用失败: {exc}")
            if attempt < max_retries - 1:
                wait_seconds = min(
                    GENERAL_FAILURE_MAX_BACKOFF_SECONDS,
                    RATE_LIMIT_BASE_DELAY_SECONDS * (2 ** attempt),
                )
                wait_seconds += random.uniform(0, wait_seconds * 0.2)
                safe_print(
                    f"   [AI标题预筛] 已触发调用失败，将在 {wait_seconds:.0f} 秒后进行第{attempt + 2}次重试..."
                )
                await asyncio.sleep(wait_seconds)
                continue
            # 最后一次尝试仍失败：API/网络错误交给外层多模型兜底，其余保守不跳过
            if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError, openai.APIStatusError)):
                raise
            return True, ""
    return True, ""
