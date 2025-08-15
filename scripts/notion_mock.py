import os
import sys
import requests
import feedparser

# deep_translator はインストール検証済みだが、念のため実行時も明示チェック
try:
    from deep_translator import DeeplTranslator
except Exception as e:
    print("❌ deep_translator の読み込みに失敗しました。ワークフローの依存インストール手順を確認してください。", file=sys.stderr)
    raise

# ===== 環境変数チェック =====
required_envs = ["NOTION_API_KEY", "NOTION_DATABASE_ID", "DEEPL_API_KEY", "RSS_URL"]
missing = [v for v in required_envs if not os.environ.get(v)]
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
    "Notion-Version": "2022-06-28",
}

def is_url_already_registered(url: str) -> bool:
    query = {
        "filter": {
            "property": "URL",
            "url": {"equals": url}
        }
    }
    resp = requests.post(NOTION_QUERY_URL, headers=headers, json=query, timeout=30)
    resp.raise_for_status()
    return len(resp.json().get("results", [])) > 0

def add_page_to_notion(title: str, url: str, summary: str):
    if is_url_already_registered(url):
        print(f"⚠️ 既存URLのためスキップ: {url}")
        return
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
        },
    }
    resp = requests.post(NOTION_API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"✅ 登録完了: {title}")

def translate_text(text: str) -> str:
    translator = DeeplTranslator(api_key=DEEPL_API_KEY, source="EN", target="JA")
    return translator.translate(text)

def fetch_and_register_articles():
    feed = feedparser.parse(RSS_URL)
    for entry in getattr(feed, "entries", []):
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        summary_raw = getattr(entry, "summary", "") or ""
        if not (title and url):
            print("⚠️ タイトルまたはURLが欠落しているためスキップ")
            continue
        summary = translate_text(summary_raw) if summary_raw else ""
        add_page_to_notion(title, url, summary)

if __name__ == "__main__":
    fetch_and_register_articles()
