import os, sys, datetime as dt

REQUIRED = [
    "DEEPL_API_KEY",
    "NOTION_TOKEN",
    "NOTION_DB_ID",
    "X_API_KEY",
    "X_API_SECRET",
    "X_ACCESS_TOKEN",
    "X_ACCESS_SECRET",
]

def mask(val: str) -> str:
    if not val:
        return "(missing)"
    if len(val) <= 6:
        return "*" * len(val)
    return val[:3] + "*" * (len(val) - 6) + val[-3:]

print("=== bot.py: environment sanity check ===")
print("UTC now:", dt.datetime.utcnow().isoformat() + "Z")
all_ok = True
for k in REQUIRED:
    v = os.getenv(k)
    ok = bool(v)
    all_ok = all_ok and ok
    print(f"{'✅' if ok else '⚠️'} {k} = {mask(v or '')}")

# ここでは実APIは叩かずに成功終了。
# 後で実装を追加していく前提のMVP。
if not all_ok:
    print("NOTE: 一部のSecretsはダミー/未設定です。MVPテストとしてはOKです。")
else:
    print("All secrets present. Ready for next step.")

sys.exit(0)
