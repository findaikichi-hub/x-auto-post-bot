import os
import sys
import json
import time
import typing as t
import requests
import feedparser

# deep_translator は小文字言語コード（en/ja）を使用する
try:
    from deep_translator import DeeplTranslator
except Exception:
    DeeplTranslator = None  # DEEPL_API_KEY 未設定やライブラリ未導入でも動くようにする

# ===== 必須環境変数チェック（本番は Notion 必須）=====
required_envs = ["NOTION_API_KEY", "NOTION_DATABASE_ID", "RSS_URL"]
missing = [v for v in required_envs if not os.environ.get(v)]
if missing:
    print(f"❌ 必須環境変数が未設定です: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
RSS_URL = os.environ["RSS_URL"]
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY", "")

NOTION_VERSION = "2022-06-28"
NOTION_CREATE_PAGE_URL = "https://api.notion.com/v1/pages"
NOTION_DB_RETRIEVE_URL = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
NOTION_DB_QUERY_URL = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

def retrieve_db_schema() -> dict:
    """DBのスキーマを取得し、プロパティ名 -> type の辞書を返す"""
    res = requests.get(NOTION_DB_RETRIEVE_URL, headers=headers, timeout=30)
    try:
        res.raise_for_status()
    except requests.HTTPError as e:
        print("Notion データベース取得に失敗しました。レスポンス:", file=sys.stderr)
        try:
            print(res.text, file=sys.stderr)
        except Exception:
            pass
        raise e
    data = res.json()
    return data.get("properties", {})

def find_property_names(props: dict) -> t.Dict[str, t.Optional[str]]:
    """タイトル/URL/要約(rich_text)のプロパティ名を推定して返す"""
    title_prop = None
    url_prop = None
    summary_prop = None

    # タイトル: type == "title"
    for name, meta in props.items():
        if meta.get("type") == "title":
            title_prop = name
            break

    # URL: type == "url"
    for name, meta in props.items():
        if meta.get("type") == "url":
            url_prop = name
            break

    # 要約: 優先順に Summary/要約 の rich_text、なければ最初の rich_text
    rich_text_candidates = []
    for name, meta in props.items():
        if meta.get("type") == "rich_text":
            rich_text_candidates.append(name)
    # 名前で優先
    for pref in ["Summary", "要約", "概要"]:
        if pref in rich_text_candidates:
            summary_prop = pref
            break
    if summary_prop is None and rich_text_candidates:
        summary_prop = rich_text_candidates[0]

    return {
        "title": title_prop,
        "url": url_prop,
        "summary": summary_prop,
    }

def is_url_already_registered(url_prop: t.Optional[str], url_value: str) -> bool:
    """URL プロパティが存在する時のみ重複チェック"""
    if not url_prop:
        print("⚠️ URL プロパティが存在しないため重複チェックをスキップします。")
        return False
    query = {
        "filter": {
            "property": url_prop,
            "url": {"equals": url_value}
        }
    }
    res = requests.post(NOTION_DB_QUERY_URL, headers=headers, json=query, timeout=30)
    res.raise_for_status()
    return len(res.json().get("results", [])) > 0

def add_page_to_notion(title_prop: str, url_prop: t.Optional[str], summary_prop: t.Optional[str],
                       title: str, url: str, summary: str) -> None:
    properties: dict = {}

    # タイトル（必須）
    if not title_prop:
        raise RuntimeError("データベースに title 型プロパティが存在しません。Notion DB を確認してください。")
    properties[title_prop] = {"title": [{"text": {"content": title}}]}

    # URL（存在すればURL型で設定、なければスキップ）
    if url_prop:
        properties[url_prop] = {"url": url}

    # 要約（存在すれば rich_text で設定、なければスキップ）
    if summary_prop:
        properties[summary_prop] = {"rich_text": [{"text": {"content": summary}}]}

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties
    }

    res = requests.post(NOTION_CREATE_PAGE_URL, headers=headers, json=payload, timeout=30)
    try:
        res.raise_for_status()
    except requests.HTTPError as e:
        print("Notion API error:", res.status_code, res.text, file=sys.stderr)
        raise e

def translate(text: str) -> str:
    if not text:
        return ""
    if not DEEPL_API_KEY or DeeplTranslator is None:
        # 翻訳キー未設定 or ライブラリ未導入なら原文返却
        return text
    try:
        translator = DeeplTranslator(api_key=DEEPL_API_KEY, source="en", target="ja")
        return translator.translate(text)
    except Exception as e:
        print(f"⚠️ 翻訳に失敗しました。原文を使用します: {e}", file=sys.stderr)
        return text

def fetch_and_register_articles():
    # スキーマ取得 & プロパティ自動検出
    props = retrieve_db_schema()
    names = find_property_names(props)
    print(f"🔎 検出したプロパティ: title='{names['title']}' url='{names['url']}' summary='{names['summary']}'")

    feed = feedparser.parse(RSS_URL)
    entries = getattr(feed, "entries", [])
    print(f"📥 RSS 取得件数: {len(entries)}")

    for entry in entries:
        title = (getattr(entry, "title", "") or "").strip()
        url = (getattr(entry, "link", "") or "").strip()
        summary_raw = (getattr(entry, "summary", "") or "")  # 無い場合あり

        if not title or not url:
            print("⚠️ タイトルまたはURLが欠落しているためスキップ")
            continue

        # 重複チェック（URL型プロパティがある場合のみ）
        if is_url_already_registered(names["url"], url):
            print(f"⏭️ 重複スキップ: {url}")
            continue

        summary_ja = translate(summary_raw)
        add_page_to_notion(
            title_prop=names["title"],
            url_prop=names["url"],
            summary_prop=names["summary"],
            title=title,
            url=url,
            summary=summary_ja
        )
        print(f"✅ 登録完了: {title}")

if __name__ == "__main__":
    print("=== 本番 Notion 登録開始 ===")
    fetch_and_register_articles()
    print("=== 本番 Notion 登録完了 ===")
