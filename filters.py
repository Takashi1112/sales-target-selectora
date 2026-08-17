"""
HP有無の判定とフィルタリングロジック。

Places API (New) の Text Search レスポンス(places[])を入力とし、
「HPを持たない/SNSのみ」かつ条件を満たす飲食店だけを残す。
"""

from __future__ import annotations

from urllib.parse import urlparse

from config import SNS_ONLY_DOMAINS


def _domain_of(url: str) -> str:
    """URL からホスト名(先頭 www. を除去)を取り出す。"""
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def classify_website(website: str | None) -> str:
    """
    website フィールドを 3 分類する。
      - "none" : URL なし → HPなし
      - "sns"  : SNS/ポータルサイトのみ → HPなし寄り(営業対象として有力)
      - "own"  : 独自HPあり → 対象外寄り
    """
    if not website:
        return "none"
    domain = _domain_of(website)
    if not domain:
        return "none"
    if any(domain == d or domain.endswith("." + d) for d in SNS_ONLY_DOMAINS):
        return "sns"
    return "own"


def website_label(kind: str) -> str:
    """CSV 表示用のラベル。"""
    return {"none": "なし", "sns": "SNSのみ", "own": "あり"}.get(kind, "不明")


def instagram_status(website: str | None) -> str:
    """
    Google が持つ website リンクから Instagram の有無を判定する。
      - "あり"   : website が instagram.com のリンク
      - "要確認" : それ以外(Instagram をやっていても Google に無いだけの場合が多い)
    確実な有無判定は Google のデータだけでは不可能なため、
    "要確認" の店は CSV の Instagram検索リンクから 1 クリックで確認できるようにする。
    """
    if not website:
        return "要確認"
    domain = _domain_of(website)
    if domain == "instagram.com" or domain.endswith(".instagram.com"):
        return "あり"
    return "要確認"


def passes_filters(place: dict, opts: dict) -> tuple[bool, str]:
    """
    1店舗がフィルタを通過するか判定する。
    通過しない場合は理由を返す(デバッグ・集計用)。
    """
    # 営業状態
    if place.get("businessStatus") != opts["business_status"]:
        return False, "非営業"

    # HP有無:has_website=False のとき、独自HPありは除外
    kind = classify_website(place.get("websiteUri"))
    if opts["has_website"] is False and kind == "own":
        return False, "独自HPあり"
    if opts["has_website"] is True and kind != "own":
        return False, "HPなし"

    # 口コミ数(欠損は 0 扱い)
    reviews = place.get("userRatingCount") or 0
    if reviews < opts["min_reviews"]:
        return False, "口コミ数が下限未満"
    if reviews > opts["max_reviews"]:
        return False, "口コミ数が上限超過"

    # 評価(欠損は除外)
    rating = place.get("rating")
    if rating is None or rating < opts["min_rating"]:
        return False, "評価が下限未満"

    return True, "OK"


def apply_filters(places: list[dict], opts: dict) -> tuple[list[dict], dict]:
    """
    店舗リスト全体にフィルタを適用し、通過分と集計を返す。
    戻り値: (通過した places, 集計dict)
    """
    passed: list[dict] = []
    stats = {"total": len(places), "no_website": 0, "passed": 0, "reasons": {}}

    for place in places:
        if classify_website(place.get("websiteUri")) in ("none", "sns"):
            stats["no_website"] += 1
        ok, reason = passes_filters(place, opts)
        if ok:
            passed.append(place)
        else:
            stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1

    stats["passed"] = len(passed)
    return passed, stats
