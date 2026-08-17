"""
営業提案の「刺さりやすさ」を数値化するスコアリングロジック。

初期案:口コミ数の中間ゾーン(既定 20〜80、ピーク50件)を最も高くする山型カーブ。
将来的には営業成果データを蓄積し、重み調整・回帰モデルへ発展させる想定(設計書 §8)。
"""

from __future__ import annotations

from config import SCORING


def calculate_score(
    rating: float | None,
    review_count: int | None,
    params: dict = SCORING,
) -> float:
    """
    評価点と口コミ数から優先度スコア(0〜100)を算出する。

    - 口コミ数スコア: review_peak に近いほど高い山型カーブ
    - 評価スコア    : rating_floor で 0、rating_ceiling 以上で 100
    - 合成          : weight_review : weight_rating の加重平均
    """
    rating = rating or 0.0
    review_count = review_count or 0

    # 口コミ数スコア(山型)
    review_score = 100 - abs(review_count - params["review_peak"]) * params["review_slope"]
    review_score = max(review_score, 0.0)

    # 評価スコア(下限〜上限で 0〜100 に正規化)
    span = params["rating_ceiling"] - params["rating_floor"]
    rating_score = (rating - params["rating_floor"]) / span * 100
    rating_score = min(max(rating_score, 0.0), 100.0)

    total = review_score * params["weight_review"] + rating_score * params["weight_rating"]
    return round(total, 1)


def score_places(places: list[dict]) -> list[dict]:
    """
    places に score を付与し、スコア降順でソートして返す。
    元の dict は変更せず、score キーを足したコピーを返す。
    """
    scored = []
    for place in places:
        item = dict(place)
        item["score"] = calculate_score(
            place.get("rating"), place.get("userRatingCount")
        )
        scored.append(item)
    scored.sort(key=lambda p: p["score"], reverse=True)
    return scored
