import os
import sys
import traceback
import feedparser

# 翻訳は DeepL を優先、使えない場合は GoogleTranslator にフォールバック
try:
    from deep_translator import DeeplTranslator, GoogleTranslator
except Exception:
    DeeplTranslator = None  # type: ignore
    GoogleTranslator = None  # type: ignore


def get_env(name: str, required: bool = False):
    val = os.environ.get(name)
    if required and (val is None or val.strip() == ""):
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return val


def translate_text(text: str, deepl_key: str | None) -> str:
    if not text:
        return ""
    # deep_translator は小文字 or auto 指定が必要
    if deepl_key and DeeplTranslator is not None:
        try:
            return DeeplTranslator(api_key=deepl_key, source="auto", target="ja").translate(text)
        except Exception:
            pass
    if GoogleTranslator is not None:
        try:
            return GoogleTranslator(source="auto", target="ja").translate(text)
        except Exception:
            pass
    return text


def main() -> int:
    try:
        # MOCK では Notion のシークレットは不要。RSS_URL は必須、DEEPLは任意
        rss_url = get_env("RSS_URL", required=True)
        deepl_key = get_env("DEEPL_API_KEY", required=False)

        feed = feedparser.parse(rss_url)
        if getattr(feed, "bozo", 0):
            raise RuntimeError(f"Failed to parse RSS: {getattr(feed, 'bozo_exception', 'unknown error')}")

        entries = getattr(feed, "entries", [])
        created = 0

        for e in entries:
            title = getattr(e, "title", "").strip()
            url = getattr(e, "link", "").strip()
            summary_raw = getattr(e, "summary", "") or getattr(e, "description", "")
            if not title or not url:
                print(f"[MOCK] skip (title/url missing): title='{title}', url='{url}'")
                continue
            summary_ja = translate_text(summary_raw, deepl_key)
            print(f"[MOCK] Would create Notion page -> title='{title}', url='{url}', summary(len)={len(summary_ja)}")
            created += 1

        print(f"[MOCK] processed={len(entries)}, would_create={created}")
        return 0
    except Exception as e:
        print("=== MOCK execution failed ===")
        print(str(e))
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
