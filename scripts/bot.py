import os

# 環境変数からキーを取得
X_API_KEY = os.getenv("X_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
RSS_URL = os.getenv("RSS_URL")

def main():
    print("Bot starting...")
    print(f"RSS URL: {RSS_URL}")
    # 実際の処理をここに記述
    # API Key は直接表示しないこと
    print("Bot finished.")

if __name__ == "__main__":
    main()
