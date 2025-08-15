import os
import requests
import tweepy
from datetime import datetime
import json

# ====== Secrets / 環境変数 ======
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

NOTION_VERSION = "2022-06-28"
POSTED_LOG_FILE = "posted_urls.json"

# ====== 関数 ======
def load_posted_urls():
    """過去投稿済みURLをローカルJSONから読み込み"""
    if os.path.exists(POSTED_LOG_FILE):
        with open(POSTED_LOG_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted_urls(urls):
    """投稿済みURLを保存"""
    with open(POSTED_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(list(urls), f, ensure_ascii=False, indent=2)

def notify_slack(message):
    """Slack通知"""
    payload = {"text": message}
    try:
        res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"Slack通知失敗: {e}")

def get_approved_articles():
    """NotionからSelect=approvedの記事を取得"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    payload = {
        "filter": {
            "property": "Select",
            "select": {"equals": "approved"}
        }
    }
    articles = []
    has_more = True
    next_cursor = None

    while has_more:
        if next_cursor:
            payload["start_cursor"] = next_cursor
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            title = props.get("Title", {}).get("title", [{}])[0].get("text", {}).get("content", "")
            link = props.get("URL", {}).get("url", "")
            if title and link:
                articles.append({"title": title.strip(), "url": link.strip()})

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return articles

def truncate_for_tweet(text, url):
    """280文字制限に収める（URLは自動短縮想定で23文字換算）"""
    max_len = 280 - 23 - 1  # URLとスペース分
    if len(text) > max_len:
        return text[:max_len - 1] + "…"
    return text

def post_to_x(article):
    """Xに投稿"""
    auth = tweepy.OAuth1UserHandler(
        X_API_KEY, X_API_SECRET,
        X_ACCESS_TOKEN, X_ACCESS_SECRET
    )
    api = tweepy.API(auth)
    tweet_text = truncate_for_tweet(article["title"], article["url"])
    status = f"{tweet_text} {article['url']}"
    api.update_status(status=status)

# ====== メイン処理 ======
def main():
    try:
        notify_slack("=== X投稿処理開始 ===")

        posted_urls = load_posted_urls()
        approved_articles = get_approved_articles()

        # 重複除外
        new_articles = [a for a in approved_articles if a["url"] not in posted_urls]

        if not new_articles:
            notify_slack("新規投稿対象なし")
            return

        success_count = 0
        for article in new_articles:
            try:
                post_to_x(article)
                posted_urls.add(article["url"])
                success_count += 1
            except Exception as e:
                notify_slack(f"投稿失敗: {article['title']} ({e})")

        save_posted_urls(posted_urls)

        notify_slack(f"✅ X投稿成功: {success_count}件 / 新規対象: {len(new_articles)}件")

    except Exception as e:
        notify_slack(f"❌ X投稿処理でエラー発生: {e}")
        raise
    finally:
        notify_slack("=== X投稿処理終了 ===")

if __name__ == "__main__":
    main()
