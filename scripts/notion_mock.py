import os
import requests
import feedparser
from datetime import datetime
from deep_translator import DeeplTranslator

# ===== 設定 =====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
DEEPL_API_KEY = os.environ["DEEPL_API_KEY"]
RSS_URL = os.environ["RSS_URL"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

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
    """DeepLで日本語に翻訳"""
    translator = DeeplTranslator(api_key=DEEPL_API_KEY, source="EN", target="JA")
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
            translated_title = translate_text(entry.title)
            summary = entry.summary if hasattr(entry, "summary") else ""
            translated_summary = translate_text(summary) if summary else ""
            articles.append({
                "title": translated_title,
                "url": entry.link,
                "summary": translated_summary
            })

        # 既存URL取得
        existing_urls = get_existing_urls()

        # 新規記事だけ抽出
        new_articles = filter_new_articles(articles, existing_urls)

        # 登録処理
        for article in new_articles:
            add_to_notion(article)

        # Slack通知
        notify_slack(f"新規登録: {len(new_articles)}件, スキップ: {len(articles) - len(new_articles)}件")

    except Exception as e:
        notify_slack(f"エラー発生: {str(e)}")
        raise


if __name__ == "__main__":
    main()
