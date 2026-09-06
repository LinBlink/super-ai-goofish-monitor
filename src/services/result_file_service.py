"""
结果记录富化与文件名校验服务
"""

from src.infrastructure.persistence.storage_names import normalize_keyword_from_filename
from src.services.price_history_service import (
    build_item_price_context,
    load_price_snapshots,
    parse_price_value,
)
from src.services.result_storage_service import load_visible_result_item_ids


def validate_result_filename(filename: str) -> None:
    if not filename.endswith(".jsonl") or "/" in filename or ".." in filename:
        raise ValueError("无效的文件名")


def enrich_records_with_price_insight(records: list[dict], filename: str) -> list[dict]:
    snapshots = load_price_snapshots(normalize_keyword_from_filename(filename))
    if not snapshots:
        return records

    visible_item_ids = load_visible_result_item_ids(filename)
    visible_snapshots = [
        snapshot
        for snapshot in snapshots
        if str(snapshot.get("item_id") or "") in visible_item_ids
    ]
    enriched = []
    for record in records:
        info = record.get("商品信息", {}) or {}
        clone = dict(record)
        item_id = str(info.get("商品ID") or "")
        latest_snapshot = next(
            (
                snapshot
                for snapshot in reversed(snapshots)
                if str(snapshot.get("item_id") or "") == item_id
            ),
            None,
        )
        if latest_snapshot is not None:
            clone["商品信息"] = {
                **info,
                "当前售价": latest_snapshot.get("price_display") or latest_snapshot.get("price"),
            }
        clone["price_insight"] = build_item_price_context(
            snapshots,
            item_id=item_id,
            current_price=(
                parse_price_value(latest_snapshot.get("price"))
                if latest_snapshot is not None
                else parse_price_value(info.get("当前售价"))
            ),
            market_snapshots=visible_snapshots,
        )
        enriched.append(clone)
    return enriched
