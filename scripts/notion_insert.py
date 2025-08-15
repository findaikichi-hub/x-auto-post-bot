import os
import feedparser
import requests
from scripts.notion_mock import fetch_existing_urls_mock, insert_to_notion_mock

# ==== 環境変数 ====
USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
RSS_URL = os.getenv("RSS_URL")

if not USE_MOCK:
    if not all([NOTION_API_KEY, NOTION_DATABASE_ID, DEEPL_API_KEY, RSS_URL]):
        raise ValueError("Missing required environment variables for production mode.")

# ==== 翻訳処理 ====
def translate_text(text, target_lang="JA"):
    if USE_MOCK:
        return f"[MOCK_TRANSLATION] {text}"
    url = "https://api-free.deepl.com/v2/translate"
    data = {"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang}
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["translations"][0]["text"]

# ==== Notion既存URL取得 ====
def fetch_existing_urls():
    if USE_MOCK:
        return fetch_existing_urls_mock()
    notion_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    has_more = True
    next_cursor = None
    urls = set()

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        response = requests.post(notion_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        for r in data.get("results", []):
            url_prop = r["properties"].get("URL", {}).get("url")
            if url_prop:
                urls.add(url_prop)
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return urls

# ==== Notion登録 ====
def add_to_notion(title, url, summary):
    if USE_MOCK:
        return insert_to_notion_mock(title, url)
    notion_url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url},
            "Status": {"select": {"name": "draft"}},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": summary}}]},
            }
        ],
    }
    response = requests.post(notion_url, headers=headers, json=data)
    response.raise_for_status()
    print(f"✅ Added to Notion: {title}")

# ==== メイン処理 ====
def main():
    existing_urls = fetch_existing_urls()
    print(f"[INFO] Found {len(existing_urls)} existing URLs in Notion")

    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries[:5]:
        if entry.link in existing_urls:
            print(f"⏩ Skipping duplicate: {entry.link}")
            continue
        title_translated = translate_text(entry.title)
        summary_translated = translate_text(entry.summary)
        add_to_notion(title_translated, entry.link, summary_translated)

if __name__ == "__main__":
    main()
