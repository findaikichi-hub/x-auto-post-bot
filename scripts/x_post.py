import os
import re
import hmac
import time
import json
import base64
import hashlib
import random
import string
import urllib.parse
from datetime import datetime, timezone

import requests

# ===== Secrets（Actionsから注入）=====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

NOTION_VERSION = "2022-06-28"
USER_AGENT = "notion-x-mvp/1.0 (prod)"

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}  # 本番でも緊急時に有効化可

# ===== 共通ユーティリティ =====
def notify_slack(message: str):
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    res.raise_for_status()

def _np(prop, key, default=None):
    return (prop or {}).get(key, default)

def plain_title(prop):
    return "".join([_np(t, "plain_text", "") for t in (prop or {}).get("title", [])])

def plain_text(prop):
    return "".join([_np(t, "plain_text", "") for t in (prop or {}).get("rich_text", [])])

def notion_query_approved_unposted():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    payload = {
        "filter": {
            "and": [
                {"property": "Select", "select": {"equals": "approved"}},
                {"property": "Posted", "checkbox": {"equals": False}},
            ]
        }
    }

    results = []
    has_more = True
    next_cursor = None
    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    pages = []
    for page in results:
        props = page.get("properties", {})
        pages.append({
            "id": page.get("id"),
            "title": plain_title(props.get("Title")),
            "summary": plain_text(props.get("Summary")),
            "url": _np(props.get("URL"), "url", ""),
        })
    return pages

def notion_mark_posted(page_id: str, tweet_id: str):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "properties": {
            "Posted": {"checkbox": True},
            "TweetID": {"rich_text": [{"text": {"content": tweet_id}}]},
            "PostedAt": {"date": {"start": now_utc}},
        }
    }
    res = requests.patch(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()

URL_RE = re.compile(r"https?://\S+")
def twitter_length(text: str) -> int:
    return len(URL_RE.sub("x" * 23, text))

def build_tweet(title: str, summary: str, url: str) -> str:
    title = (title or "").strip()
    summary = (summary or "").strip()
    url = (url or "").strip()

    base = f"{title}\n{url}" if title else url
    if twitter_length(base) <= 280 and summary:
        candidate = f"{title}\n{summary}\n{url}" if title else f"{summary}\n{url}"
        if twitter_length(candidate) <= 280:
            return candidate
        remain = 280 - twitter_length(f"{title}\n\n{url}" if title else f"\n{url}") - 1
        remain = max(remain, 0)
        trimmed = summary
        if len(trimmed) > remain:
            trimmed = trimmed[: max(remain - 1, 0)] + ("…" if remain > 0 else "")
        candidate = f"{title}\n{trimmed}\n{url}" if title else f"{trimmed}\n{url}"
        if twitter_length(candidate) <= 280:
            return candidate

    if title:
        max_title_len = 280 - 23 - 1
        if len(title) > max_title_len:
            title = title[: max_title_len - 1] + "…"
        return f"{title}\n{url}"
    return url

# ===== OAuth 1.0a 署名 & 投稿 =====
def _percent_encode(s: str) -> str:
    return urllib.parse.quote(s, safe="~")

def _nonce(n: int = 32) -> str:
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

def _timestamp() -> str:
    return str(int(time.time()))

def sign_and_post_status(status_text: str) -> str:
    """
    v1.1 statuses/update.json に投稿し、ツイートID（文字列）を返す。
    失敗時は例外を送出。
    """
    url = "https://api.twitter.com/1.1/statuses/update.json"
    method = "POST"

    oauth_params = {
        "oauth_consumer_key": X_API_KEY,
        "oauth_nonce": _nonce(),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": _timestamp(),
        "oauth_token": X_ACCESS_TOKEN,
        "oauth_version": "1.0",
    }

    # パラメータ結合（POST bodyのstatusも署名対象）
    params = {**oauth_params, "status": status_text}
    # 署名用正規化
    sorted_items = sorted((k, v) for k, v in params.items())
    param_str = "&".join(f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted_items)

    base_str = "&".join([
        method,
        _percent_encode(url),
        _percent_encode(param_str),
    ])

    signing_key = "&".join([_percent_encode(X_API_SECRET), _percent_encode(X_ACCESS_SECRET)])
    digest = hmac.new(signing_key.encode("utf-8"), base_str.encode("utf-8"), hashlib.sha1).digest()
    signature = base64.b64encode(digest).decode("utf-8")

    oauth_params["oauth_signature"] = signature

    # Authorizationヘッダ作成（statusはボディ側）
    auth_header = "OAuth " + ", ".join([f'{_percent_encode(k)}="{_percent_encode(v)}"' for k, v in oauth_params.items()])
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
    }

    res = requests.post(url, headers=headers, data={"status": status_text}, timeout=30)
    if res.status_code >= 400:
        raise RuntimeError(f"X API error {res.status_code}: {res.text}")

    data = res.json()
    # v1.1 レスポンス: id_str がツイートID
    tweet_id = data.get("id_str") or str(data.get("id"))
    if not tweet_id:
        raise RuntimeError(f"Tweet posted but id is missing: {json.dumps(data)[:200]}")
    return tweet_id

# ===== メイン =====
def main():
    try:
        pages = notion_query_approved_unposted()
        if not pages:
            notify_slack("X投稿対象は0件でした。")
            return

        posted = 0
        previews = []

        for p in pages:
            tweet = build_tweet(p["title"], p["summary"], p["url"])
            if DRY_RUN:
                previews.append(f"- {p['id']}: {tweet}")
                continue

            try:
                tweet_id = sign_and_post_status(tweet)
                notion_mark_posted(p["id"], tweet_id)
                posted += 1
                previews.append(f"- OK {p['id']} → {tweet_id}")
            except Exception as e:
                previews.append(f"- NG {p['id']}: {str(e)}")

        if DRY_RUN:
            notify_slack("（DRY_RUN）X投稿プレビュー:\n" + "\n".join(previews[:10]) + ("" if len(previews) <= 10 else "\n…"))
        else:
            notify_slack(f"X投稿完了: {posted}件 / 対象 {len(pages)}件\n" + "\n".join(previews[:10]) +_
