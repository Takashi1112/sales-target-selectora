"""
営業先自動選定ツール — Web画面(Streamlit)。

起動:
  streamlit run app.py
  （または 起動.bat をダブルクリック)

機能:
  - 都道府県 + 市区町村/エリア + 業態 で検索
  - 複数エリアをまとめて検索(1行に1エリア)
  - ホームページなし・Instagram有無の判定
  - 営業ステータス(未対応/架電済/アポ/成約/NG)とメモを記録・保存
    → 次回検索で「対応済み(成約/NG)」を自動除外できる
  - 結果を表で表示・CSVダウンロード
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import (
    FILTER_DEFAULTS,
    GENRES,
    PREFECTURES,
    SEARCH,
    STATUS_DONE,
    STATUS_OPTIONS,
    load_municipalities,
)
from exporter import export_csv, to_row
from pipeline import run_pipeline
from places_client import PlacesApiError
from status_store import done_ids, load_statuses, save_statuses, update_status

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
OUTPUT_DIR = BASE_DIR / "output"
MUNICIPALITIES = load_municipalities()

st.set_page_config(page_title="営業先自動選定ツール", page_icon="🍽️", layout="wide")
st.title("🍽️ 営業先自動選定ツール")
st.caption("ホームページを持たない飲食店を見つけて、営業候補リストを作ります。")

# ── サイドバー:検索条件 ──────────────────────────────────────
with st.sidebar:
    st.header("検索条件")
    prefecture = st.selectbox("都道府県", ["(指定なし)"] + PREFECTURES, index=0)

    munis = MUNICIPALITIES.get(prefecture, []) if prefecture != "(指定なし)" else []
    city = st.selectbox(
        "市区町村",
        ["(すべて)"] + munis,
        index=0,
        disabled=not munis,
        help="都道府県を選ぶと、その市区町村を選べます",
    )
    detail = st.text_input(
        "詳細エリア(任意)",
        value="",
        placeholder="例:三軒茶屋 / 野毛 など町名・駅名",
        help="市区町村より細かく絞りたいときに入力",
    )
    genre = st.selectbox("業態", list(GENRES.keys()), index=0)
    multi_areas = st.text_area(
        "複数エリアをまとめて検索(任意)",
        value="",
        placeholder="1行に1エリア。例:\n静岡市\n浜松市\n沼津市",
        help="ここに入力すると、上の『市区町村・エリア』の代わりに各行をまとめて検索します(都道府県を選んでいれば各行の頭に付きます)",
    )
    max_results = st.slider(
        "取得件数(エリアごと)", min_value=10, max_value=100, value=40, step=10,
        help="多いほど候補は増えますが、時間とAPI費用も増えます",
    )
    st.divider()
    min_reviews = st.number_input("口コミ数の下限", 0, 5000, FILTER_DEFAULTS["min_reviews"])
    max_reviews = st.number_input("口コミ数の上限", 0, 5000, FILTER_DEFAULTS["max_reviews"])
    min_rating = st.slider("評価の下限", 0.0, 5.0, float(FILTER_DEFAULTS["min_rating"]), step=0.1)
    exclude_done = st.checkbox(
        "対応済み(成約・NG)を除外", value=True,
        help="過去にステータスを『成約』『NG』にした店を結果から隠します",
    )
    run = st.button("この条件で検索", type="primary", use_container_width=True)

def get_api_key() -> str:
    """APIキーを取得する。
    クラウド(Streamlit Cloud)では Secrets を、ローカルでは .env(環境変数)を使う。
    """
    try:
        if "GOOGLE_PLACES_API_KEY" in st.secrets:
            return str(st.secrets["GOOGLE_PLACES_API_KEY"])
    except Exception:
        pass  # secrets 未設定のローカル環境では例外になるので無視
    return os.getenv("GOOGLE_PLACES_API_KEY", "")


api_key = get_api_key()

if not api_key:
    st.error(
        "APIキーが設定されていません。"
        "クラウドでは Streamlit の Secrets に、ローカルでは `.env` に "
        "`GOOGLE_PLACES_API_KEY` を設定してください。"
    )
    st.stop()


def build_area_list() -> list[str]:
    """入力から検索対象エリアのリストを作る。"""
    pref = "" if prefecture == "(指定なし)" else prefecture
    lines = [ln.strip() for ln in multi_areas.splitlines() if ln.strip()]
    if lines:
        # 複数エリア:各行の頭に都道府県を付ける
        return [f"{pref}{ln}" for ln in lines]
    muni = "" if city == "(すべて)" else city
    single = f"{pref}{muni}{detail.strip()}"
    return [single] if single else []


# ── 検索実行 ────────────────────────────────────────────────
if run:
    areas = build_area_list()
    if not areas:
        st.warning("都道府県か、市区町村・エリア名(または複数エリア)を入力してください。")
        st.stop()

    genre_type = GENRES[genre]
    genre_kw = "" if genre == "(すべて)" else genre

    search_cfg = dict(SEARCH)
    search_cfg["max_results"] = max_results
    filter_opts = {
        "has_website": False,
        "min_reviews": min_reviews,
        "max_reviews": max_reviews,
        "min_rating": min_rating,
        "business_status": FILTER_DEFAULTS["business_status"],
    }
    statuses = load_statuses()
    exclude = done_ids(statuses, STATUS_DONE) if exclude_done else set()

    all_scored: list[dict] = []
    total_fetched = total_no_website = 0
    prog = st.progress(0.0, text="検索中…")
    try:
        for i, area in enumerate(areas):
            prog.progress(i / len(areas), text=f"「{area}」を検索中…")
            query = " ".join(x for x in [area, genre_kw, "飲食店 レストラン"] if x)
            result = run_pipeline(
                api_key, query, filter_opts, search_cfg,
                area_label=area, exclude_ids=exclude, included_type=genre_type,
            )
            total_fetched += result["fetched"]
            total_no_website += result["stats"]["no_website"]
            all_scored.extend(result["scored"])
    except PlacesApiError as exc:
        prog.empty()
        st.error(f"エラー: {exc}")
        st.stop()
    prog.empty()

    # 全エリア合算でスコア降順に並べ替え
    all_scored.sort(key=lambda p: p.get("score", 0), reverse=True)

    label = areas[0] if len(areas) == 1 else f"{len(areas)}エリア"
    st.session_state["results"] = {
        "scored": all_scored,
        "fetched": total_fetched,
        "no_website": total_no_website,
        "passed": len(all_scored),
        "label": label,
    }

# ── 結果表示(session_state から。保存ボタンで再実行されても消えない) ──
results = st.session_state.get("results")
if not results:
    st.info("← 左のサイドバーで条件を決めて「この条件で検索」を押してください。")
    st.stop()

scored = results["scored"]

c1, c2, c3 = st.columns(3)
c1.metric("取得件数", f"{results['fetched']}件")
c2.metric("HPなし店舗", f"{results['no_website']}件")
c3.metric("営業候補", f"{results['passed']}件")

if not scored:
    st.info("条件に合う候補がありませんでした。取得件数を増やすか、条件を緩めてみてください。")
    st.stop()

# 保存済みステータス・メモを各店にマージ
statuses = load_statuses()
for p in scored:
    rec = statuses.get(p.get("id", ""), {})
    p["_status"] = rec.get("status", "未対応")
    p["_memo"] = rec.get("memo", "")

rows = [to_row(p) for p in scored]
df = pd.DataFrame(rows)

st.markdown("#### 営業候補リスト（ステータスとメモは直接編集できます）")
editable = ["ステータス", "メモ"]
edited = st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    disabled=[c for c in df.columns if c not in editable],
    column_config={
        "GoogleマップURL": st.column_config.LinkColumn("地図", display_text="開く"),
        "Instagram検索": st.column_config.LinkColumn("IG確認", display_text="検索"),
        "評価": st.column_config.NumberColumn(format="%.1f"),
        "ステータス": st.column_config.SelectboxColumn("ステータス", options=STATUS_OPTIONS),
    },
)

col_save, col_dl = st.columns([1, 1])

with col_save:
    if st.button("💾 ステータスを保存", use_container_width=True):
        for p, (_, row) in zip(scored, edited.iterrows()):
            update_status(statuses, p.get("id", ""), row["ステータス"], row.get("メモ", ""))
        save_statuses(statuses)
        st.success("保存しました。次回検索から反映されます。")

with col_dl:
    stamp = date.today().strftime("%Y%m%d")
    safe = results["label"].replace(" ", "_").replace("　", "_")
    out_path = export_csv(scored, OUTPUT_DIR / f"candidates_{safe}_{stamp}.csv")
    st.download_button(
        "📥 CSVをダウンロード",
        data=out_path.read_bytes(),
        file_name=out_path.name,
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )
st.caption(f"CSV保存先: {out_path}　※ステータスは「保存」した内容がCSVにも反映されます")
