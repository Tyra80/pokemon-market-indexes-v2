# debug_filter_steps.py
import sys
sys.path.insert(0, ".")

from scripts.utils import get_db_client
from config.settings import INDEX_CONFIG, RARE_RARITIES, OUTLIER_RULES

client = get_db_client()
price_date = "2026-01-04"

print("="*60)
print("ÉTAPE 1: Prix du jour")
print("="*60)
response = client.from_("card_prices_daily") \
    .select("card_id, market_price, nm_price, liquidity_score") \
    .eq("price_date", price_date) \
    .not_.is_("nm_price", "null") \
    .limit(5) \
    .execute()
print(f"Cartes avec nm_price: {len(response.data)} (limité à 5)")
for r in response.data:
    print(f"  {r}")

print("\n" + "="*60)
print("ÉTAPE 2: Jointure cards + prices")
print("="*60)

# Récupère quelques prix
prices_response = client.from_("card_prices_daily") \
    .select("card_id, nm_price, liquidity_score") \
    .eq("price_date", price_date) \
    .not_.is_("nm_price", "null") \
    .order("nm_price", desc=True) \
    .limit(10) \
    .execute()

print(f"Top 10 prix NM:")
for p in prices_response.data:
    # Cherche la carte
    card_resp = client.from_("cards") \
        .select("name, rarity") \
        .eq("card_id", p["card_id"]) \
        .execute()
    
    if card_resp.data:
        card = card_resp.data[0]
        rarity = card["rarity"]
        is_rare = rarity in RARE_RARITIES
        print(f"  ${p['nm_price']:>8} | liq={p['liquidity_score']:.2f} | {rarity:<25} | rare={is_rare} | {card['name'][:30]}")
    else:
        print(f"  ${p['nm_price']:>8} | card_id NOT FOUND: {p['card_id']}")

print("\n" + "="*60)
print("ÉTAPE 3: Filtre liquidité")
print("="*60)

threshold = INDEX_CONFIG["RARE_100"]["liquidity_threshold_entry"]
print(f"Seuil liquidité RARE_100: {threshold}")

# Compte les cartes par niveau de liquidité
response = client.from_("card_prices_daily") \
    .select("liquidity_score") \
    .eq("price_date", price_date) \
    .execute()

scores = [r["liquidity_score"] for r in response.data if r["liquidity_score"] is not None]
print(f"Total cartes avec liquidity_score: {len(scores)}")
print(f"  liq >= 0.60: {sum(1 for s in scores if s >= 0.60)}")
print(f"  liq >= 0.50: {sum(1 for s in scores if s >= 0.50)}")
print(f"  liq >= 0.40: {sum(1 for s in scores if s >= 0.40)}")
print(f"  liq >= 0.30: {sum(1 for s in scores if s >= 0.30)}")
print(f"  liq >= 0.20: {sum(1 for s in scores if s >= 0.20)}")
print(f"  liq >= 0.10: {sum(1 for s in scores if s >= 0.10)}")
print(f"  liq = 1.00: {sum(1 for s in scores if s == 1.0)}")

print("\n" + "="*60)
print("ÉTAPE 4: Cartes rares + liquides")
print("="*60)

# Cartes avec haute liquidité
high_liq = client.from_("card_prices_daily") \
    .select("card_id, nm_price, liquidity_score") \
    .eq("price_date", price_date) \
    .gte("liquidity_score", 0.60) \
    .order("nm_price", desc=True) \
    .limit(20) \
    .execute()

print(f"Cartes avec liq >= 0.60 (top 20 par prix):")
rare_count = 0
for p in high_liq.data:
    card_resp = client.from_("cards") \
        .select("name, rarity") \
        .eq("card_id", p["card_id"]) \
        .execute()
    
    if card_resp.data:
        card = card_resp.data[0]
        is_rare = card["rarity"] in RARE_RARITIES
        if is_rare:
            rare_count += 1
        print(f"  ${p['nm_price']:>8} | liq={p['liquidity_score']:.2f} | rare={is_rare} | {card['rarity']:<20} | {card['name'][:25]}")

print(f"\nCartes rares parmi celles-ci: {rare_count}/20")