"""
デフォルト設定・閾値。
CLI引数で上書き可能な値はここに集約する。
"""

import json
from pathlib import Path

# 全国市区町村リスト(都道府県 → 市区町村名の配列)。
# data/municipalities.json は公開データセット(geolonia/japanese-addresses)を同梱したもの。
_MUNI_PATH = Path(__file__).parent / "municipalities.json"


def load_municipalities() -> dict:
    """{都道府県名: [市区町村名, ...]} を読み込む。ファイルが無ければ空。"""
    try:
        return json.loads(_MUNI_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# ── フィルタリングのデフォルト値 ──────────────────────────────
FILTER_DEFAULTS = {
    "has_website": False,               # False = website を持たない店舗のみ残す
    "min_reviews": 20,                  # 口コミ数の下限
    "max_reviews": 80,                  # 口コミ数の上限(中間ゾーンの目安)
    "min_rating": 3.5,                  # 評価点の下限
    "business_status": "OPERATIONAL",   # 営業中の店舗のみ
}

# 「正式なHPではない」とみなすドメイン。
# website にこれらのドメインしか入っていない場合は「HPなし寄り」として扱う。
SNS_ONLY_DOMAINS = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "twitter.com",
    "x.com",
    "tabelog.com",
    "hotpepper.jp",
    "gnavi.co.jp",
    "retty.me",
    "linktr.ee",
    "lit.link",
)

# ── スコアリングのパラメータ ─────────────────────────────────
SCORING = {
    "review_peak": 50,        # 口コミ数スコアが最大になる中心値
    "review_slope": 1.2,      # 中心から離れるほど減点する傾き
    "rating_floor": 3.0,      # この評価を 0 点とする
    "rating_ceiling": 4.5,    # この評価で満点(100)に到達
    "weight_review": 0.6,     # 合成時の口コミ数の重み
    "weight_rating": 0.4,     # 合成時の評価の重み
}

# ── 検索・API のデフォルト ───────────────────────────────────
SEARCH = {
    "included_type": "restaurant",  # Places API (New) の includedType
    "language_code": "ja",
    "region_code": "JP",
    "page_size": 20,                # 1リクエストあたりの取得件数(New APIは最大20)
    "max_results": 100,             # v1 の安全上限(コスト抑制)
    "request_interval_sec": 2.0,    # pageToken 取得後のウェイト(伝播待ち)
    "timeout_sec": 10,
    "max_retries": 3,
}

# 出力 CSV のカラム順
CSV_COLUMNS = [
    "エリア",
    "店舗名",
    "住所",
    "評価",
    "口コミ数",
    "スコア",
    "HP有無",
    "Instagram",
    "電話番号",
    "ステータス",
    "メモ",
    "GoogleマップURL",
    "Instagram検索",
]

# 業態の絞り込み(ラベル → Places API の includedType)。
# includedType が無いジャンルは "restaurant" のまま、ラベルを検索キーワードに足して絞る。
GENRES = {
    "(すべて)": None,
    "カフェ": "cafe",
    "バー": "bar",
    "ベーカリー": "bakery",
    "居酒屋": "restaurant",
    "ラーメン": "restaurant",
    "焼肉": "restaurant",
    "寿司": "restaurant",
    "イタリアン": "restaurant",
    "中華": "restaurant",
    "定食・食堂": "restaurant",
}

# 営業ステータスの選択肢と、「対応済み(次回除外の候補)」の定義
STATUS_OPTIONS = ["未対応", "架電済", "アポ", "成約", "NG"]
STATUS_DEFAULT = "未対応"
STATUS_DONE = ["成約", "NG"]  # 除外オプション ON のとき次回から隠す

# 都道府県(絞り込み用ドロップダウン)
PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]
