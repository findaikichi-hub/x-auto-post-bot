#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import feedparser
import requests

# === 実行モード設定 ===
USE_MOCK = os.getenv("USE_MOCK", "false").lower() == "true"

# === 環境変数（必ずRepository secretsから取得） ===
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
RSS_URL = os.getenv("RSS_URL")

# 明示指定（任意）
NOTION_PROP_TITLE = os.getenv("NOTION_PROP_TITLE")
NOTION_PROP_URL = os.getenv("NOTION_PROP_URL")
NOTION_PROP_STATUS = os.getenv("NOTION_PROP_STATUS")
NOTION_STATUS_DEFAULT = os.getenv("NOTION_STATUS_DEFAULT", "draft")

# === 事前チェック ===
if not NOTION_API_KEY or not NOTION_DATABASE_ID:
    raise ValueError("NOTION_API_KEY または NOTION_DATABASE_ID が設定されていません。")
if not DEEPL_API_KEY:
    raise ValueError("DEEPL_API_KEY is not set.")
if not RSS_URL:
    raise ValueError("RSS_URL is not set.")

NOTION_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"

def translate_text(text, target_lang="JA"):
    """DeepL翻訳"""
    url = "https://api-free.deepl.com/v2/translate"
    data = {"auth_key": DEEPL_API_KEY, "text": text, "target_lang": target_lang}
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["translations"][0]["text"]

def discover_properties():
    """Notion DBプロパティ自動検出"""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
    }
    res = requests.get(f"{NOTION_API_BASE}/databases/{NOTION_DATABASE_ID}", headers=headers)
    res.raise_for_status()
    props = res.json().get("properties", {})

    def ensure_prop_exists(name, expected_type=None):
        if not name:
            return None
        p = props.get(name)
        if not p:
            return None
        if expected_type and p.get("type") != expected_type:
            return None
        return name

    title_key = ensure_prop_exists(NOTION_PROP_TITLE, "title") or next((k for k, v in props.items() if v.get("type") == "title"), None)
    url_key = ensure_prop_exists(NOTION_PROP_URL, "url") or next((k for k, v in props.items() if v.get("type") == "url"), None)
    status_key = ensure_prop_exists(NOTION_PROP_STATUS, "select") or next((k for k, v in props.items() if v.get("type") == "select"), None)
    status_options = [opt.get("name") for opt in props[status_key]["select"].get("options", [])] if status_key else []

    print("[INFO] Detected properties:", title_key, url_key, status_key, status_options)
    return {"title": title_key, "url": url_key, "status": status_key, "status_options": status_options}

def add_to_notion(title, url, summary, prop_map):
    """Notionに追加"""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    properties = {}
    if not prop_map["title"]:
        raise RuntimeError("title型プロパティが見つかりません。")
    properties[prop_map["title"]] = {"title": [{"text": {"content": title}}]}
    if prop_map["url"]:
        properties[prop_map["url"]] = {"url": url}
    if prop_map["status"]:
        status_name = NOTION_STATUS_DEFAULT if NOTION_STATUS_DEFAULT in prop_map["status_options"] else (prop_map["status_options"][0] if prop_map["status_options"] else None)
        if status_name:
            properties[prop_map["status"]] = {"select": {"name": status_name}}

    data = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": properties,
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"text": {"content": summary or ""}},
                        {"text": {"content": "\n\nSource: " + (url or "")}},
                    ]
                },
            }
        ],
    }

    if USE_MOCK:
        print(f"[MOCK] Would add to Notion: {title} ({url})")
        return

    resp = requests.post(f"{NOTION_API_BASE}/pages", headers=headers, json=data)
    if resp.status_code != 200:
        print("Error from Notion:", resp.text)
    resp.raise_for_status()
    print(f"✅ Added to Notion: {title}")

def safe_get_summary(entry):
    if hasattr(entry, "summary"):
        return entry.summary
    if hasattr(entry, "description"):
        return entry.description
    if hasattr(entry, "content") and entry.content:
        try:
            return entry.content[0].value
        except Exception:
            pass
    return ""

def main():
    prop_map = discover_properties()
    feed = feedparser.parse(RSS_URL)
    entries = getattr(feed, "entries", []) or []
    if not entries:
        print("[WARN] No RSS entries found.")
        return
    for entry in entries[:5]:
        title_raw = getattr(entry, "title", "(no title)")
        link_raw = getattr(entry, "link", "")
        summary_raw = safe_get_summary(entry)
        title_ja = translate_text(title_raw)
        summary_ja = translate_text(summary_raw) if summary_raw else ""
        add_to_notion(title_ja, link_raw, summary_ja, prop_map)

if __name__ == "__main__":
    main()
