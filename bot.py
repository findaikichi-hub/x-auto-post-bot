import os
import feedparser
import requests

X_API_KEY = os.environ.get("X_API_KEY")
DEEPL_API_KEY = os.environ.get("DEEPL_API_KEY")

print(f"[DEBUG] X_API_KEY={'***' if X_API_KEY else None}")
print(f"[DEBUG] DEEPL_API_KEY={'***' if DEEPL_API_KEY else None}")

RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

def translate_text(text, target_lang="JA"):
    url = "https://api-free.deepl.com/v2/translate"
    data = {
        "auth_key": DEEPL_API_KEY,
        "text": text,
        "target_lang": target_lang
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        result = response.json()
        return result["translations"][0]["text"]
    except Exception as e:
        print(f"[ERROR] DeepL translation failed: {e}")
        return text

print(f"[INFO] Fetching RSS feed from: {RSS_URL}")
feed = feedparser.parse(RSS_URL)
print(f"[INFO] Found {len(feed.entries)} entries")

for entry in feed.entries[:5]:
    title_en = entry.title
    link = entry.link
    title_ja = translate_text(title_en)
    print(f"- {title_en}")
    print(f"  → {title_ja}")
    print(f"  {link}")
