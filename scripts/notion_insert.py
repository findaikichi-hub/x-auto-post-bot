import os
import feedparser
import requests

# === 環境変数 ===
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
RSS_URL = os.getenv("RSS_URL")

# 明示指定があればそれを最優先（任意）
NOTION_PROP_TITLE = os.getenv("NOTION_PROP_TITLE")      # 例: "Title" や "名前"
NOTION_PROP_URL = os.getenv("NOTION_PROP_URL")          # 例: "URL" や "リンク"
NOTION_PROP_STATUS = os.getenv("NOTION_PROP_STATUS")    # 例: "Status" や "ステータス"
NOTION_STATUS_DEFAULT = os.getenv("NOTION_STATUS_DEFAULT", "draft")

# === 事前チェック ===
if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError("NOTION_API_KEY または NOTION_DATABASE_ID が設定されていません。")
if not DEEPL_API_KEY:
    raise ValueError("DEEPL_API_KEY is not set. Check GitHub Secrets and workflow env.")
if not RSS_URL:
    raise ValueError("RSS_URL is not set. Set it in workflow env or Secrets.")

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"

def translate_text(text, target_lang="JA"):
    url = "https://api-free.deepl.com/v2/translate"
    data = {"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang}
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["translations"][0]["text"]

def discover_properties():
    """
    DBのプロパティを取得して、title/url/select を自動特定。
    環境変数で明示指定があればそれを最優先。
    戻り値: dict = {
        "title": <内部名 or None>,
        "url": <内部名 or None>,
        "status": <内部名 or None>,
        "status_options": [<選択肢名の配列>] (statusがある場合)
    }
    """
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
    }
    res = requests.get(f"{NOTION_API_BASE}/databases/{NOTION_DATABASE_ID}", headers=headers)
    res.raise_for_status()
    props = res.json().get("properties", {})

    # 初期化
    title_key = None
    url_key = None
    status_key = None
    status_options = []

    # 環境変数で明示指定されていれば最優先で使う（存在チェックもする）
    def ensure_prop_exists(name, expected_type=None):
        if not name:
            return None
        p = props.get(name)
        if not p:
            return None
        if expected_type and p.get("type") != expected_type:
            return None
        return name

    title_key = ensure_prop_exists(NOTION_PROP_TITLE, expected_type="title")
    url_key = ensure_prop_exists(NOTION_PROP_URL, expected_type="url")
    status_key = ensure_prop_exists(NOTION_PROP_STATUS, expected_type="select")

    # 自動検出（未指定・未検出のものだけ）
    if not title_key:
        for k, v in props.items():
            if v.get("type") == "title":
                title_key = k
                break
    if not url_key:
        for k, v in props.items():
            if v.get("type") == "url":
                url_key = k
                break
    if not status_key:
        for k, v in props.items():
            if v.get("type") == "select":
                status_key = k
                break

    if status_key:
        status_options = [opt.get("name") for opt in props[status_key]["select"].get("options", []) if opt.get("name")]

    print("[INFO] Detected Notion properties ->",
          f"title='{title_key}', url='{url_key}', status='{status_key}', options={status_options}")

    return {
        "title": title_key,
        "url": url_key,
        "status": status_key,
        "status_options": status_options,
    }

def add_to_notion(title, url, summary, prop_map):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    properties = {}

    # タイトル（必須：見つからない場合は失敗させる）
    if not prop_map["title"]:
        raise RuntimeError("Notionデータベースに title 型プロパティが見つかりません。内部名が不明です。")
    properties[prop_map["title"]] = {"title": [{"text": {"content": title}}]}

    # URL（あれば設定）
    if prop_map["url"]:
        properties[prop_map["url"]] = {"url": url}

    # ステータス（あれば設定／選択肢がなければ最初の選択肢にフォールバック／それもなければスキップ）
    if prop_map["status"]:
        status_name = NOTION_STATUS_DEFAULT
        if status_name not in prop_map["status_options"]:
            if prop_map["status_options"]:
                print(f"[WARN] Select '{status_name}' not found. Fallback to '{prop_map['status_options'][0]}'")
                status_name = prop_map["status_options"][0]
            else:
                print("[WARN] No select options defined. Skip setting status.")
                status_name = None
        if status_name:
            properties[prop_map["status"]] = {"select": {"name": status_name}}

    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"text": {"content": summary or ""}},
                        {"text": {"content": "\n\nSource: " + (url or "")}},
                    ]
                },
            }
        ],
    }

    resp = requests.post(f"{NOTION_API_BASE}/pages", headers=headers, json=data)
    if resp.status_code != 200:
        print("Error response from Notion:", resp.text)
    resp.raise_for_status()
    print(f"✅ Added to Notion: {title}")

def safe_get_summary(entry):
    # feed により summary/description/content が異なることがあるので頑健に
    if hasattr(entry, "summary"):
        return entry.summary
    if hasattr(entry, "description"):
        return entry.description
    if hasattr(entry, "content") and entry.content:
        # content は配列のことが多い
        try:
            return entry.content[0].value
        except Exception:
            pass
    return ""

def main():
    prop_map = discover_properties()

    feed = feedparser.parse(RSS_URL)
    entries = getattr(feed, "entries", []) or []
    if not entries:
        print("[WARN] No RSS entries found.")
        return

    for entry in entries[:5]:
        title_raw = getattr(entry, "title", "(no title)")
        link_raw = getattr(entry, "link", "")
        summary_raw = safe_get_summary(entry)

        title_ja = translate_text(title_raw)
        summary_ja = translate_text(summary_raw) if summary_raw else ""

        add_to_notion(title_ja, link_raw, summary_ja, prop_map)

if __name__ == "__main__":
    main()
