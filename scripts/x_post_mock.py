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

# Xのキーはモックでは使わないが、同一仕様のため読み取りは許容
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")

NOTION_VERSION = "2022-06-28"
USER_AGENT = "notion-x-mvp/1.0 (mock)"

DRY_RUN = True  # モックは常にドライラン

# ===== 共通ユーティリティ =====
def notify_slack(message: str):
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    res.raise_for_status()

def _np(prop, key, default=None):
    """安全にネストを取り出す（Notion property helper）"""
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

URL_RE = re.compile(r"https?://\S+")
def twitter_length(text: str) -> int:
    """t.co換算：URLは常に23文字としてカウント（実運用近似）"""
    return len(URL_RE.sub("x" * 23, text))

def build_tweet(title: str, summary: str, url: str) -> str:
    """タイトル優先、余裕があれば要約も。最後にURL。280字に丸める。"""
    title = (title or "").strip()
    summary = (summary or "").strip()
    url = (url or "").strip()

    # まずタイトル + URL
    base = f"{title}\n{url}" if title else url
    if twitter_length(base) <= 280 and summary:
        # 要約を1行差し込む
        candidate = f"{title}\n{summary}\n{url}" if title else f"{summary}\n{url}"
        if twitter_length(candidate) <= 280:
            return candidate
        # 収まらないなら要約を削って入るところまで
        # 余白計算
        remain = 280 - twitter_length(f"{title}\n\n{url}" if title else f"\n{url}") - 1
        # 安全側でマージン
        remain = max(remain, 0)
        trimmed = summary
        if len(trimmed) > remain:
            trimmed = trimmed[: max(remain - 1, 0)] + ("…" if remain > 0 else "")
        candidate = f"{title}\n{trimmed}\n{url}" if title else f"{trimmed}\n{url}"
        if twitter_length(candidate) <= 280:
            return candidate

    # 最低限、タイトル + URL で返す（またはURLのみ）
    # タイトルがオーバーするケースにも備え丸める
    if title:
        # 280 - URL(23) - 改行1
        max_title_len = 280 - 23 - 1
        if len(title) > max_title_len:
            title = title[: max_title_len - 1] + "…"
        return f"{title}\n{url}"
    return url

# ===== メイン =====
def main():
    try:
        pages = notion_query_approved_unposted()
        if not pages:
            notify_slack("（モック）X投稿対象は0件でした。")
            return

        preview_lines = []
        for p in pages:
            tweet = build_tweet(p["title"], p["summary"], p["url"])
            preview_lines.append(f"- {p['id']}: {tweet}")

        notify_slack("（モック）X投稿プレビュー:\n" + "\n".join(preview_lines[:10]) + ("" if len(preview_lines) <= 10 else "\n…"))
    except Exception as e:
        try:
            notify_slack(f"（モック）X投稿でエラー: {str(e)}")
        finally:
            raise

if __name__ == "__main__":
    main()
