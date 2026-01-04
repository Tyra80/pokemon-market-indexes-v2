# check_november_data.py
from scripts.utils import get_db_client

client = get_db_client()

# Vérifie les données de fin novembre / début décembre
dates_to_check = [
    "2025-11-28", "2025-11-29", "2025-11-30",
    "2025-12-01", "2025-12-02", "2025-12-03", "2025-12-04", "2025-12-05", "2025-12-06"
]

print("Données par date:")
for d in dates_to_check:
    response = client.from_("card_prices_daily") \
        .select("card_id", count="exact") \
        .eq("price_date", d) \
        .execute()
    print(f"  {d}: {response.count} cartes")