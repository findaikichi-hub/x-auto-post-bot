import os
import time
import requests
from requests_oauthlib import OAuth1

# 環境変数からSecretsを取得
API_KEY = os.environ["X_API_KEY"]
API_SECRET = os.environ["X_API_SECRET"]
ACCESS_TOKEN = os.environ["X_ACCESS_TOKEN"]
ACCESS_SECRET = os.environ["X_ACCESS_SECRET"]

# OAuth1認証設定
auth = OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)

def verify_credentials():
    """X APIの認証確認"""
    url = "https://api.twitter.com/1.1/account/verify_credentials.json"
    resp = requests.get(url, auth=auth)
    if resp.status_code == 200:
        print("✅ 認証成功")
        return True
    else:
        print(f"❌ 認証失敗: {resp.status_code} {resp.text}")
        return False

def post_test_tweet():
    """テスト投稿"""
    timestamp = int(time.time())
    text = f"✅ X投稿テスト成功！（CI） {timestamp}"
    url = "https://api.twitter.com/2/tweets"
    resp = requests.post(url, json={"text": text}, auth=auth)
    if resp.status_code in [200, 201]:
        print(f"✅ 投稿成功: {text}")
    else:
        print(f"❌ 投稿失敗: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    print("=== X投稿プリフライト開始（mock）===")
    if verify_credentials():
        post_test_tweet()
    print("=== X投稿プリフライト終了（mock）===")
