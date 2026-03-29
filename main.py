import os
import requests
import json
import time
from pathlib import Path

# =========================
# SETTINGS
# =========================
MIN_PRICE = 40
CHECK_EVERY_SECONDS = 60
SEND_STARTUP_MESSAGE = True

SEARCH_TERMS = [
    "Barbie Fairytopia Elina",
    "Barbie Fairytopia Elina NRFB",
    "Fairytopia Elina",
    "Elina doll Mattel",
    "Barbie Elina Fairytopia",
    "Mattel Fairytopia Elina",
]

# =========================
# ENV VARS
# =========================
EBAY_CLIENT_ID = os.environ["EBAY_CLIENT_ID"]
EBAY_CLIENT_SECRET = os.environ["EBAY_CLIENT_SECRET"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# =========================
# SEEN FILE
# =========================
# Safer than __file__ in environments like IDLE
SEEN_FILE = Path.cwd() / "seen_items.json"

# =========================
# TELEGRAM
# =========================
def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    r = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    if not r.ok:
        raise RuntimeError(f"Telegram error {r.status_code}: {r.text}")

# =========================
# EBAY TOKEN
# =========================
def get_ebay_token() -> str:
    url = "https://api.ebay.com/identity/v1/oauth2/token"

    r = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        auth=(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )

    if not r.ok:
        raise RuntimeError(f"eBay token error {r.status_code}: {r.text}")

    data = r.json()

    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token in eBay response: {data}")

    return access_token

# =========================
# SEEN ITEMS
# =========================
def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()

    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
        return set()
    except Exception:
        return set()

def save_seen(seen: set[str]) -> None:
    SEEN_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

# =========================
# HELPERS
# =========================
def parse_price_value(price_info) -> float | None:
    if not price_info:
        return None

    value = price_info.get("value")
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None

# =========================
# EBAY SEARCH
# =========================
def search_ebay(query: str, token: str) -> list[dict]:
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    params = {
        "q": query,
        "limit": 50,
        "sort": "newlyListed",
        "filter": "buyingOptions:{AUCTION|FIXED_PRICE}",
    }

    r = requests.get(url, headers=headers, params=params, timeout=30)

    if not r.ok:
        raise RuntimeError(f"eBay search error {r.status_code}: {r.text}")

    data = r.json()
    return data.get("itemSummaries", [])

# =========================
# MAIN CHECK
# =========================
def check() -> None:
    token = get_ebay_token()
    seen = load_seen()
    new_items = []
    seen_this_run = set()

    for term in SEARCH_TERMS:
        items = search_ebay(term, token)
        print(f"[DEBUG] {term}: {len(items)} results")

        for item in items:
            item_id = item.get("itemId")
            if not item_id:
                continue

            # avoid duplicates across different search terms in same run
            if item_id in seen_this_run:
                continue
            seen_this_run.add(item_id)

            if item_id in seen:
                continue

            title = item.get("title", "No title")

            price_info = item.get("price")
            price_value = parse_price_value(price_info)
            currency = price_info.get("currency", "") if price_info else ""

            if price_value is None:
                price_text = "No price"
            else:
                price_text = str(price_value)

            if price_value is not None and price_value < MIN_PRICE:
                print(f"[DEBUG] Skipped under {MIN_PRICE}: {title} / {price_text} {currency}")
                continue

            link = item.get("itemWebUrl", "No link")

            message = (
                f"🧚 NEW ELINA FOUND\n\n"
                f"Title:\n{title}\n\n"
                f"Price:\n{price_text} {currency}\n\n"
                f"Link:\n{link}"
            )

            new_items.append(message)
            seen.add(item_id)

    save_seen(seen)

    print(f"[DEBUG] New items to send: {len(new_items)}")

    for m in new_items:
        send_telegram(m)

# =========================
# LOOP
# =========================
def main() -> None:
    if SEND_STARTUP_MESSAGE:
        try:
            send_telegram("✅ Elina bot started.")
        except Exception as e:
            print("Startup Telegram error:", e)

    while True:
        try:
            check()
        except Exception as e:
            print("Error:", e)
            try:
                send_telegram(f"⚠️ Bot error:\n{e}")
            except Exception as telegram_error:
                print("Failed to send Telegram error:", telegram_error)

        time.sleep(CHECK_EVERY_SECONDS)

if __name__ == "__main__":
    main()
