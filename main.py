import os
import requests
import json
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
    "Barbie Fairytopia Elina NRFB",
    "Fairytopia Elina",
    "Elina doll Mattel",
    "Barbie Elina Fairytopia",
    "Mattel Fairytopia Elina"
]

SEEN_FILE = Path(__file__).with_name("seen_items.json")


# =========================
# TELEGRAM MESSAGE
# =========================
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    r = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        }
    )

    print("Telegram status:", r.status_code)
    print("Telegram response:", r.text)


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

    print("eBay token status:", r.status_code)
    print("eBay token response:", r.text)

    r.raise_for_status()
    return r.json()["access_token"]


# =========================
# LOAD SEEN ITEMS
# =========================
def load_seen():
    # TEMPORARY RESET MODE FOR TESTING
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(list(seen)))


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

    print("\n=========================")
    print("QUERY:", query)
    print("SEARCH STATUS:", r.status_code)
    print("SEARCH URL:", r.url)
    print("SEARCH RESPONSE:", r.text[:1000])

    r.raise_for_status()

    data = r.json()
    items = data.get("itemSummaries", [])

    print("RESULT COUNT:", len(items))

    return items


# =========================
# MAIN CHECK
# =========================
def check():
    token = get_ebay_token()
    seen = load_seen()

    print("Seen count at start:", len(seen))

    new_items = []

    for term in SEARCH_TERMS:
        items = search_ebay(term, token)

        for item in items:
            item_id = item["itemId"]

            if item_id not in seen:
                title = item.get("title", "No title")

                price_info = item.get("price")
                if price_info:
                    price = price_info.get("value", "?")
                    currency = price_info.get("currency", "")
                else:
                    price = "No price"
                    currency = ""

                link = item.get("itemWebUrl", "No link")

                message = f"""🧚 NEW ELINA FOUND

Title:
{title}

Price:
{price} {currency}

Link:
{link}
"""

                print("NEW ITEM FOUND:", title)

                new_items.append(message)
                seen.add(item_id)
            else:
                print("ALREADY SEEN:", item.get("title", "No title"))

    save_seen(seen)

    print("\nTOTAL NEW ITEMS TO SEND:", len(new_items))

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
