"""
CSV 出力処理。スコア降順の候補リストをファイルに書き出す。
"""

from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import quote_plus

from config import CSV_COLUMNS
from filters import classify_website, instagram_status, website_label

# place_id から GoogleマップURL を組み立てる
MAPS_URL = "https://www.google.com/maps/search/?api=1&query=Google&query_place_id={pid}"

# 店名から Instagram をワンクリック確認するための検索URL
INSTAGRAM_SEARCH_URL = "https://www.google.com/search?q={q}"


def instagram_search_url(name: str) -> str:
    """店名で「〇〇 Instagram」を Google 検索するURLを作る。"""
    if not name:
        return ""
    return INSTAGRAM_SEARCH_URL.format(q=quote_plus(f"{name} Instagram"))


def _display_name(place: dict) -> str:
    name = place.get("displayName")
    if isinstance(name, dict):
        return name.get("text", "")
    return name or ""


def to_row(place: dict) -> dict:
    """1 件の place(score・詳細付き)を CSV 行に整形する。"""
    website = place.get("websiteUri")
    kind = classify_website(website)
    name = _display_name(place)
    return {
        "エリア": place.get("_area", ""),
        "店舗名": name,
        "住所": place.get("formattedAddress", ""),
        "評価": place.get("rating", ""),
        "口コミ数": place.get("userRatingCount", ""),
        "スコア": place.get("score", ""),
        "HP有無": website_label(kind),
        "Instagram": instagram_status(website),
        "電話番号": place.get("nationalPhoneNumber", ""),
        "ステータス": place.get("_status", ""),
        "メモ": place.get("_memo", ""),
        "GoogleマップURL": MAPS_URL.format(pid=place.get("id", "")),
        "Instagram検索": instagram_search_url(name),
    }


def export_csv(places: list[dict], output_path: str | Path) -> Path:
    """places を CSV に書き出し、書き込んだパスを返す。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Excel で文字化けしないよう BOM 付き UTF-8 で保存
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for place in places:
            writer.writerow(to_row(place))

    return path
