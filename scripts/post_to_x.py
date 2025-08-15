import os
import json
from datetime import datetime
from typing import List, Dict, Set

import requests
import tweepy

# ====== Secrets / 環境変数 ======
# 必須：前提条件どおり、Secrets から取得（平文不可）
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]

# v2 create_tweet でも OAuth1.0a のユーザーコンテキストが利用可能
# （Freeプラン想定・Write権限付与済み）
X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

# ====== 定数 ======
NOTION_VERSION = "2022-06-28"
POSTED_LOG_FILE = "posted_urls.json"
TCO_URL_LENGTH = 23  # X (t.co) のURL固定長換算（実運用の一般値）

# ====== ユーティリティ ======
def notify_slack(message: str) -> None:
    """Slackへテキスト通知。YAML側ルールに合わせて text フィールドを必ず送る"""
    try:
        res = requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=15)
        res.raise_for_status()
    except Exception as e:
        # Slack障害時は標準出力に出すのみ（処理は続行）
        print(f"Slack通知失敗: {e} :: {message}")

def load_posted_urls() -> Set[str]:
    """過去投稿済みURLをローカルJSONから読み込み"""
    if os.path.exists(POSTED_LOG_FILE):
        try:
            with open(POSTED_LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return set(map(str, data))
        except Exception as e:
            notify_slack(f"⚠ posted_urls.json 読み込み失敗: {e}")
    return set()

def save_posted_urls(urls: Set[str]) -> None:
    """投稿済みURLを保存"""
    try:
        with open(POSTED_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(urls)), f, ensure_ascii=False, indent=2)
    except Exception as e:
        notify_slack(f"⚠ posted_urls.json 保存失敗: {e}")

def _extract_notion_title(title_prop: Dict) -> str:
    """Notion Title プロパティからテキストを抽出（複数要素連結に対応）"""
    parts = []
    for block in title_prop.get("title", []):
        text = block.get("plain_text") or block.get("text", {}).get("content")
        if text:
            parts.append(text)
    return "".join(parts).strip()

def get_approved_articles() -> List[Dict[str, str]]:
    """Notionから Select=approved の記事（title/url）を全件取得"""
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

    articles: List[Dict[str, str]] = []
    has_more = True
    next_cursor = None

    while has_more:
        body = dict(payload)
        if next_cursor:
            body["start_cursor"] = next_cursor

        res = requests.post(url, headers=headers, json=body, timeout=30)
        res.raise_for_status()
        data = res.json()

        for page in data.get("results", []):
            props = page.get("properties", {})
            title = _extract_notion_title(props.get("Title", {}))
            link = props.get("URL", {}).get("url", "")
            if title and link:
                articles.append({"title": title, "url": link})

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return articles

def truncate_for_tweet(text: str, url: str) -> str:
    """280文字制限に収める（URLは t.co 固定長換算）"""
    max_len = 280 - TCO_URL_LENGTH - 1  # URL + スペース分
    if len(text) > max_len:
        # 末尾に三点リーダを付けて切り詰め
        return text[: max_len - 1] + "…"
    return text

def get_twitter_client() -> tweepy.Client:
    """Tweepy v2 Client をユーザーコンテキスト（OAuth1.0a）で初期化"""
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET,
        wait_on_rate_limit=True,
    )
    return client

def post_to_x_v2(article: Dict[str, str]) -> Dict:
    """
    Xに投稿（v2 create_tweet）。成功時はレスポンスの dict を返す。
    失敗時は例外を送出。
    """
    client = get_twitter_client()
    tweet_text = truncate_for_tweet(article["title"], article["url"])
    status = f"{tweet_text} {article['url']}"

    try:
        resp = client.create_tweet(text=status)
        # resp.data 例: {'id': '1234567890123456789', 'text': '...'} を想定
        if not getattr(resp, "data", None) or "id" not in resp.data:
            # 期待するフィールドが無い場合は失敗扱い
            raise RuntimeError(f"Unexpected response: {getattr(resp, 'data', None)}")
        return resp.data  # {'id': str, 'text': str}
    except tweepy.TweepyException as e:
        # TweepyのHTTPエラー詳細
        detail = getattr(e, "response", None)
        if detail is not None:
            try:
                body = detail.json()
            except Exception:
                body = detail.text
            raise RuntimeError(f"Tweepy error status={detail.status_code}, body={body}") from e
        raise

# ====== メイン処理 ======
def main() -> None:
    notify_slack("=== X投稿処理開始（v2） ===")

    try:
        posted_urls = load_posted_urls()
        approved_articles = get_approved_articles()

        # 重複除外（URL基準）
        new_articles = [a for a in approved_articles if a["url"] not in posted_urls]

        if not new_articles:
            notify_slack("新規投稿対象なし")
            return

        success_count = 0
        posted_ids: List[str] = []
        failures: List[str] = []

        for article in new_articles:
            try:
                data = post_to_x_v2(article)
                tweet_id = str(data.get("id"))
                posted_urls.add(article["url"])
                success_count += 1
                posted_ids.append(tweet_id)
                # 各投稿の即時通知（詳細）
                notify_slack(f"✅ 投稿成功: id={tweet_id} | title={article['title']}")
            except Exception as e:
                msg = f"投稿失敗: title={article.get('title')} | url={article.get('url')} | error={e}"
                failures.append(msg)
                notify_slack(f"❌ {msg}")

        save_posted_urls(posted_urls)

        summary_lines = [
            f"✅ X投稿成功: {success_count}件 / 新規対象: {len(new_articles)}件",
        ]
        if posted_ids:
            summary_lines.append(f"投稿ID: {', '.join(posted_ids)}")
        if failures:
            summary_lines.append("失敗詳細:")
            summary_lines.extend(f"- {line}" for line in failures)

        notify_slack("\n".join(summary_lines))

    except Exception as e:
        notify_slack(f"❌ X投稿処理でエラー発生: {e}")
        raise
    finally:
        notify_slack("=== X投稿処理終了（v2） ===")

if __name__ == "__main__":
    main()
