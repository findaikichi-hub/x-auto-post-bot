import json
import os

MOCK_FILE = "notion_mock_data.json"

def fetch_existing_urls_mock():
    if os.path.exists(MOCK_FILE):
        with open(MOCK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("entries", []))
    return set()

def insert_to_notion_mock(title, url):
    data = {"entries": []}
    if os.path.exists(MOCK_FILE):
        with open(MOCK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data["entries"].append(url)
    with open(MOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[MOCK] Added to mock DB: {title} ({url})")
