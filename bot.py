import os
import sys
import subprocess

def ensure_package(pkg_name):
    """パッケージがなければ pip でインストール"""
    try:
        __import__(pkg_name)
    except ImportError:
        print(f"[INFO] Installing missing package: {pkg_name}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])

# ===== 最初に必要パッケージを確実に入れる =====
ensure_package("feedparser")
ensure_package("requests")

# ===== インストール後に import =====
import feedparser
import requests

# ===== デバッグ用にキーの一部を表示（先頭3文字+***） =====
def mask_secret(value):
    if value and len(value) > 3:
        return value[:3] + "***"
    return "***"

X_API_KEY = os.getenv("X_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
RSS_URL = os.getenv("RSS_URL", "https://feeds.bbci.co.uk/news/world/rss.xml")

print(f"[DEBUG] X_API_KEY={mask_secret(X_API_KEY)}")
print(f"[DEBUG] DEEPL_API_KEY={mask_secret(DEEPL_API_KEY)}")
print(f"[INFO] Fetching RSS feed from: {RSS_URL}")

# ===== RSS取得 =====
feed = feedparser.parse(RSS_URL)
print(f"[INFO] Found {len(feed.entries)} entries")

# ===== 翻訳関数 =====
def translate_text(text, target_lang="JA"):
    if not DEEPL_API_KEY:
        print("[WARN] Deepl API Key not set. Skipping translation.")
        return text
    try:
        res = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang},
            timeout=10
        )
        res.raise_for_status()
        return res.json()["translations"][0]["text"]
    except Exception as e:
        print(f"[ERROR] Translation failed: {e}")
        return text

# ===== 最新5件を表示 =====
for entry in feed.entries[:5]:
    title = entry.title
    link = entry.link
    translated = translate_text(title)
    print(f"- {title}\n  → {translated}\n  {link}")
