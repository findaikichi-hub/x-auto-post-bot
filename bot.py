import os
import sys
import subprocess

# 必要なパッケージを確認してインストール
def ensure_package(pkg_name):
    try:
        __import__(pkg_name)
    except ImportError:
        print(f"[INFO] Installing missing package: {pkg_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])

# 必要なライブラリを確認
ensure_package("feedparser")
ensure_package("requests")

import feedparser
import requests

# デバッグ用に環境変数を表示（APIキーはマスク）
print(f"[DEBUG] X_API_KEY={'***' if os.getenv('X_API_KEY') else 'None'}")
print(f"[DEBUG] DEEPL_API_KEY={'***' if os.getenv('DEEPL_API_KEY') else 'None'}")

# RSS URL
rss_url = os.getenv("RSS_URL", "https://feeds.bbci.co.uk/news/world/rss.xml")
print(f"[INFO] Fetching RSS feed from: {rss_url}")

# RSSを取得
feed = feedparser.parse(rss_url)
print(f"[INFO] Found {len(feed.entries)} entries")

# 各記事を翻訳して表示
deepl_api_key = os.getenv("DEEPL_API_KEY")
if not deepl_api_key:
    print("[ERROR] DEEPL_API_KEY not found in environment variables.")
    sys.exit(1)

for entry in feed.entries[:5]:
    title = entry.title
    link = entry.link

    # DeepL APIで翻訳
    try:
        resp = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": deepl_api_key, "text": title, "target_lang": "JA"},
            timeout=10
        )
        if resp.status_code == 200:
            translated_title = resp.json()["translations"][0]["text"]
        else:
            translated_title = "[翻訳失敗]"
    except Exception as e:
        translated_title = f"[翻訳エラー: {e}]"

    print(f"- {title}\n  → {translated_title}\n  {link}")
