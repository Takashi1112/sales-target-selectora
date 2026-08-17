"""
営業先自動選定ツール — エントリーポイント(CLI)。

パイプライン:
  Step1 検索   → Step2 詳細取得(候補のみ) → Step3 フィルタ
  → Step4 スコアリング → Step5 CSV 出力

使い方:
  python main.py --area "三軒茶屋" --min-reviews 20 --max-reviews 80 --min-rating 3.5
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from config import FILTER_DEFAULTS, SEARCH
from exporter import _display_name, export_csv
from pipeline import run_pipeline
from places_client import PlacesApiError

OUTPUT_DIR = Path(__file__).parent / "output"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ホームページ未保有の飲食店を営業候補として抽出する")
    p.add_argument("--area", required=True, help='検索エリア名(例:"三軒茶屋")')
    p.add_argument("--query", default=None, help="検索クエリを直接指定(省略時は area から自動生成)")
    p.add_argument("--min-reviews", type=int, default=FILTER_DEFAULTS["min_reviews"])
    p.add_argument("--max-reviews", type=int, default=FILTER_DEFAULTS["max_reviews"])
    p.add_argument("--min-rating", type=float, default=FILTER_DEFAULTS["min_rating"])
    p.add_argument(
        "--has-website",
        action="store_true",
        help="指定すると『HPを持つ店舗』を抽出(既定は HPなし店舗)",
    )
    p.add_argument("--max-results", type=int, default=SEARCH["max_results"])
    p.add_argument("--output", default=None, help="出力CSVパス(省略時は output/candidates_YYYYMMDD.csv)")
    return p


def resolve_output(arg_output: str | None) -> Path:
    if arg_output:
        return Path(arg_output)
    stamp = date.today().strftime("%Y%m%d")
    return OUTPUT_DIR / f"candidates_{stamp}.csv"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv()

    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")

    search_cfg = dict(SEARCH)
    search_cfg["max_results"] = args.max_results

    filter_opts = {
        "has_website": args.has_website,
        "min_reviews": args.min_reviews,
        "max_reviews": args.max_reviews,
        "min_rating": args.min_rating,
        "business_status": FILTER_DEFAULTS["business_status"],
    }

    query = args.query or f"{args.area} レストラン 飲食店"

    try:
        print(f"検索エリア: {args.area}")
        result = run_pipeline(api_key, query, filter_opts, search_cfg, area_label=args.area)
        scored = result["scored"]
        stats = result["stats"]

        print(f"取得件数: {result['fetched']}件(飲食店)")
        print(f"HPなし店舗: {stats['no_website']}件")
        print(f"フィルタ後候補: {stats['passed']}件")

        # コンソールサマリ(上位5件)
        print("スコア上位5件:")
        for i, place in enumerate(scored[:5], start=1):
            print(
                f"  {i}. {_display_name(place):<16} "
                f"評価{place.get('rating', '-')} / "
                f"口コミ{place.get('userRatingCount', 0)}件 / "
                f"スコア{place['score']}"
            )

        # Step5: 出力
        out_path = export_csv(scored, resolve_output(args.output))
        print(f"CSV出力完了: {out_path}")
        return 0

    except PlacesApiError as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
