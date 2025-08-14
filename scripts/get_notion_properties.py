import os
import requests

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError("NOTION_API_KEY または NOTION_DATABASE_ID が設定されていません。")

url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": "2022-06-28"
}

response = requests.get(url, headers=headers)
response.raise_for_status()
data = response.json()

print("\n=== プロパティ一覧 ===")
for name, details in data.get("properties", {}).items():
    print(f"表示名: {name} | タイプ: {details.get('type')}")
