import os
import requests
import feedparser
from datetime import datetime
from deep_translator import DeeplTranslator

# ===== 設定（Secrets をそのまま参照）=====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")  # 任意
RSS_URL = os.environ["RSS_URL"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

# 言語コードは deep_translator 仕様に合わせて小文字で固定
SRC_LANG = "en"
TGT_LANG = "ja"

# ===== 関数 =====
def get_existing_urls():
    """Notionの下書きDBから既存URL一覧を取得"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    existing_urls = set()
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        data = res.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            url_prop = props.get("URL", {}).get("url")
            if url_prop:
                existing_urls.add(url_prop)

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return existing_urls


def filter_new_articles(articles, existing_urls):
    """
    articles: [{'title': str, 'url': str, 'summary': str}, ...]
    existing_urls: set([...])
    """
    return [a for a in articles if a["url"] not in existing_urls]


def translate_text(text):
    """DeepLで日本語に翻訳（DEEPL_API_KEY が未設定なら原文返却）"""
    if not text:
        return ""
    if not DEEPL_API_KEY:
        return text
    translator = DeeplTranslator(api_key=DEEPL_API_KEY, source=SRC_LANG, target=TGT_LANG)
    return translator.translate(text)


def add_to_notion(article):
    """記事をNotionの下書きDBに登録"""
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Title": {
                "title": [{"text": {"content": article["title"]}}]
            },
            "URL": {
                "url": article["url"]
            },
            "Select": {
                "select": {"name": "draft"}
            }
        }
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()


def notify_slack(message):
    """Slack通知"""
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload)
    res.raise_for_status()


def main():
    try:
        # RSS取得
        feed = feedparser.parse(RSS_URL)
        articles = []
        for entry in feed.entries:
            title_raw = getattr(entry, "title", "")
            summary_raw = getattr(entry, "summary", "") if hasattr(entry, "summary") else ""
            translated_title = translate_text(title_raw)
            translated_summary = translate_text(summary_raw) if summary_raw else ""
            articles.append({
                "title": translated_title,
                "url": getattr(entry, "link", ""),
                "summary": translated_summary
            })

        # 既存URL取得
        existing_urls = get_existing_urls()

        # 新規記事だけ抽出
        new_articles = fil_
