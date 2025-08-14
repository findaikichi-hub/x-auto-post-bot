import os
import requests
import feedparser

# 環境変数からAPIキー取得
X_API_KEY = os.getenv("X_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"  # 無料版エンドポイント
RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

def translate_text(text, target_lang="JA"):
    if not DEEPL_API_KEY:
        print("[ERROR] DEEPL_API_KEY is not set.")
        return text
    try:
        response = requests.post(
            DEEPL_API_URL,
            data={
                "auth_key": DEEPL_API_KEY,
                "text": text,
                "target_lang": target_lang
            }
        )
        response.raise_for_status()
        result = response.json()
        if "translations" in result:
            return result["translations"][0]["text"]
        else:
            print("[ERROR] Unexpected DeepL API response:", result)
            return text
    except requests.RequestException as e:
        print(f"Error:  DeepL translation failed: {e}")
        return text

def fetch_rss_entries():
    print(f"[INFO] Fetching RSS feed from: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    print(f"[INFO] Found {len(feed.entries)} entries")
    return feed.entries

def main():
    print(f"[DEBUG] X_API_KEY={'***' if X_API_KEY else 'NOT SET'}")
    print(f"[DEBUG] DEEPL_API_KEY={'***' if DEEPL_API_KEY else 'NOT SET'}")

    entries = fetch_rss_entries()
    for entry in entries[:5]:  # 最新5件だけ処理
        translated_title = translate_text(entry.title)
        print(f"- {entry.title}")
        print(f"  → {translated_title}")
        print(f"  {entry.link}")

if __name__ == "__main__":
    main()
