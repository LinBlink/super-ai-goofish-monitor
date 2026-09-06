"""
价格历史记录与聚合服务
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from datetime import date, datetime
from statistics import median
from typing import Any, Iterable, Optional

from src.infrastructure.persistence.sqlite_bootstrap import bootstrap_sqlite_storage
from src.infrastructure.persistence.sqlite_connection import sqlite_connection

PRICE_HISTORY_DIR = "price_history"
DEFAULT_HISTORY_WINDOW_DAYS = 30


def normalize_keyword_slug(keyword: str) -> str:
    text = "".join(
        char for char in str(keyword or "").lower().replace(" ", "_")
        if char.isalnum() or char in "_-"
    ).rstrip("_")
    return text or "unknown"


def build_price_history_path(keyword: str) -> str:
    return os.path.join(
        PRICE_HISTORY_DIR,
        f"{normalize_keyword_slug(keyword)}_history.jsonl",
    )


def parse_price_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)

    text = str(value).strip().replace("¥", "").replace(",", "")
    if not text or text in {"价格异常", "暂无", "-", "N/A"}:
        return None
    if text.endswith("万"):
        text = str(float(text[:-1]) * 10000)
    try:
        return round(float(text), 2)
    except (TypeError, ValueError):
        return None


def _safe_iso_datetime(value: Optional[str]) -> str:
    if value:
        return value
    return datetime.now().isoformat()


def _to_day(iso_text: str) -> str:
    return iso_text[:10]


def _build_snapshot_record(
    *,
    keyword: str,
    task_name: str,
    item: dict,
    run_id: str,
    snapshot_time: str,
) -> Optional[dict]:
    item_id = str(item.get("商品ID") or "").strip()
    link = str(item.get("商品链接") or "").strip()
    unique_id = item_id or link
    price_value = parse_price_value(item.get("当前售价"))
    if not unique_id or price_value is None:
        return None

    return {
        "snapshot_time": snapshot_time,
        "snapshot_day": _to_day(snapshot_time),
        "run_id": run_id,
        "task_name": task_name,
        "keyword": keyword,
        "item_id": unique_id,
        "title": item.get("商品标题") or "",
        "price": price_value,
        "price_display": item.get("当前售价") or "",
        "tags": item.get("商品标签") or [],
        "region": item.get("发货地区") or "",
        "seller": item.get("卖家昵称") or "",
        "publish_time": item.get("发布时间") or "",
        "link": link,
    }


def record_market_snapshots(
    *,
    keyword: str,
    task_name: str,
    items: Iterable[dict],
    run_id: str,
    snapshot_time: Optional[str] = None,
    seen_item_ids: Optional[set[str]] = None,
) -> list[dict]:
    snapshot_time = _safe_iso_datetime(snapshot_time)
    seen = seen_item_ids if seen_item_ids is not None else set()
    records: list[dict] = []

    for item in items:
        record = _build_snapshot_record(
            keyword=keyword,
            task_name=task_name,
            item=item,
            run_id=run_id,
            snapshot_time=snapshot_time,
        )
        if record is None or record["item_id"] in seen:
            continue
        seen.add(record["item_id"])
        records.append(record)

    if not records:
        return []

    bootstrap_sqlite_storage()
    keyword_slug = normalize_keyword_slug(keyword)
    with sqlite_connection() as conn:
        for record in records:
            conn.execute(
                """
                INSERT OR IGNORE INTO price_snapshots (
                    keyword_slug, keyword, task_name, snapshot_time, snapshot_day,
                    run_id, item_id, title, price, price_display, tags_json, region,
                    seller, publish_time, link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    keyword_slug,
                    record.get("keyword", keyword),
                    record.get("task_name", task_name),
                    record.get("snapshot_time", snapshot_time),
                    record.get("snapshot_day", _to_day(snapshot_time)),
                    record.get("run_id", run_id),
                    record.get("item_id", ""),
                    record.get("title", ""),
                    record.get("price"),
                    record.get("price_display", ""),
                    json.dumps(record.get("tags") or [], ensure_ascii=False),
                    record.get("region", ""),
                    record.get("seller", ""),
                    record.get("publish_time", ""),
                    record.get("link", ""),
                ),
            )
        conn.commit()
    return records


