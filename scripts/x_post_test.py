import os
import sys
import time
import tweepy

def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        print(f"[ENV] Missing: {name}", file=sys.stderr)
        sys.exit(1)
    return v.strip()

API_KEY = require_env("X_API_KEY")
API_SECRET = require_env("X_API_SECRET")
ACCESS_TOKEN = require_env("X_ACCESS_TOKEN")
ACCESS_SECRET = require_env("X_ACCESS_SECRET")

# mock では既定で投稿しない（true/1/yes/on のときだけ投稿）
DO_POST = os.getenv("X_POST_TEST_DO_POST", "false").lower() in ("1", "true", "yes", "on")

auth = tweepy.OAuth1UserHandler(
    API_KEY,
    API_SECRET,
    ACCESS_TOKEN,
    ACCESS_SECRET
)
api = tweepy.API(auth, wait_on_rate_limit=True)

def fail(msg: str, exc: Exception | None = None, code: int = 1):
    print(msg, file=sys.stderr)
    if exc:
        print(str(exc), file=sys.stderr)
    sys.exit(code)

try:
    me = api.verify_credentials()
    if me is None:
        fail("認証に失敗しました（verify_credentials が None を返しました）。")

    screen = getattr(me, "screen_name", "unknown")
    uid = getattr(me, "id", "unknown")
    print(f"✅ 認証OK: @{screen} (id={uid})")

    if not DO_POST:
        print("ℹ️ 確認のみ（X_POST_TEST_DO_POST=false）。投稿は行いません。")
        sys.exit(0)

    text = f"✅ X投稿テスト成功！（CI） {int(ti
