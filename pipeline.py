"""
検索〜スコアリングまでの一連の処理をまとめた共通パイプライン。
CLI(main.py)と Web画面(app.py)の両方から呼び出す。
"""

from __future__ import annotations

from filters import apply_filters
from places_client import PlacesClient
from scoring import score_places


def run_pipeline(
    api_key: str,
    query: str,
    filter_opts: dict,
    search_cfg: dict,
    fetch_phone: bool = True,
    area_label: str = "",
    exclude_ids: set[str] | None = None,
    included_type: str | None = None,
) -> dict:
    """
    Step1 検索 → Step3 フィルタ → Step2 詳細(電話番号) → Step4 スコアリング。

    area_label   : 各店に付けるエリア名(複数エリア一括検索でどの街か分かるように)
    exclude_ids  : 除外する place_id 集合(対応済みの店を隠す用)
    included_type: この検索だけ includedType を上書き(業態絞り込み用)

    戻り値:
      {
        "fetched": 取得件数,
        "stats":   フィルタ集計(no_website / passed / reasons),
        "scored":  スコア付き・降順ソート済みの候補リスト,
      }
    """
    if included_type is not None:
        search_cfg = {**search_cfg, "included_type": included_type}
    client = PlacesClient(api_key, search_cfg)

    # Step1: 検索
    places = client.search_text(query)

    # Step3: フィルタ(電話番号取得の前に絞ってコスト削減)
    passed, stats = apply_filters(places, filter_opts)

    # 対応済みの店を除外
    if exclude_ids:
        passed = [p for p in passed if p.get("id") not in exclude_ids]

    # エリア名を各店に付与
    for p in passed:
        p["_area"] = area_label

    # Step2: 詳細取得(候補のみ、電話番号を付与)
    if fetch_phone and passed:
        for place, details in zip(
            passed, client.iter_details([p["id"] for p in passed])
        ):
            if details.get("nationalPhoneNumber"):
                place["nationalPhoneNumber"] = details["nationalPhoneNumber"]

    # Step4: スコアリング
    scored = score_places(passed)

    return {"fetched": len(places), "stats": stats, "scored": scored}
