"""
Google Places API (New) の呼び出しラッパー。

エンドポイント:
  - Text Search : POST https://places.googleapis.com/v1/places:searchText
  - Place Details: GET  https://places.googleapis.com/v1/places/{place_id}

New API ではフィールドマスク(X-Goog-FieldMask)で取得項目を指定する。
取得項目が増えるほど課金SKUが上がるため、
  Step1(検索)は基本項目のみ、
  Step2(詳細)はフィルタ後の候補に対してのみ電話番号を取得する。
という二段構えでコストを抑える。
"""

from __future__ import annotations

import time
from typing import Iterator

import requests

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Step1 検索で取得する基本フィールド
SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.rating",
        "places.userRatingCount",
        "places.websiteUri",
        "places.businessStatus",
        "places.types",
    ]
)

# Step2 詳細で追加取得するフィールド(電話番号など)
DETAILS_FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "nationalPhoneNumber",
        "internationalPhoneNumber",
        "websiteUri",
    ]
)


class PlacesApiError(RuntimeError):
    """API 呼び出しに関する例外。"""


class PlacesClient:
    def __init__(self, api_key: str, search_config: dict):
        if not api_key:
            raise PlacesApiError(
                "GOOGLE_PLACES_API_KEY が設定されていません。.env を確認してください。"
            )
        self._api_key = api_key
        self._cfg = search_config
        self._session = requests.Session()

    # ── 内部ヘルパ ────────────────────────────────────────────
    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        """リトライ付き POST。"""
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg["max_retries"] + 1):
            try:
                resp = self._session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._cfg["timeout_sec"],
                )
                if resp.status_code == 200:
                    return resp.json()
                # レート制限・一時的エラーはリトライ対象
                if resp.status_code in (429, 500, 503):
                    last_exc = PlacesApiError(
                        f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    time.sleep(self._cfg["request_interval_sec"] * attempt)
                    continue
                # それ以外(400/401/403 など)は即座に失敗
                raise PlacesApiError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(self._cfg["request_interval_sec"] * attempt)
        raise PlacesApiError(f"リトライ上限に達しました: {last_exc}")

    def _get(self, url: str, headers: dict) -> dict:
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg["max_retries"] + 1):
            try:
                resp = self._session.get(
                    url, headers=headers, timeout=self._cfg["timeout_sec"]
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code in (429, 500, 503):
                    last_exc = PlacesApiError(
                        f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    time.sleep(self._cfg["request_interval_sec"] * attempt)
                    continue
                raise PlacesApiError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(self._cfg["request_interval_sec"] * attempt)
        raise PlacesApiError(f"リトライ上限に達しました: {last_exc}")

    # ── Step1: Text Search ───────────────────────────────────
    def search_text(self, text_query: str) -> list[dict]:
        """
        テキストクエリで飲食店を検索し、基本情報のリストを返す。
        max_results に達するまで pageToken でページングする。
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": f"{SEARCH_FIELD_MASK},nextPageToken",
        }
        results: list[dict] = []
        page_token: str | None = None

        while len(results) < self._cfg["max_results"]:
            payload: dict = {
                "textQuery": text_query,
                "includedType": self._cfg["included_type"],
                "languageCode": self._cfg["language_code"],
                "regionCode": self._cfg["region_code"],
                "pageSize": self._cfg["page_size"],
            }
            if page_token:
                payload["pageToken"] = page_token

            data = self._post(SEARCH_URL, headers, payload)
            results.extend(data.get("places", []))

            page_token = data.get("nextPageToken")
            if not page_token:
                break
            # nextPageToken は発行直後だと無効なことがあるため待機
            time.sleep(self._cfg["request_interval_sec"])

        return results[: self._cfg["max_results"]]

    # ── Step2: Place Details ─────────────────────────────────
    def get_details(self, place_id: str) -> dict:
        """1店舗の詳細(電話番号など)を取得する。"""
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": DETAILS_FIELD_MASK,
        }
        return self._get(DETAILS_URL.format(place_id=place_id), headers)

    def iter_details(self, place_ids: list[str]) -> Iterator[dict]:
        """複数店舗の詳細を順次取得(レート制限回避のためウェイトを挟む)。"""
        for pid in place_ids:
            yield self.get_details(pid)
            time.sleep(self._cfg["request_interval_sec"])
