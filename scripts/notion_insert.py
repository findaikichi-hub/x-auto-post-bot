import os
import sys
import json
import time
import traceback
import feedparser
import requests
from typing import Optional

try:
    from deep_translator import DeeplTranslator, GoogleTranslator
except Exception:
    DeeplTranslator = None  # type: ignore
    GoogleTranslator = None  # type: ignore

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_QUERY_URL_FMT = "https://api.notion.com/v1/databases/{db}/query"
NOTION_VERSION = "2022-06-28"

# Notion DB のプロパティ名（DB側と一致させる）
PROP_NAME = "Name"        # title
PROP_URL = "URL"          # url
PROP_SUMMARY = "Summary"  # rich_text


def get_env(name: str, required: bool = False) -> Optional[str]:
    val = os.environ.get(name)
    if required and (val is None or val.strip() == ""):
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return val


def notion_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def translate_text(text: str, deepl_key: Optional[str]) -> str:
    if not text:
        return ""
    # deep_translator は小文字 or auto 指定
    if deepl_key and DeeplTranslator is not None:
        try:
            return DeeplTranslator(api_key=deepl_key, source="auto", target="ja").translate(text)
        except Exception:
            pass
    if GoogleTranslator is not None:
        try:
            return GoogleTranslator(source="auto", target="ja").translate(text)
        except Exception:
            pass
    return text


def parse_feed(rss_url: str):
    feed = feedparser.parse(rss_url)
    if getattr(feed, "bozo", 0):
        raise RuntimeError(f"Failed to parse RSS: {getattr(feed, 'bozo_exception', 'unknown error')}")
    return getattr(feed, "entries", [])


def is_url_already_registered(url: str, token: str, db_id: str) -> bool:
    query_url = NOTION_QUERY_URL_FMT.format(db=db_id)
    headers = notion_headers(token)
    payload = {
        "filter": {
            "property": PROP_URL,
            "url": {"equals": url}
        }
    }
    res = requests.post(query_url, headers=headers, json=payload, timeout=30)
    if res.status_code == 429:
        time.sleep(2)
        res = requests.post(query_url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    return len(res.json().get("results", [])) > 0


def add_page_to_notion(title: str, url: str, summary: str, token: str, db_id: str) -> None:
    headers = notion_headers(token)
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            PROP_NAME: {"title": [{"text": {"content": title}}]},
            PROP_URL: {"url": url},
            PROP_SUMMARY: {"rich_text": [{"text": {"content": summary}}]},
        },
    }
    res = requests.post(NOTION_API_URL, headers=headers, json=payload, timeout=30)
    if res.status_code == 429:
        time.sleep(2)
        res = requests.post(NOTION_API_URL, headers=headers, json=payload, timeout=30)
    if res.status_code >= 400:
        try:
            print(f"Notion API error ({res.status_code})")
            print(res.text)
        finally:
            res.raise_for_status()


def main() -> int:
    try:
        token = get_env("NOTION_API_KEY", required=True)
        db_id = get_env("NOTION_DATABASE_ID", required=True)
        rss_url = get_env("RSS_URL", required=True)
        deepl_key = get_env("DEEPL_API_KEY", required=True)

        entries = parse_feed(rss_url)
        if not entries:
            print("RSS に記事がありません。処理を終了します。")
            print(json.dumps({"result": {"processed": 0, "created": 0, "skipped": 0}}, ensure_ascii=False))
            return 0

        created, skipped = 0, 0
        for e in entries:
            title = getattr(e, "title", "").strip()
            url = getattr(e, "link", "").strip()
            summary_raw = getattr(e, "summary", "") or getattr(e, "description", "")
            if not title or not url:
                print(f"skip (title/url missing): title='{title}', url='{url}'")
                skipped += 1
                continue

            if is_url_already_registered(url, token, db_id):
                print(f"⚠️ 既存URLのためスキップ: {url}")
                skipped += 1
                continue

            summary_ja = translate_text(summary_raw, deepl_key)
            add_page_to_notion(title, url, summary_ja, token, db_id)
            print(f"✅ 登録完了: {title}")
            created += 1

        print(json.dumps({"result": {"processed": len(entries), "created": created, "skipped": skipped}}, ensure_ascii=False))
        return 0
    except Exception as e:
        print("=== PRODUCTION execution failed ===")
        print(str(e))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
