# 営業先自動選定ツール(sales-target-selector)

ホームページを持たない飲食店を Google Places API (New) で発見・スコアリングし、
優先度付きの営業候補リスト(CSV)を出力する CLI ツール。

## セットアップ

```bash
cd sales-target-selector
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt

copy .env.example .env         # Windows(macOS/Linux は cp)
# .env を開いて GOOGLE_PLACES_API_KEY を設定
```

Google Cloud Console 側の準備:
1. **Places API (New)** を有効化
2. API キーを発行(利用制限をかけることを推奨)
3. 請求先アカウントと予算アラートを設定(従量課金のため)

## 実行

```bash
python main.py --area "三軒茶屋" --min-reviews 20 --max-reviews 80 --min-rating 3.5
```

主なオプション:

| 引数 | 既定値 | 説明 |
|---|---|---|
| `--area` | (必須) | 検索エリア名 |
| `--query` | area から自動生成 | 検索クエリを直接指定 |
| `--min-reviews` | 20 | 口コミ数の下限 |
| `--max-reviews` | 80 | 口コミ数の上限 |
| `--min-rating` | 3.5 | 評価点の下限 |
| `--has-website` | (off) | 付けると「HPを持つ店舗」を抽出 |
| `--max-results` | 100 | 検索件数の上限(コスト抑制) |
| `--output` | `output/candidates_YYYYMMDD.csv` | 出力先 |

出力 CSV: `店舗名, 住所, 評価, 口コミ数, スコア, HP有無, 電話番号, GoogleマップURL`(スコア降順)

## テスト

```bash
python -m unittest discover tests
# または pytest
```

## 構成

```
sales-target-selector/
├── main.py              # CLI エントリーポイント / パイプライン
├── config.py            # 閾値・スコアリング・API のデフォルト
├── src/
│   ├── places_client.py # Places API (New) ラッパー(検索 + 詳細)
│   ├── filters.py       # HP有無判定・フィルタリング
│   ├── scoring.py       # スコアリング(山型カーブ)
│   └── exporter.py      # CSV 出力
├── tests/test_scoring.py
└── output/
```

## 設計上のメモ

- **Places API (New) を使用**:`POST /v1/places:searchText` と `GET /v1/places/{id}`。
  フィールドマスクで取得項目を絞り、課金SKUを抑える。
- **二段構え**:検索(基本項目)でフィルタしてから、
  通過した候補だけに詳細取得(電話番号)を行い API コストを削減。
- **SNSのみ判定**:`websiteUri` が Instagram / 食べログ等のみの場合は
  「HPなし寄り(SNSのみ)」として営業候補に残す(`config.SNS_ONLY_DOMAINS`)。
- **スコアリングは初期案**:口コミ 20〜80(ピーク50)を高評価する山型。
  営業成果が溜まり次第、重み調整・回帰モデルへ発展させる想定。
```
