import os
import sys
import requests
import feedparser
from deep_translator import DeeplTranslator

# ===== 環境変数（Secrets） =====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
RSS_URL = os.environ["RSS_URL"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")

SRC_LANG = "en"
TGT_LANG = "ja"
NOTION_VERSION = "2022-06-28"

# ===== 関数 =====
def get_existing_urls():
    """Notionの下書きDBから既存URL一覧を取得（重複登録防止用）"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    existing_urls = set()
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res = requests.post(url, headers=headers, json=payload, timeout=30)
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
    """既存URLと突き合わせて新規だけ抽出"""
    return [a for a in articles if a.get("url") and a["url"] not in existing_urls]


def translate_text(text):
    """DeepLで翻訳（APIキーが無ければ原文返却）"""
    if not text:
        return ""
    if not DEEPL_API_KEY:
        return text
    translator = DeeplTranslator(api_key=DEEPL_API_KEY, source=SRC_LANG, target=TGT_LANG)
    return translator.translate(text)


def add_to_notion(article):
    """Notionの下書きDBに登録（Select = draft, Summary 追加）"""
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Title": {"title": [{"text": {"content": article["title"]}}]},
            "URL": {"url": article["url"]},
            "Summary": {"rich_text": [{"text": {"content": article.get("summary", "")}}]},
            "Select": {"select": {"name": "draft"}},
        },
    }
    res = requests.post(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()


def notify_slack(message):
    """Slack通知（text フィールド必須）"""
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    res.raise_for_status()


def main():
    try:
        # RSS取得
        feed = feedparser.parse(RSS_URL)
        articles = []
        for entry in getattr(feed, "entries", []):
            title_raw = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary_raw = getattr(entry, "summary", "") if hasattr(entry, "summary") else ""

            if not title_raw or not link:
                continue

            translated_title = translate_text(title_raw)
            translated_summary = translate_text(summary_raw) if summary_raw else ""

            articles.append({
                "title": translated_title,
                "url": link,
                "summary": translated_summary,
            })

        existing_urls = get_existing_urls()
        new_articles = filter_new_articles(articles, existing_urls)

        for article in new_articles:
            add_to_notion(article)

        notify_slack(
            f"✅ Notion登録（本番）成功: 新規 {len(new_articles)} 件 / 取得 {len(articles)} 件 / 重複 {len(articles) - len(new_articles)} 件"
        )

    except Exception as e:
        try:
            notify_slack(f"❌ Notion登録（本番）失敗: {str(e)}")
        finally:
            raise


if __name__ == "__main__":
    main()
