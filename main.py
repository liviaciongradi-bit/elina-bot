import requests
import json
import os
import time
from pathlib import Path

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
# SEARCH TERMS
# =========================
SEARCH_TERMS = [
    "Barbie Fairytopia Elina",
    "Barbie Fairytopia",
    "Barbie Erika",
    "Barbie 12 Dancing Princesses",
    "Barbie Merissa",
    "Mattel Swan Lake"
]

SEEN_FILE = Path(__file__).with_name("seen_items.json")


# =========================
# TELEGRAM MESSAGE
# =========================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        }
    )


# =========================
# EBAY TOKEN
# =========================
def get_ebay_token():

    url = "https://api.ebay.com/identity/v1/oauth2/token"

    r = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        },
        auth=(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET),
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    return r.json()["access_token"]


# =========================
# LOAD SEEN ITEMS
# =========================
def load_seen():

    if not SEEN_FILE.exists():
        return set()

    try:
        data = json.loads(SEEN_FILE.read_text())
        return set(data)

    except:
        return set()


def save_seen(seen):

    SEEN_FILE.write_text(
        json.dumps(list(seen))
    )


# =========================
# EBAY SEARCH
# =========================
def search_ebay(query, token):

    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    params = {
        "q": query,
        "limit": 50,
        "sort": "newlyListed",
        "filter": "buyingOptions:{AUCTION|FIXED_PRICE}"
    }

    r = requests.get(url, headers=headers, params=params)

    data = r.json()

    return data.get("itemSummaries", [])


# =========================
# MAIN CHECK
# =========================
def check():

    token = get_ebay_token()

    seen = load_seen()

    new_items = []

    for term in SEARCH_TERMS:

        items = search_ebay(term, token)

        for item in items:

            item_id = item["itemId"]

            if item_id not in seen:

                title = item["title"]

                price_info = item.get("price")
                if price_info:
                    price = price_info.get("value", "?")
                    currency = price_info.get("currency", "")
                else:
                    price = "No price"
                    currency = ""

                buying_options = item.get("buyingOptions", [])

                is_auction = "AUCTION" in buying_options
                is_fixed_price = "FIXED_PRICE" in buying_options

                # safest version:
                # skip only cheap pure fixed-price listings
                # keep auctions, and keep mixed cases
                if is_fixed_price and not is_auction and price < 100:
                    continue

                link = item["itemWebUrl"]

                message = f"""
🧚 NEW DOLL FOUND

Title:
{title}

Price:
{price} {currency}

Link:
{link}
"""

                new_items.append(message)

                seen.add(item_id)

    save_seen(seen)

    for m in new_items:
        send_telegram(m)


# =========================
# LOOP
# =========================
while True:

    try:

        check()

    except Exception as e:

        print("Error:", e)

    time.sleep(60)
