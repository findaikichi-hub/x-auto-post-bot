import os
import feedparser
from deep_translator import DeeplTranslator
from notion_client import Client
import requests

# 環境変数からSecretsを取得
RSS_URL = os.getenv("RSS_URL")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

# Notionクライアント
notion = Client(auth=NOTION_API_KEY)


def send_slack_notification(message: str):
    """Slackに通知"""
    if not SLACK_WEBHOOK_URL:
        print("Slack Webhook URL が設定されていません。通知をスキップします。")
        return
    payload = {"text": message}
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Slack通知失敗: {e}")


def translate_text(text: str) -> str:
    """DeepLで翻訳。失敗時は原文を返す"""
    if not DEEPL_API_KEY:
        return text
    try:
        return DeeplTranslator(api_key=DEEPL_API_KEY, source="EN", target="JA").translate(text)
    except Exception as e:
        print(f"翻訳失敗: {e}")
        return text


def fetch_rss_entries():
    """RSSフィードを取得"""
    feed = feedparser.parse(RSS_URL)
    return feed.entries


def save_to_notion(entry, translated_summary):
    """RSS記事をNotionに保存"""
    try:
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "Title": {"title": [{"text": {"content": entry.title}}]},
                "URL": {"url": entry.link},
                "Summary": {"rich_text": [{"text": {"content": translated_summary}}]},
                "Posted": {"checkbox": False},
            },
        )
    except Exception as e:
        print(f"Notion保存失敗: {e}")
        send_slack_notification(f"❌ Notion保存失敗: {e}")


def post_to_x_mock(entry, translated_summary):
    """モック用：Xに投稿せずprintで確認"""
    print("=== モック投稿開始 ===")
    print(f"Title: {entry.title}")
    print(f"URL: {entry.link}")
    print(f"Summary: {translated_summary}")
    print("=== モック投稿終了 ===")


def main():
    try:
        entries = fetch_rss_entries()
        if not entries:
            send_slack_notification("⚠️ RSSから記事が取得できませんでした。")
            return

        for entry in entries:
            translated_summary = translate_text(entry.summary)
            save_to_notion(entry, translated_summary)
            post_to_x_mock(entry, translated_summary)

        send_slack_notification("✅ モック処理が完了しました。")

    except Exception as e:
        send_slack_notification(f"❌ モック処理中にエラー発生: {e}")


if __name__ == "__main__":
    main()
