"""
営業ステータスの永続化。
place_id をキーに「未対応/架電済/アポ/成約/NG」とメモをローカルの JSON に保存する。
検索を跨いで記録が残り、次回検索時に対応済みの店を自動除外できる。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

STORE_PATH = Path(__file__).resolve().parent / "status_store.json"


def load_statuses() -> dict:
    """{place_id: {"status": ..., "memo": ..., "updated": ...}} を読み込む。"""
    if not STORE_PATH.exists():
        return {}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_statuses(data: dict) -> None:
    """ステータス辞書をファイルに書き出す。"""
    STORE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def update_status(data: dict, place_id: str, status: str, memo: str) -> None:
    """1件分のステータスを辞書に反映(空・未対応かつメモ無しなら記録から削除)。"""
    if not place_id:
        return
    if status in ("", "未対応") and not (memo or "").strip():
        data.pop(place_id, None)
        return
    data[place_id] = {
        "status": status,
        "memo": (memo or "").strip(),
        "updated": date.today().isoformat(),
    }


def done_ids(data: dict, done_statuses: list[str]) -> set[str]:
    """対応済み(除外対象)の place_id 集合を返す。"""
    return {
        pid for pid, rec in data.items() if rec.get("status") in done_statuses
    }
