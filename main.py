import requests
import json
import os
import time
from pathlib import Path
from datetime import datetime

# =========================
# EBAY API KEYS
# =========================
EBAY_CLIENT_ID = os.environ["EBAY_CLIENT_ID"]
EBAY_CLIENT_SECRET = os.environ["EBAY_CLIENT_SECRET"]

# =========================
# TELEGRAM
# =========================
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# =========================
# SETTINGS
# =========================
CHECK_INTERVAL_SECONDS = 120        # ✅ 2 minutes
PAUSE_BETWEEN_SEARCHES = 10         # small delay between queries
RATE_LIMIT_SLEEP = 1800             # 30 min if 429
REQUEST_TIMEOUT = 20
TOKEN_REFRESH_SECONDS = 3300        # ~55 min

SEARCH_TERMS = [
    "Barbie Fairytopia Elina",
    "Barbie Fairytopia",
    "Barbie Erika",
    "Barbie 12 Dancing Princesses",
    "Barbie Swan Lake 2003",
    "Barbie Nutcracker 2001"
]

SEEN_FILE = Path(__file__).with_name("seen_items.json")

EBAY_TOKEN = None
EBAY_TOKEN_TIME = 0
LAST_TELEGRAM_ERROR = ""
LAST_TELEGRAM_ERROR_TIME = 0


# =========================
# HELPERS
# =========================
def now():
    return datetime.now().strftime("%H:%M:%S")


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": False
            },
            timeout=REQUEST_TIMEOUT
        )
    except Exception as e:
        print(f"[{now()}] Telegram error: {e}", flush=True)


def send_error_once(error_text):
    global LAST_TELEGRAM_ERROR, LAST_TELEGRAM_ERROR_TIME

    current_time = time.time()

    if error_text == LAST_TELEGRAM_ERROR and current_time - LAST_TELEGRAM_ERROR_TIME < 1800:
        return

    LAST_TELEGRAM_ERROR = error_text
    LAST_TELEGRAM_ERROR_TIME = current_time
    send_telegram(f"⚠️ Bot error: {error_text}")


# =========================
# EBAY TOKEN
# =========================
def get_ebay_token():
    global EBAY_TOKEN, EBAY_TOKEN_TIME

    current_time = time.time()

    if EBAY_TOKEN and current_time - EBAY_TOKEN_TIME < TOKEN_REFRESH_SECONDS:
        return EBAY_TOKEN

    url = "https://api.ebay.com/identity/v1/oauth2/token"

    r = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        },
        auth=(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=REQUEST_TIMEOUT
    )

    if r.status_code != 200:
        raise Exception(f"Token error {r.status_code}")

    data = r.json()
    EBAY_TOKEN = data["access_token"]
    EBAY_TOKEN_TIME = current_time

    print(f"[{now()}] New token", flush=True)
    return EBAY_TOKEN


# =========================
# LOAD SEEN
# =========================
def load_seen():
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except:
        return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(list(seen)))


# =========================
# SEARCH
# =========================
def search_ebay(query, token):
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    params = {
        "q": query,
        "limit": 30,
        "sort": "newlyListed",
        "filter": "buyingOptions:{AUCTION|FIXED_PRICE}"
    }

    r = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

    if r.status_code == 429:
        print(f"[{now()}] 429 hit → sleeping", flush=True)
        time.sleep(RATE_LIMIT_SLEEP)
        return []

    if r.status_code == 401:
        global EBAY_TOKEN
        EBAY_TOKEN = None
        raise Exception("Token expired")

    if r.status_code != 200:
        raise Exception(f"Search error {r.status_code}")

    data = r.json()
    return data.get("itemSummaries", [])


# =========================
# MAIN
# =========================
def check():
    token = get_ebay_token()
    seen = load_seen()
    new_items = []

    print(f"[{now()}] Checking...", flush=True)

    for term in SEARCH_TERMS:
        items = search_ebay(term, token)

        for item in items:
            item_id = item.get("itemId")
            if not item_id or item_id in seen:
                continue

            title = item.get("title", "")
            link = item.get("itemWebUrl", "")

            price_info = item.get("price")
            if price_info:
                try:
                    price = float(price_info.get("value", 0))
                except:
                    price = 0
                currency = price_info.get("currency", "")
            else:
                price = 0
                currency = ""

            buying_options = item.get("buyingOptions", [])
            is_auction = "AUCTION" in buying_options
            is_fixed = "FIXED_PRICE" in buying_options

            if is_fixed and not is_auction and price < 100:
                seen.add(item_id)
                continue

            message = f"""🧚 NEW DOLL

{title}

{price:.2f} {currency}

{link}
"""

            new_items.append(message)
            seen.add(item_id)

        save_seen(seen)
        time.sleep(PAUSE_BETWEEN_SEARCHES)

    for m in new_items:
        send_telegram(m)
        time.sleep(2)

    print(f"[{now()}] Done. Found: {len(new_items)}", flush=True)


# =========================
# LOOP
# =========================
send_telegram("✅ Bot started")

while True:
    try:
        check()
    except Exception as e:
        err = str(e)
        print(f"[{now()}] ERROR: {err}", flush=True)

        if "429" in err:
            send_error_once("Rate limit → waiting")
            time.sleep(RATE_LIMIT_SLEEP)
        else:
            send_error_once(err)
            time.sleep(300)

    time.sleep(CHECK_INTERVAL_SECONDS)
