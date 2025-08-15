import os
import tweepy

# 環境変数（GitHub Secrets）から取得
api_key = os.getenv("X_API_KEY")
api_secret = os.getenv("X_API_SECRET")
access_token = os.getenv("X_ACCESS_TOKEN")
access_secret = os.getenv("X_ACCESS_SECRET")

if not all([api_key, api_secret, access_token, access_secret]):
    raise ValueError("X APIの認証情報が不足しています。Secrets設定を確認してください。")

# Tweepy認証
auth = tweepy.OAuth1UserHandler(
    api_key,
    api_secret,
    access_token,
    access_secret
)
api = tweepy.API(auth)

# テスト投稿内容
tweet_text = "✅ X投稿テスト成功！（GitHub Actionsから送信）"

try:
    api.update_status(status=tweet_text)
    print("投稿成功:", tweet_text)
except Exception as e:
    print("投稿失敗:", e)
    raise
