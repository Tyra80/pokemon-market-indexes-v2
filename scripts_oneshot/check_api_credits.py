"""Check remaining API credits."""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config.settings import PPT_API_KEY

BASE_URL = "https://www.pokemonpricetracker.com/api/v2"
HEADERS = {"Authorization": f"Bearer {PPT_API_KEY}"}

# Lightweight request to check credits
response = requests.get(
    f"{BASE_URL}/cards",
    headers=HEADERS,
    params={"set": "Base Set", "limit": 1},
    timeout=30
)

# Daily limits
daily_remaining = response.headers.get("X-Ratelimit-Daily-Remaining", "?")
daily_limit = response.headers.get("X-Ratelimit-Daily-Limit", "?")
daily_reset = response.headers.get("X-Ratelimit-Daily-Reset")

# Minute limits
minute_remaining = response.headers.get("X-Ratelimit-Minute-Remaining", "?")
minute_limit = response.headers.get("X-Ratelimit-Minute-Limit", "?")

print(f"📊 API Credits")
print(f"   Daily:  {daily_remaining} / {daily_limit}")
print(f"   Minute: {minute_remaining} / {minute_limit}")

if daily_reset:
    reset_time = datetime.fromtimestamp(int(daily_reset))
    print(f"   Reset:  {reset_time.strftime('%Y-%m-%d %H:%M')}")
