import os
import re
from datetime import datetime, timezone
from typing import List, Dict
import requests
import tweepy

# ===== Secrets（Actionsから注入）=====
NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
X_API_KEY = os.environ["X_API_KEY"]
X_API_SECRET = os.environ["X_API_SECRET"]
X_ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
X_ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN")  # 任意

# ===== 定数 =====
NOTION_VERSION = "2022-06-28"
USER_AGENT = "notion-x-mvp/1.0 (prod)"
TCO_URL_LENGTH = 23

# ===== 共通 =====
def notify_slack(message: str) -> None:
    try:
        res = requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"Slack通知失敗: {e} :: {message}")

def _np(prop, key, default=None):
    return (prop or {}).get(key, default)

def plain_title(prop) -> str:
    return "".join([(t or {}).get("plain_text", "") for t in (prop or {}).get("title", [])])

def plain_text(prop) -> str:
    return "".join([(t or {}).get("plain_text", "") for t in (prop or {}).get("rich_text", [])])

# ===== Notion =====
def notion_query_approved_unposted() -> List[Dict[str, str]]:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    payload = {
        "filter": {
            "and": [
                {"property": "Select", "select": {"equals": "approved"}},
                {"property": "Posted", "checkbox": {"equals": False}},
            ]
        }
    }
    results = []
    has_more = True
    next_cursor = None
    while has_more:
        body = dict(payload)
        if next_cursor:
            body["start_cursor"] = next_cursor
        res = requests.post(url, headers=headers, json=body, timeout=30)
        res.raise_for_status()
        data = res.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    pages: List[Dict[str, str]] = []
    for page in results:
        props = page.get("properties", {})
        pages.append({
            "id": page.get("id"),
            "title": plain_title(props.get("Title")),
            "summary": plain_text(props.get("Summary")),
            "url": _np(props.get("URL"), "url", ""),
        })
    return pages

def notion_mark_posted(page_id: str, tweet_id: str) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "properties": {
            "Posted": {"checkbox": True},
            "TweetID": {"rich_text": [{"text": {"content": str(tweet_id)}}]},
            "PostedAt": {"date": {"start": now_utc}},
        }
    }
    res = requests.patch(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()

# ===== ツイート整形 =====
URL_RE = re.compile(r"https?://\S+")

def twitter_length(text: str) -> int:
    return len(URL_RE.sub("x" * TCO_URL_LENGTH, text))

def build_tweet(title: str, summary: str, url: str) -> str:
    title = (title or "").strip()
    summary = (summary or "").strip()
    url = (url or "").strip()

    base = f"{title}\n{url}" if title else url
    if twitter_length(base) <= 280 and summary:
        candidate = f"{title}\n{summary}\n{url}" if title else f"{summary}\n{url}"
        if twitter_length(candidate) <= 280:
            return candidate

    remain = 280 - twitter_length((f"{title}\n\n{url}" if title else f"\n{url}")) - 1
    remain = max(remain, 0)
    trimmed = summary if len(summary) <= remain else (summary[: max(remain - 1, 0)] + ("…" if remain > 0 else ""))

    candidate = f"{title}\n{trimmed}\n{url}" if title else f"{trimmed}\n{url}"
    if twitter_length(candidate) <= 280:
        return candidate

    if title:
        max_title_len = 280 - TCO_URL_LENGTH - 1
        if len(title) > max_title_len:
            title = title[: max_title_len - 1] + "…"
        return f"{title}\n{url}"
    return url

# ===== X(v2) =====
def get_twitter_client() -> tweepy.Client:
    return tweepy.Client(
        bearer_token=X_BEARER_TOKEN,
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET,
        wait_on_rate_limit=True,
    )

def _extract_error_detail(resp) -> str:
    try:
        return resp.json()
    except Exception:
        try:
            return resp.text
        except Exception:
            return "unknown error body"

def verify_x_credentials(client: tweepy.Client) -> None:
    try:
        me = client.get_me(user_auth=True)
        data = getattr(me, "data", None)
        if not data or not getattr(data, "id", None):
            raise RuntimeError(f"get_me() returned invalid data: {data}")
        notify_slack(f"X認証OK: @{getattr(data, 'username', 'unknown')} (id={data.id})")
    except tweepy.TweepyException as e:
        detail = getattr(e, "response", None)
        if detail is not None:
            body = _extract_error_detail(detail)
            raise RuntimeError(f"X認証失敗 status={detail.status_code}, body={body}") from e
        raise

def post_to_x_v2(client: tweepy.Client, status_text: str) -> str:
    try:
        resp = client.create_tweet(text=status_text, user_auth=True)
        data = getattr(resp, "data", None) or {}
        tweet_id = str(data.get("id") or "")
        if not tweet_id:
            raise RuntimeError(f"Unexpected response: {data}")
        return tweet_id
    except tweepy.TweepyException as e:
        detail = getattr(e, "response", None)
        if detail is not None:
            body = _extract_error_detail(detail)
            raise RuntimeError(f"X投稿失敗 status={detail.status_code}, body={body}") from e
        raise

# ===== メイン =====
def main() -> None:
    notify_slack("=== X投稿処理開始（v2）===")
    try:
        pages = notion_query_approved_unposted()
        if not pages:
            notify_slack("新規投稿対象（approved & Posted=false）はありません。")
            return

        client = get_twitter_client()
        verify_x_credentials(client)

        posted = 0
        previews = []
        for p in pages:
            tweet = build_tweet(p["title"], p["summary"], p["url"])
            try:
                tweet_id = post_to_x_v2(client, tweet)
                notion_mark_posted(p["id"], tweet_id)
                posted += 1
                previews.append(f"- OK {p['id']} → {tweet_id}")
                notify_slack(f"✅ 投稿成功: id={tweet_id} | title={p['title']}")
            except Exception as e:
                previews.append(f"- NG {p['id']}: {str(e)}")
                notify_slack(f"❌ 投稿失敗: page={p['id']} | url={p['url']} | error={e}")

        notify_slack(f"X投稿完了: {posted}件 / 対象 {len(pages)}件\n" +
                     "\n".join(previews[:10]) +
                     ("" if len(previews) <= 10 else "\n…"))
    except Exception as e:
        notify_slack(f"❌ X投稿処理エラー: {e}")
        raise
    finally:
        notify_slack("=== X投稿処理終了（v2）===")

if __name__ == "__main__":
    main()
