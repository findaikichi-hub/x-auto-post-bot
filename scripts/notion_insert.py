import os
import feedparser
import requests

# === 設定値（GitHub Secrets または .env に登録） ===
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
RSS_URL = os.getenv("RSS_URL")

# Notion の内部プロパティ名（目視確認して修正）
NOTION_PROP_TITLE = os.getenv("NOTION_PROP_TITLE", "Title")    # タイトル型
NOTION_PROP_URL = os.getenv("NOTION_PROP_URL", "URL")          # URL型
NOTION_PROP_STATUS = os.getenv("NOTION_PROP_STATUS", "Status") # 選択型

# デフォルトの select 値（Notion の選択肢と一致させる）
NOTION_STATUS_DEFAULT = os.getenv("NOTION_STATUS_DEFAULT", "draft")

# === エラーチェック ===
if not DEEPL_API_KEY:
    raise ValueError("DEEPL_API_KEY is not set. Check GitHub Secrets and workflow env.")
if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError("NOTION_API_KEY または NOTION_DATABASE_ID が設定されていません。")


# === 翻訳処理 ===
def translate_text(text, target_lang="JA"):
    url = "https://api-free.deepl.com/v2/translate"
    data = {"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang}
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["translations"][0]["text"]


# === Notion 追加処理 ===
def add_to_notion(title, url, summary):
    notion_url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            NOTION_PROP_TITLE: {"title": [{"text": {"content": title}}]},
            NOTION_PROP_URL: {"url": url},
            NOTION_PROP_STATUS: {"select": {"name": NOTION_STATUS_DEFAULT}},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": summary}}]},
            }
        ],
    }
    response = requests.post(notion_url, headers=headers, json=data)
    if response.status_code != 200:
        print("Error response from Notion:", response.text)
    response.raise_for_status()
    print(f"✅ Added to Notion: {title}")


# === メイン処理 ===
def main():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries[:5]:
        title_translated = translate_text(entry.title)
        summary_translated = translate_text(entry.summary)
        add_to_notion(title_translated, entry.link, summary_translated)


if __name__ == "__main__":
    main()
