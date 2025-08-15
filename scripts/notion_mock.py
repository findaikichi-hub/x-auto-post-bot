import os
import sys
import requests
import feedparser
from deep_translator import DeeplTranslator

# ===== 環境変数チェック =====
required_envs = [
    "NOTION_API_KEY",
    "NOTION_DATABASE_ID",
    "DEEPL_API_KEY",
    "RSS_URL"
]
missing = [var for var in required_envs if not os.environ.get(var)]
if missing:
    print(f"❌ 必須環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

# ===== 環境変数読み込み =====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
DEEPL_API_KEY = os.environ["DEEPL_API_KEY"]
RSS_URL = os.environ["RSS_URL"]

NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_QUERY_URL = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def is_url_already_registered(url: str) -> bool:
    query = {
        "filter": {
            "property": "URL",
            "url": {
                "equals": url
            }
        }
    }
    response = requests.post(NOTION_QUERY_URL, headers=headers, json=query)
    response.raise_for_status()
    return len(response.json().get("results", [])) > 0

def add_page_to_notion(title: str, url: str, summary: str):
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
    response = requests.post(NOTION_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    print(f"✅ 登録完了: {title}")

def translate_text(text: str) -> str:
    translator = DeeplTranslator(api_key=DEEPL_API_KEY, source="EN", target="JA")
    return translator.translate(text)

def fetch_and_register_articles():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        title = entry.title
        url = entry.link
        summary = translate_text(entry.summary)
        add_page_to_notion(title, url, summary)

if __name__ == "__main__":
    fetch_and_register_articles()
