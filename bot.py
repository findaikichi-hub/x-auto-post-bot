import os
import feedparser

# Secrets読み込みテスト
X_API_KEY = os.getenv("X_API_KEY", "NoKey")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "NoKey")

print(f"[DEBUG] X_API_KEY={X_API_KEY}")
print(f"[DEBUG] DEEPL_API_KEY={DEEPL_API_KEY}")

# RSS URL（Reuters World News）
RSS_URL = "https://feeds.reuters.com/reuters/worldNews"

print(f"[INFO] Fetching RSS feed from: {RSS_URL}")
feed = feedparser.parse(RSS_URL)

print(f"[INFO] Found {len(feed.entries)} entries")

# 最新5件のタイトルとURLを出力
for entry in feed.entries[:5]:
    print(f"- {entry.title}")
    print(f"  {entry.link}")
