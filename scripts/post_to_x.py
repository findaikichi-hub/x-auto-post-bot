import os
import requests
import tweepy

# ===== 設定 =====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

NOTION_VERSION = "2022-06-28"


def get_approved_articles():
    """Notion DBからSelect='approved'の記事を取得"""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }
    payload = {
        "filter": {
            "property": "Select",
            "select": {"equals": "approved"},
        }
    }

    res = requests.post(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()

    articles = []
    for page in data.get("results", []):
        props = page.get("properties", {})
        title = props.get("Title", {}).get("title", [{}])[0].get("plain_text", "")
        url_prop = props.get("URL", {}).get("url", "")
        if title and url_prop:
            articles.append({"title": title, "url": url_prop})

    return articles


def notify_slack(message):
    """Slackに通知"""
    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=15)
    res.raise_for_status()


def post_to_x(text):
    """X(Twitter)に投稿"""
    auth = tweepy.OAuth1UserHandler(
        X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
    )
    api = tweepy.API(auth)
    api.update_status(status=text)


def verify_x_credentials():
    """Xの認証情報を事前確認"""
    auth = tweepy.OAuth1UserHandler(
        X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
    )
    api = tweepy.API(auth)
    api.verify_credentials()


def main():
    try:
        # 認証チェック
        verify_x_credentials()

        articles = get_approved_articles()
        if not articles:
            notify_slack("ℹ️ 投稿対象（approved）はありません。")
            return

        for art in articles:
            text = f"{art['title']} {art['url']}"
            post_to_x(text)

        notify_slack(f"✅ 本番投稿完了: {len(articles)}件")
    except Exception as e:
        notify_slack(f"❌ エラー発生: {str(e)}")
        raise


if __name__ == "__main__":
    main()
