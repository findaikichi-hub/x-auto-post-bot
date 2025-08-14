import os
import subprocess
import sys

# feedparser が未インストールならインストール
try:
    import feedparser
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "feedparser"])
    import feedparser

# requests が未インストールならインストール
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# 環境変数からキーを取得
X_API_KEY = os.getenv("X_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
RSS_URL = os.getenv("RSS_URL")

print(f"[DEBUG] X_API_KEY={'***' if X_API_KEY else 'MISSING'}")
print(f"[DEBUG] DEEPL_API_KEY={'***' if DEEPL_API_KEY else 'MISSING'}")

def translate_text(text, target_lang="JA"):
    """
    DeepL API を使って英語タイトルを日本語に翻訳
    """
    url = "https://api-free.deepl.com/v2/translate"
    data = {
        "auth_key": DEEPL_API_KEY,
        "text": text,
        "target_lang": target_lang
    }
    try:
        r = requests.post(url, data=data)
        r.raise_for_status()
        result = r.json()
        return result["translations"][0]["text"]
    except Exception as e:
        print(f"[ERROR] Translation failed: {e}")
        return text

def fetch_rss_entries():
    print(f"[INFO] Fetching RSS feed from: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    entries = feed.entries
    print(f"[INFO] Found {len(entries)} entries")
    return entries

def main():
    entries = fetch_rss_entries()

    for entry in entries[:5]:  # 上位5件のみ表示
        title_en = entry.title
        title_ja = translate_text(title_en)
        url = entry.link
        print(f"- {title_en}\n  → {title_ja}\n  {url}")

if __name__ == "__main__":
    main()
