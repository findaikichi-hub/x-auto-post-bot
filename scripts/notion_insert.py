import os
import requests
import feedparser
from deep_translator import DeeplTranslator
from bs4 import BeautifulSoup

# ===== 設定（Secrets をそのまま参照。任意は .get()）=====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
RSS_URL = os.environ["RSS_URL"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")  # 任意

# deep_translator の仕様に合わせ言語コードは小文字固定
SRC_LANG = "en"
TGT_LANG = "ja"

NOTION_VERSION = "2022-06-28"
NOTION_DB_QUERY_URL = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
NOTION_CREATE_PAGE_URL = "https://api.notion.com/v1/pages"

# ===== ヘルパー =====
def strip_html(text: str) -> str:
    """HTMLを除去してプレーンテキスト化（失敗時は原文返却）"""
    if not text:
        return ""
    try:
        return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        return text

def get_existing_urls():
    """Notionの下書きDBから既存URL一覧を取得（重複登録防止用）"""
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

        res = requests.post(NOTION_DB_QUERY_URL, headers=headers, json=payload, timeout=30)
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
    return [a for a in articles if a.get("url") and a["url"] not in existing_urls]


def translate_text(text):
    """DeepLで日本語に翻訳（DEEPL_API_KEY が未設定 or 失敗時は原文返却）"""
    if not text:
        return ""
    if not DEEPL_API_KEY:
        return text
    try:
        translator = DeeplTranslator(api_key=DEEPL_API_KEY, source=SRC_LANG, target=TGT_LANG)
        return translator.translate(text)
    except Exception:
        # DeepLエラー時は原文で続行
        return text


def add_to_notion(article):
    """記事をNotionの下書きDBに登録（Select = draft）"""
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
            "Select": {"select": {"name": "draft"}},
        },
    }
    res = requests.post(NOTION_CREATE_PAGE_URL, headers=headers, json=payload, timeout=30)
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
                # タイトル or URL 無しはスキップ（ログはSlackに載せない）
                continue

            # summaryはHTMLをプレーンテキスト化
            summary_clean = strip_html(summary_raw) if summary_raw else ""

            translated_title = translate_text(title_raw)
            translated_summary = translate_text(summary_clean) if summary_clean else ""

            articles.append(
                {
                    "title": translated_title,
                    "url": link,
                    "summary": translated_summary,
                }
            )

        # 既存URL取得 & 新規のみ抽出
        existing_urls = get_existing_urls()
        new_articles = filter_new_articles(articles, existing_urls)

        # 登録処理
        for article in new_articles:
            add_to_notion(article)

        # Slack通知
        notify_slack(
            f"新規登録: {len(new_articles)}件 / 取得: {len(articles)}件 / 重複スキップ: {len(articles) - len(new_articles)}件"
        )

    except Exception as e:
        # 失敗通知してリスロー（Actions failure に反映）
        try:
            notify_slack(f"エラー発生: {str(e)}")
        finally:
            raise


if __name__ == "__main__":
    main()
