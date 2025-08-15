name: Post to X (Production)

on:
  workflow_dispatch:
  schedule:
    - cron: "0 * * * *" # 毎時0分に実行

jobs:
  post_to_x:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Verify X API credentials
        run: |
          set +e
          RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
            --url "https://api.twitter.com/1.1/account/verify_credentials.json" \
            --header "Authorization: OAuth oauth_consumer_key=${{ secrets.X_API_KEY }},oauth_token=${{ secrets.X_ACCESS_TOKEN }},oauth_signature_method=HMAC-SHA1,oauth_timestamp=$(date +%s),oauth_nonce=$(uuidgen),oauth_version=1.0,oauth_signature=TEST")
          if [ "$RESPONSE" != "200" ]; then
            echo "X API credentials verification failed. HTTP status: $RESPONSE"
            exit 1
          fi

      - name: Run post_to_x.py
        env:
          X_API_KEY: ${{ secrets.X_API_KEY }}
          X_API_SECRET: ${{ secrets.X_API_SECRET }}
          X_ACCESS_TOKEN: ${{ secrets.X_ACCESS_TOKEN }}
          X_ACCESS_SECRET: ${{ secrets.X_ACCESS_SECRET }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: |
          python scripts/post_to_x.py

      - name: Notify Slack (Success)
        if: success()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"✅ X投稿（本番）ワークフローが正常に完了しました。"}' \
            ${{ secrets.SLACK_WEBHOOK_URL }}

      - name: Notify Slack (Failure)
        if: failure()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"❌ X投稿（本番）ワークフローが失敗しました。"}' \
            ${{ secrets.SLACK_WEBHOOK_URL }}
