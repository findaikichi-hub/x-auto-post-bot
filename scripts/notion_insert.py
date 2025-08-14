(
echo import os
echo import feedparser
echo import requests
echo.
echo NOTION_API_KEY = os.getenv("NOTION_API_KEY")
echo NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
echo DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
echo RSS_URL = os.getenv("RSS_URL")
echo.
echo def translate_text(text, target_lang="JA"):
echo.    url = "https://api-free.deepl.com/v2/translate"
echo.    data = {"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang}
echo.    response = requests.post(url, data=data)
echo.    response.raise_for_status()
echo.    return response.json()["translations"][0]["text"]
echo.
echo def add_to_notion(title, url, summary):
echo.    notion_url = "https://api.notion.com/v1/pages"
echo.    headers = {
echo.        "Authorization": f"Bearer {NOTION_API_KEY}",
echo.        "Content-Type": "application/json",
echo.        "Notion-Version": "2022-06-28",
echo.    }
echo.    data = {
echo.        "parent": {"database_id": NOTION_DATABASE_ID},
echo.        "properties": {
echo.            "Title": {"title": [{"text": {"content": title}}]},
echo.            "URL": {"url": url},
echo.            "Status": {"select": {"name": "draft"}}
echo.        },
echo.        "children": [
echo.            {
echo.                "object": "block",
echo.                "type": "paragraph",
echo.                "paragraph": {"rich_text": [{"text": {"content": summary}}]}
echo.            }
echo.        ]
echo.    }
echo.    response = requests.post(notion_url, headers=headers, json=data)
echo.    response.raise_for_status()
echo.    print(f"Added to Notion: {title}")
echo.
echo def main():
echo.    feed = feedparser.parse(RSS_URL)
echo.    for entry in feed.entries[:5]:
echo.        title_translated = translate_text(entry.title)
echo.        summary_translated = translate_text(entry.summary)
echo.        add_to_notion(title_translated, entry.link, summary_translated)
echo.
echo if __name__ == "__main__":
echo.    main()
) > scripts\notion_insert.py
