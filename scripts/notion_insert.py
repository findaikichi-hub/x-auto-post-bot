import os
import requests
import feedparser
from deep_translator import DeeplTranslator

# === 環境変数から取得（Repository secrets 経由） ===
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
DEEPL_API_KEY = os.environ["DEEPL_API_KEY"]
RSS_URL = os.environ["RSS_URL"]

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_QUERY_URL = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

# === 共通ヘッダー ===
headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def is_url_already_registered(url: str) -> bool:
    """Notion DB に同じ URL が登録済みか確認"""
    query = {
        "filter": {
            "property": "URL",
            "url": {
                "equals": url
            }
        }
    }
    res = requests.post(NOTION_QUERY_URL, headers=headers, json=query)
    res.raise_for_status()
    return len(res.json().get("results", [])) > 0

def add_page_to_notion(title: str, url: str, summary: str):
    """記事を Notion に登録"""
    if is_url_already_registered(url):
        print(f"⚠️ 既存URLのためスキップ: {url}")
        return

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url},
            "Summary": {"rich_text": [{"text": {"content": summary}}]}
        }
    }
    res = requests.post(NOTION_API_URL, headers=headers, json=payload)
    if res.status_code != 200:
        print("Notion API error:", res.status_code, res.text)
    res.raise_for_status()
    print(f"✅ 登録完了: {title}")

def translate_text(text: str) -> str:
    """DeepL APIで翻訳（英語→日本語）"""
    translator = DeeplTranslator(api_key=DEEPL_API_KEY, source="en", target="ja")
    return translator.translate(text)

def fetch_and_register_articles():
    """RSSから記事を取得してNotionに登録"""
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        title = entry.title
        url = entry.link
        summary_raw = getattr(entry, "summary", "")
        summary_ja = translate_text(summary_raw) if summary_raw else ""
        add_page_to_notion(title, url, summary_ja)

if __name__ == "__main__":
    print("=== 本番 Notion 登録開始 ===")
    fetch_and_register_articles()
    print("=== 本番 Notion 登録完了 ===")
