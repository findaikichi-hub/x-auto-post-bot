import os
import feedparser
import requests

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
RSS_URL = os.getenv("RSS_URL")


def translate_text(text, target_lang="JA"):
    url = "https://api-free.deepl.com/v2/translate"
    data = {"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang}
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["translations"][0]["text"]


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
            "Title": {"title": [{"text": {"content": title}}]},
            "URL": {"url": url},
            "Status": {"select": {"name": "draft"}},
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
    response.raise_for_status()
    print(f"Added to Notion: {title}")


def main():
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries[:5]:
        title_translated = translate_text(entry.title)
        summary_translated = translate_text(entry.summary)
        add_to_notion(title_translated, entry.link, summary_translated)


if __name__ == "__main__":
    main()