def load_price_snapshots(keyword: str) -> list[dict]:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM price_snapshots
            WHERE keyword_slug = ?
            ORDER BY snapshot_time ASC, id ASC
            """,
            (normalize_keyword_slug(keyword),),
        ).fetchall()
    snapshots: list[dict] = []
    for row in rows:
        snapshots.append(
            {
                "snapshot_time": row["snapshot_time"],
                "snapshot_day": row["snapshot_day"],
                "run_id": row["run_id"],
                "task_name": row["task_name"],
                "keyword": row["keyword"],
                "item_id": row["item_id"],
                "title": row["title"],
                "price": row["price"],
                "price_display": row["price_display"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "region": row["region"],
                "seller": row["seller"],
                "publish_time": row["publish_time"],
                "link": row["link"],
            }
        )
    return snapshots


def rename_price_history(old_keyword: str, new_keyword: str, new_task_name: str) -> bool:
    """任务改关键词后，把历史价格快照迁移到新的 keyword_slug 下。

    若新 keyword 的 slug 已被别的任务占用，跳过迁移（返回 False）而不是把两份历史数据混在一起。
    """
    old_slug = normalize_keyword_slug(old_keyword)
    new_slug = normalize_keyword_slug(new_keyword)
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        if old_slug == new_slug:
            conn.execute(
                "UPDATE price_snapshots SET keyword = ?, task_name = ? WHERE keyword_slug = ?",
                (new_keyword, new_task_name, old_slug),
            )
            conn.commit()
            return True

        collision = conn.execute(
            "SELECT 1 FROM price_snapshots WHERE keyword_slug = ? LIMIT 1",
            (new_slug,),
        ).fetchone()
        if collision is not None:
            return False

        conn.execute(
            """
            UPDATE price_snapshots
            SET keyword_slug = ?, keyword = ?, task_name = ?
            WHERE keyword_slug = ?
            """,
            (new_slug, new_keyword, new_task_name, old_slug),
        )
        conn.commit()
        return True


def delete_price_snapshots(keyword: str) -> int:
    bootstrap_sqlite_storage()
    with sqlite_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM price_snapshots WHERE keyword_slug = ?",
            (normalize_keyword_slug(keyword),),
        )
        conn.commit()
    return int(cursor.rowcount or 0)


def _dedupe_latest(records: Iterable[dict], group_key: str) -> list[dict]:
    latest_by_key: dict[str, dict] = {}
    for record in records:
        key = str(record.get(group_key) or "").strip()
        if not key:
            continue
        latest_by_key[key] = record
    return list(latest_by_key.values())


def _summarize_prices(records: Iterable[dict]) -> dict:
    entries = [record for record in records if parse_price_value(record.get("price")) is not None]
    prices = [float(record["price"]) for record in entries]
    if not prices:
        return {
            "sample_count": 0,
            "avg_price": None,
            "median_price": None,
            "min_price": None,
            "max_price": None,
        }

    return {
        "sample_count": len(prices),
        "avg_price": round(sum(prices) / len(prices), 2),
        "median_price": round(float(median(prices)), 2),
        "min_price": round(min(prices), 2),
        "max_price": round(max(prices), 2),
    }


def _build_daily_trend(
    snapshots: list[dict],
    ai_item_ids_by_day: Optional[dict[str, set[str]]] = None,
) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for snapshot in snapshots:
        grouped[str(snapshot.get("snapshot_day") or "")].append(snapshot)

    points: list[dict] = []
    for day in sorted(grouped.keys()):
        day_snapshots = grouped[day]
        if ai_item_ids_by_day is not None and day in ai_item_ids_by_day:
            day_snapshots = [
                snapshot
                for snapshot in day_snapshots
                if str(snapshot.get("item_id") or "") in ai_item_ids_by_day[day]
            ]
        day_records = _dedupe_latest(day_snapshots, "item_id")
        summary = _summarize_prices(day_records)
        summary["day"] = day
        points.append(summary)
    return points


def _recent_window_snapshots(snapshots: list[dict], window_days: int) -> list[dict]:
    if not snapshots:
        return []
    latest_time = max(str(record.get("snapshot_time") or "") for record in snapshots)
    latest_dt = datetime.fromisoformat(latest_time)
    filtered = []
    for record in snapshots:
        current_time = datetime.fromisoformat(str(record.get("snapshot_time") or latest_time))
        if (latest_dt - current_time).days <= max(0, window_days):
            filtered.append(record)
    return filtered


def _resolve_deal_label(score: int) -> str:
    if score >= 65:
        return "高性价比"
    if score >= 50:
        return "值得关注"
    if score >= 40:
        return "价格正常"
    return "价格偏高"


def build_item_price_context(
    snapshots: list[dict],
    *,
    item_id: str,
    current_price: Optional[float],
    market_snapshots: Optional[list[dict]] = None,
) -> dict:
    if not item_id:
        return {"observation_count": 0, "deal_score": None, "deal_label": "暂无数据"}

    item_snapshots = [record for record in snapshots if str(record.get("item_id")) == str(item_id)]
    if not item_snapshots:
        return {"observation_count": 0, "deal_score": None, "deal_label": "暂无数据"}

    latest_item_snapshot = item_snapshots[-1]
    price_now = current_price if current_price is not None else parse_price_value(latest_item_snapshot.get("price"))
    historical_prices = [float(record["price"]) for record in item_snapshots if parse_price_value(record.get("price")) is not None]
    source_snapshots = market_snapshots if market_snapshots is not None else snapshots
    latest_run_id = str(source_snapshots[-1].get("run_id") or "") if source_snapshots else ""
    latest_market = _dedupe_latest(
        [record for record in source_snapshots if str(record.get("run_id") or "") == latest_run_id],
        "item_id",
    )
    market_summary = _summarize_prices(latest_market)
    market_avg = market_summary.get("avg_price")
    market_median = market_summary.get("median_price")

    score = 50
    if price_now is not None and market_avg:
        score += int(((market_avg - price_now) / market_avg) * 60)
    if price_now is not None and historical_prices:
        historical_max = max(historical_prices)
        if historical_max > 0:
            score += int(((historical_max - price_now) / historical_max) * 20)
        if math.isclose(price_now, min(historical_prices), rel_tol=0.001):
            score += 8
    score = max(0, min(100, score))

    previous_price = historical_prices[-2] if len(historical_prices) >= 2 else None
    change_amount = None if previous_price is None or price_now is None else round(price_now - previous_price, 2)
    change_percent = None
    if change_amount is not None and previous_price:
        change_percent = round(change_amount / previous_price * 100, 2)

    return {
        "observation_count": len(historical_prices),
        "current_price": price_now,
        "avg_price": round(sum(historical_prices) / len(historical_prices), 2),
        "median_price": round(float(median(historical_prices)), 2),
        "min_price": round(min(historical_prices), 2),
        "max_price": round(max(historical_prices), 2),
        "first_seen_at": item_snapshots[0].get("snapshot_time"),
        "last_seen_at": latest_item_snapshot.get("snapshot_time"),
        "market_avg_price": market_avg,
        "market_median_price": market_median,
        "price_change_amount": change_amount,
        "price_change_percent": change_percent,
        "deal_score": score,
        "deal_label": _resolve_deal_label(score),
    }


def build_market_reference(
    *,
    keyword: str,
    item: dict,
    current_market_items: list[dict],
    historical_snapshots: list[dict],
) -> dict:
    current_market_records = []
    for market_item in current_market_items:
        price = parse_price_value(market_item.get("当前售价"))
        if price is None:
            continue
        current_market_records.append({"price": price})

    market_snapshot = _summarize_prices(current_market_records)
    history_summary = _summarize_prices(_dedupe_latest(historical_snapshots, "item_id"))
    item_context = build_item_price_context(
        historical_snapshots,
        item_id=str(item.get("商品ID") or ""),
        current_price=parse_price_value(item.get("当前售价")),
    )
    return {
        "当前搜索样本": market_snapshot,
        "历史价格概览": history_summary,
        "本商品价格位置": item_context,
        "关键词": keyword,
    }


def build_price_history_insights(
    keyword: str,
    *,
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
    visible_item_ids: Optional[set[str]] = None,
    ai_item_ids_by_day: Optional[dict[str, set[str]]] = None,
) -> dict:
    snapshots = load_price_snapshots(keyword)
    if visible_item_ids is not None:
        snapshots = [
            snapshot
            for snapshot in snapshots
            if str(snapshot.get("item_id") or "") in visible_item_ids
        ]
    if not snapshots:
        return {
            "market_summary": _summarize_prices([]),
            "history_summary": {"unique_items": 0, **_summarize_prices([])},
            "daily_trend": [],
            "latest_snapshot_at": None,
        }

    recent_snapshots = _recent_window_snapshots(snapshots, window_days)
    latest_run_id = str(snapshots[-1].get("run_id") or "")
    latest_run_snapshots = _dedupe_latest(
        [record for record in snapshots if str(record.get("run_id") or "") == latest_run_id],
        "item_id",
    )
    latest_records_by_item = _dedupe_latest(recent_snapshots, "item_id")

    return {
        "market_summary": {
            **_summarize_prices(latest_run_snapshots),
            "snapshot_time": snapshots[-1].get("snapshot_time"),
        },
        "history_summary": {
            "unique_items": len(latest_records_by_item),
            **_summarize_prices(latest_records_by_item),
        },
        "daily_trend": _build_daily_trend(recent_snapshots, ai_item_ids_by_day),
        "latest_snapshot_at": snapshots[-1].get("snapshot_time"),
    }


def _is_strictly_decreasing(prices: list[float]) -> bool:
    """价格序列是否逐次下降（严格单调递减）。"""
    if len(prices) < 2:
        return False
    return all(prices[index] > prices[index + 1] for index in range(len(prices) - 1))


def _is_non_increasing(prices: list[float]) -> bool:
    """价格序列不递增（允许持平，但不允许上涨）。"""
    if len(prices) < 2:
        return False
    return all(prices[index] >= prices[index + 1] for index in range(len(prices) - 1))


def _has_any_drop(prices: list[float]) -> bool:
    """序列里是否至少有一次严格下跌（防止「跌完又横盘」伪入选）。"""
    if len(prices) < 2:
        return False
    return any(prices[index] > prices[index + 1] for index in range(len(prices) - 1))


def _is_overall_declining(min_series: list[dict]) -> bool:
    """用按日线性回归判断每日最低价曲线是否总体向下。

    允许中途短暂反弹，但要求回归斜率为负，且最新价低于首日价格，
    避免单个异常高点把横盘或总体上涨的曲线误判为下降。
    """
    if len(min_series) < 2:
        return False
    try:
        first_day = date.fromisoformat(str(min_series[0]["day"]))
        x_values = [
            (date.fromisoformat(str(point["day"])) - first_day).days
            for point in min_series
        ]
        y_values = [float(point["min_price"]) for point in min_series]
    except (KeyError, TypeError, ValueError):
        return False
    if len(set(x_values)) < 2 or y_values[-1] >= y_values[0]:
        return False
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    denominator = sum((value - x_mean) ** 2 for value in x_values)
    if denominator <= 0:
        return False
    slope = sum(
        (x_value - x_mean) * (y_value - y_mean)
        for x_value, y_value in zip(x_values, y_values)
    ) / denominator
    return slope < 0


def _days_between(start_day: str, end_day: str) -> int:
    """两个 YYYY-MM-DD 日期之间相差的天数（end - start）。"""
    try:
        return (date.fromisoformat(end_day) - date.fromisoformat(start_day)).days
    except ValueError:
        return 0


def _avg_daily_decline(
    min_series: list[dict],
    highest_min: float,
    latest_min: float,
) -> tuple[float, int]:
    """根据「最高价日 → 最新日」的天数差，计算平均每日下跌金额（元/天）。

    返回 (avg_daily_decline, decline_days)。
    decline_days == 0 时退回使用「累计跌幅」本身。
    """
    if highest_min <= latest_min:
        return 0.0, 0
    first_high_index = next(
        (i for i, point in enumerate(min_series) if point["min_price"] == highest_min),
        len(min_series) - 1,
    )
    high_day = min_series[first_high_index]["day"]
    latest_day = min_series[-1]["day"]
    decline_days = _days_between(high_day, latest_day)
    if decline_days <= 0:
        return round(highest_min - latest_min, 2), 0
    return round((highest_min - latest_min) / decline_days, 2), decline_days


def find_declining_dip_tasks(
    keyword_to_ai_ids: dict[str, set[str]],
    *,
    min_tail_points: int = 3,
    min_decline_percent: float = 8.0,
    min_decline_days: int = 3,
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
    max_results: int = 12,
) -> list[dict]:
    """按任务聚合的「持续下跌可抄底」榜单。

    入选条件（针对单个任务/关键词）：
    - keyword_to_ai_ids 提供每个关键词下 AI 推荐商品的 item_id 集合。
    - 在 window_days 窗口内的「每日最低价（仅统计 AI 推荐商品）」序列：
      * 至少 min_tail_points 个有效数据点；
      * 整个窗口按日期做线性回归后斜率为负，且最新价低于首日价格；
      * 较窗口内的「每日最低价」最大值累计下跌 ≥ min_decline_percent；
      * 跌幅期跨度（日历天数：最高价日 → 最新日）≥ min_decline_days，
        避免「单日峰值后回落」这种伪下跌被误判为持续下跌。

    返回按累计跌幅降序排列的最多 max_results 个任务，每个任务包含：
    task_id / task_name / keyword / latest_min_price / highest_min_price /
    decline_percent / avg_daily_decline / decline_days / trend（每日 min/avg
    序列）/ lowest_item（当前 AI 推荐商品里最低价的那一条）/
    first_seen_at / last_seen_at。
    """
    candidates: list[dict] = []
    for keyword, ai_ids in keyword_to_ai_ids.items():
        if not ai_ids:
            continue
        insights = build_price_history_insights(
            keyword, window_days=window_days, visible_item_ids=ai_ids
        )
        daily = insights.get("daily_trend") or []
        min_series = [
            {"day": str(point["day"]), "min_price": float(point["min_price"]),
             "avg_price": point.get("avg_price"), "sample_count": int(point.get("sample_count") or 0)}
            for point in daily
            if isinstance(point.get("min_price"), (int, float))
        ]
        if len(min_series) < min_tail_points:
            continue
        # 以整个窗口的回归趋势判断，允许中途短暂反弹，但总体必须持续走低。
        if not _is_overall_declining(min_series):
            continue
        highest_min = max(point["min_price"] for point in min_series)
        latest_min = min_series[-1]["min_price"]
        if highest_min <= 0:
            continue
        decline_percent = round((latest_min - highest_min) / highest_min * 100, 2)
        if decline_percent >= 0 or abs(decline_percent) < min_decline_percent:
            continue

        avg_daily_decline, decline_days = _avg_daily_decline(
            min_series, highest_min, latest_min
        )
        # 要求跌幅期跨越至少 min_decline_days 个日历日，
        # 避免「单日峰值→次日回落」这种伪下跌被算成持续下跌。
        if decline_days < min_decline_days:
            continue

        lowest_item = _find_lowest_ai_recommended_item(
            keyword=keyword, ai_ids=ai_ids, window_days=window_days
        )
        if not lowest_item:
            continue
        candidates.append(
            {
                "task_id": None,
                "task_name": keyword,
                "keyword": keyword,
                "latest_min_price": round(latest_min, 2),
                "latest_min_price_display": "",
                "highest_min_price": round(highest_min, 2),
                "decline_percent": decline_percent,
                "avg_daily_decline": avg_daily_decline,
                "decline_days": decline_days,
                "trend": [
                    {
                        "day": point["day"],
                        "min_price": round(point["min_price"], 2),
                        "avg_price": (
                            round(float(point["avg_price"]), 2)
                            if isinstance(point.get("avg_price"), (int, float))
                            else None
                        ),
                        "max_price": (
                            round(float(point["max_price"]), 2)
                            if isinstance(point.get("max_price"), (int, float))
                            else None
                        ),
                        "sample_count": point["sample_count"],
                    }
                    for point in min_series
                ],
                "lowest_item": lowest_item,
                "trend_points": len(min_series),
                "first_seen_at": min_series[0]["day"],
                "last_seen_at": min_series[-1]["day"],
            }
        )

    candidates.sort(key=lambda item: item["decline_percent"])
    return candidates[:max_results]


async def collect_keyword_to_ai_ids() -> dict[str, set[str]]:
    """异步收集每个关键词对应的 AI 推荐商品 ID 集合（合并多个结果文件）。"""
    from src.services.result_storage_service import (
        load_ai_recommended_item_ids,
        list_result_filenames,
        load_result_summary,
    )

    keyword_to_ai_ids: dict[str, set[str]] = {}
    try:
        filenames = await list_result_filenames()
    except Exception:
        filenames = []
    for filename in filenames:
        try:
            summary = await load_result_summary(filename)
        except Exception:
            continue
        if not summary:
            continue
        latest = summary.get("latest_record") or {}
        file_keyword = str(latest.get("搜索关键字") or "").strip()
        if not file_keyword:
            continue
        try:
            ai_ids = load_ai_recommended_item_ids(filename)
        except Exception:
            ai_ids = set()
        if ai_ids:
            keyword_to_ai_ids.setdefault(file_keyword, set()).update(ai_ids)
    return keyword_to_ai_ids


def _find_lowest_ai_recommended_item(
    *,
    keyword: str,
    ai_ids: set[str],
    window_days: int,
) -> dict | None:
    """在关键词对应的快照里，找出 AI 推荐商品中当前最低价的那一件。

    取窗口内最近一次爬取批次（latest run_id）里 AI 推荐商品的最低价；
    若 AI 推荐数量太少，回退到窗口内 AI 推荐的全局最低价。
    """
    if not ai_ids:
        return None
    snapshots = load_price_snapshots(keyword)
    if not snapshots:
        return None
    windowed = _recent_window_snapshots(snapshots, window_days)
    if not windowed:
        return None
    ai_filtered = [
        record for record in windowed if str(record.get("item_id") or "") in ai_ids
    ]
    if not ai_filtered:
        return None
    # 优先取最近一次 run_id（最贴近当前市场）的快照
    latest_run_id = str(windowed[-1].get("run_id") or "")
    latest_run_records = [
        record for record in ai_filtered if str(record.get("run_id") or "") == latest_run_id
    ]
    pool = latest_run_records or ai_filtered
    # 同 item_id 只保留最新一条
    deduped = _dedupe_latest(pool, "item_id")
    if not deduped:
        return None
    priced = [record for record in deduped if parse_price_value(record.get("price")) is not None]
    if not priced:
        return None
    priced.sort(key=lambda record: float(record["price"]))
    pick = priced[0]
    return {
        "item_id": str(pick.get("item_id") or ""),
        "title": str(pick.get("title") or ""),
        "price": round(float(pick["price"]), 2),
        "price_display": str(pick.get("price_display") or ""),
        "link": str(pick.get("link") or ""),
        "seller": str(pick.get("seller") or ""),
        "region": str(pick.get("region") or ""),
        "snapshot_time": str(pick.get("snapshot_time") or ""),
    }
