"""
Pokemon Market Indexes v2 - Calculate Index (Laspeyres Chain-Linking)
=====================================================================
Calcule les valeurs des indices Pokemon Market avec la méthode Laspeyres.

Méthode:
- Rebalancement mensuel des constituants
- Calcul hebdomadaire de la valeur
- Chain-linking Laspeyres: Index_t = Index_{t-1} × Σ(w_i × P_i,t) / Σ(w_i × P_i,t-1)

Indices calculés:
- RARE_100 : Top 100 cartes rares par score (price × liquidity)
- RARE_500 : Top 500 cartes rares
- RARE_ALL : Toutes les cartes rares liquides

Usage:
    python scripts/calculate_index.py
    python scripts/calculate_index.py --rebalance  # Force le rebalancement mensuel
"""

import sys
import os
import argparse
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Imports locaux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import INDEX_CONFIG, RARE_RARITIES, OUTLIER_RULES


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_latest_price_date(client) -> str:
    """Récupère la date la plus récente avec des prix."""
    response = client.from_("card_prices_daily") \
        .select("price_date") \
        .order("price_date", desc=True) \
        .limit(1) \
        .execute()
    
    if response.data:
        return response.data[0]["price_date"]
    return get_today()


def get_current_month() -> str:
    """Retourne le premier jour du mois courant."""
    return date.today().replace(day=1).strftime("%Y-%m-%d")


def get_previous_month() -> str:
    """Retourne le premier jour du mois précédent."""
    first_of_current = date.today().replace(day=1)
    last_of_previous = first_of_current - timedelta(days=1)
    return last_of_previous.replace(day=1).strftime("%Y-%m-%d")


# =============================================================================
# DATA LOADING
# =============================================================================

def get_cards_with_prices(client, price_date: str) -> list:
    """
    Récupère toutes les cartes avec leurs prix NM du jour spécifié.
    Utilise nm_price comme référence (Near Mint = notre standard).
    Pagine pour récupérer toutes les données (Supabase limite à 1000).
    """
    # Récupère TOUS les prix du jour avec pagination
    all_prices = []
    offset = 0
    limit = 1000
    
    while True:
        response = client.from_("card_prices_daily") \
            .select("card_id, market_price, nm_price, nm_listings, total_listings, liquidity_score") \
            .eq("price_date", price_date) \
            .not_.is_("nm_price", "null") \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_prices.extend(response.data)
        
        if len(response.data) < limit:
            break
        
        offset += limit
    
    prices_by_card = {p["card_id"]: p for p in all_prices}
    
    # Récupère TOUTES les cartes éligibles avec pagination
    all_cards = []
    offset = 0
    
    while True:
        response = client.from_("cards") \
            .select("card_id, name, set_id, rarity, is_eligible") \
            .eq("is_eligible", True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        if not response.data:
            break
        
        all_cards.extend(response.data)
        
        if len(response.data) < limit:
            break
        
        offset += limit
    
    # Fusionne - utilise nm_price comme prix de référence
    result = []
    for card in all_cards:
        card_id = card["card_id"]
        if card_id in prices_by_card:
            price_data = prices_by_card[card_id]
            
            # Prix de référence = NM price (Near Mint)
            ref_price = price_data.get("nm_price") or price_data.get("market_price")
            
            if ref_price and ref_price > 0:
                result.append({
                    "card_id": card_id,
                    "name": card["name"],
                    "set_id": card["set_id"],
                    "rarity": card["rarity"],
                    "price": float(ref_price),  # Prix NM
                    "market_price": float(price_data.get("market_price") or ref_price),
                    "liquidity_score": float(price_data.get("liquidity_score") or 0),
                    "nm_listings": int(price_data.get("nm_listings") or 0),
                    "total_listings": int(price_data.get("total_listings") or 0),
                })
    
    return result


def get_prices_for_date(client, card_ids: list, price_date: str) -> dict:
    """Récupère les prix NM pour une liste de cartes à une date donnée."""
    if not card_ids:
        return {}
    
    prices = {}
    batch_size = 100  # Réduit pour éviter les erreurs de query trop longue
    
    for i in range(0, len(card_ids), batch_size):
        batch_ids = card_ids[i:i + batch_size]
        
        response = client.from_("card_prices_daily") \
            .select("card_id, nm_price, market_price") \
            .eq("price_date", price_date) \
            .in_("card_id", batch_ids) \
            .execute()
        
        for row in response.data:
            price = row.get("nm_price") or row.get("market_price")
            if price:
                prices[row["card_id"]] = float(price)
    
    return prices


# =============================================================================
# FILTERING & SELECTION
# =============================================================================

def filter_rare_cards(cards: list) -> list:
    """Filtre les cartes avec rareté >= Rare."""
    return [c for c in cards if c.get("rarity") in RARE_RARITIES]


def filter_outliers(cards: list) -> list:
    """Filtre les outliers selon les règles définies."""
    min_price = OUTLIER_RULES.get("min_price", 0.10)
    max_price = OUTLIER_RULES.get("max_price", 100000)
    
    return [c for c in cards if min_price <= c.get("price", 0) <= max_price]


def calculate_ranking_score(card: dict) -> float:
    """
    Calcule le ranking score pour le classement.
    Formule: price × liquidity_score
    """
    return card.get("price", 0) * card.get("liquidity_score", 0)


def select_constituents(cards: list, index_code: str) -> list:
    """
    Sélectionne les constituants d'un index.
    """
    config = INDEX_CONFIG.get(index_code, {})
    
    # Calcule le ranking score pour chaque carte
    for card in cards:
        card["ranking_score"] = calculate_ranking_score(card)
    
    # Filtre par seuil de liquidité
    threshold = config.get("liquidity_threshold_entry", 0.40)
    eligible = [c for c in cards if c.get("liquidity_score", 0) >= threshold]
    
    # Trie par ranking score décroissant
    eligible.sort(key=lambda x: x.get("ranking_score", 0), reverse=True)
    
    # Sélectionne le top N
    size = config.get("size")
    if size:
        return eligible[:size]
    else:
        return eligible  # RARE_ALL: toutes les cartes éligibles


def calculate_weights(constituents: list) -> list:
    """
    Calcule les poids de chaque constituant.
    Méthode: Capitalisation (price-weighted)
    weight_i = price_i / sum(prices)
    """
    total_price = sum(c.get("price", 0) for c in constituents)
    
    if total_price == 0:
        equal_weight = 1.0 / len(constituents) if constituents else 0
        for c in constituents:
            c["weight"] = equal_weight
        return constituents
    
    for c in constituents:
        c["weight"] = c.get("price", 0) / total_price
    
    return constituents


# =============================================================================
# LASPEYRES CHAIN-LINKING
# =============================================================================

def get_previous_index_data(client, index_code: str) -> dict:
    """
    Récupère les données de l'index à la période précédente.
    Returns: {value, date, constituents: [{card_id, weight, price}]}
    """
    # Dernière valeur
    response = client.from_("index_values_weekly") \
        .select("index_value, week_date") \
        .eq("index_code", index_code) \
        .order("week_date", desc=True) \
        .limit(1) \
        .execute()
    
    if not response.data:
        return None
    
    prev_value = response.data[0]["index_value"]
    prev_date = response.data[0]["week_date"]
    
    # Constituants du mois en cours (ou précédent si début de mois)
    current_month = get_current_month()
    
    response = client.from_("constituents_monthly") \
        .select("item_id, weight, composite_price") \
        .eq("index_code", index_code) \
        .eq("month", current_month) \
        .execute()
    
    # Si pas de constituants ce mois, essaie le mois précédent
    if not response.data:
        prev_month = get_previous_month()
        response = client.from_("constituents_monthly") \
            .select("item_id, weight, composite_price") \
            .eq("index_code", index_code) \
            .eq("month", prev_month) \
            .execute()
    
    constituents = []
    for row in response.data:
        constituents.append({
            "card_id": row["item_id"],
            "weight": float(row["weight"]) if row["weight"] else 0,
            "price": float(row["composite_price"]) if row["composite_price"] else 0,
        })
    
    return {
        "value": float(prev_value),
        "date": prev_date,
        "constituents": constituents,
    }


def calculate_index_laspeyres(client, index_code: str, constituents: list, 
                               current_date: str) -> tuple:
    """
    Calcule la valeur de l'index avec la méthode Laspeyres chain-linking.
    
    Formule:
    Index_t = Index_{t-1} × [Σ(w_i × P_i,t) / Σ(w_i × P_i,t-1)]
    
    où:
    - w_i = poids du constituant i (fixé au rebalancement)
    - P_i,t = prix du constituant i à la date t
    - P_i,t-1 = prix du constituant i à la date t-1
    
    Returns: (index_value, details_dict)
    """
    # Récupère les données précédentes
    prev_data = get_previous_index_data(client, index_code)
    
    # Premier calcul = base 100
    if prev_data is None or not prev_data.get("constituents"):
        return 100.0, {"method": "base", "reason": "first_calculation"}
    
    prev_value = prev_data["value"]
    prev_date = prev_data["date"]
    prev_constituents = prev_data["constituents"]
    
    # Si même date, pas de changement
    if prev_date == current_date:
        return prev_value, {"method": "same_date", "reason": "no_change"}
    
    # Récupère les prix actuels pour les constituants précédents
    card_ids = [c["card_id"] for c in prev_constituents]
    current_prices = get_prices_for_date(client, card_ids, current_date)
    
    # Calcule le ratio Laspeyres
    numerator = 0.0    # Σ(w_i × P_i,t)
    denominator = 0.0  # Σ(w_i × P_i,t-1)
    matched_count = 0
    
    for pc in prev_constituents:
        card_id = pc["card_id"]
        weight = pc["weight"]
        prev_price = pc["price"]
        
        if card_id in current_prices and prev_price > 0:
            current_price = current_prices[card_id]
            
            numerator += weight * current_price
            denominator += weight * prev_price
            matched_count += 1
    
    # Vérification
    if denominator == 0 or matched_count < len(prev_constituents) * 0.5:
        # Pas assez de données pour un calcul fiable
        # Fallback: utilise la moyenne des variations disponibles
        if matched_count > 0:
            ratio = numerator / denominator if denominator > 0 else 1.0
            new_value = prev_value * ratio
            return round(new_value, 4), {
                "method": "laspeyres_partial",
                "matched": matched_count,
                "total": len(prev_constituents),
                "ratio": round(ratio, 6),
            }
        else:
            return prev_value, {"method": "fallback", "reason": "no_price_match"}
    
    # Calcul Laspeyres
    ratio = numerator / denominator
    new_value = prev_value * ratio
    
    return round(new_value, 4), {
        "method": "laspeyres",
        "matched": matched_count,
        "total": len(prev_constituents),
        "ratio": round(ratio, 6),
        "change_pct": round((ratio - 1) * 100, 4),
    }


# =============================================================================
# PERSISTENCE
# =============================================================================

def save_constituents(client, index_code: str, month: str, constituents: list) -> int:
    """Sauvegarde les constituants du mois."""
    if not constituents:
        return 0
    
    rows = []
    for i, c in enumerate(constituents, 1):
        rows.append({
            "index_code": index_code,
            "month": month,
            "item_type": "card",
            "item_id": c["card_id"],
            "composite_price": round(c.get("price", 0), 2),
            "liquidity_score": round(c.get("liquidity_score", 0), 4),
            "ranking_score": round(c.get("ranking_score", 0), 4),
            "rank": i,
            "weight": round(c.get("weight", 0), 8),
            "is_new": True,
        })
    
    # Supprime les anciens constituants pour ce mois
    try:
        client.from_("constituents_monthly") \
            .delete() \
            .eq("index_code", index_code) \
            .eq("month", month) \
            .execute()
    except:
        pass
    
    # Insère les nouveaux
    result = batch_upsert(client, "constituents_monthly", rows)
    return result["saved"]


def save_index_value(client, index_code: str, week_date: str, 
                     value: float, n_constituents: int, market_cap: float,
                     details: dict = None) -> bool:
    """Sauvegarde la valeur de l'index."""
    try:
        # Calcule les variations
        change_1w = None
        change_1m = None
        
        # Variation 1 semaine
        prev_week = (date.fromisoformat(week_date) - timedelta(days=7)).strftime("%Y-%m-%d")
        response = client.from_("index_values_weekly") \
            .select("index_value") \
            .eq("index_code", index_code) \
            .eq("week_date", prev_week) \
            .execute()
        
        if response.data and response.data[0]["index_value"]:
            prev_val = float(response.data[0]["index_value"])
            if prev_val > 0:
                change_1w = round((value - prev_val) / prev_val * 100, 4)
        
        # Variation 1 mois (4 semaines)
        prev_month_date = (date.fromisoformat(week_date) - timedelta(days=28)).strftime("%Y-%m-%d")
        response = client.from_("index_values_weekly") \
            .select("index_value") \
            .eq("index_code", index_code) \
            .eq("week_date", prev_month_date) \
            .execute()
        
        if response.data and response.data[0]["index_value"]:
            prev_val = float(response.data[0]["index_value"])
            if prev_val > 0:
                change_1m = round((value - prev_val) / prev_val * 100, 4)
        
        # Upsert
        client.from_("index_values_weekly").upsert({
            "index_code": index_code,
            "week_date": week_date,
            "index_value": round(value, 4),
            "n_constituents": n_constituents,
            "total_market_cap": round(market_cap, 2) if market_cap else None,
            "change_1w": change_1w,
            "change_1m": change_1m,
        }, on_conflict="index_code,week_date").execute()
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ Erreur sauvegarde: {e}")
        return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebalance", action="store_true", 
                        help="Force le rebalancement mensuel")
    args = parser.parse_args()
    
    print_header("📊 Pokemon Market Indexes - Calculate Index (Laspeyres)")
    print(f"📅 Date : {get_today()}")
    print(f"🔄 Rebalancement forcé : {'Oui' if args.rebalance else 'Non'}")
    
    # Connexion
    print_step(1, "Connexion à Supabase")
    try:
        client = get_db_client()
        print_success("Connecté à Supabase")
    except Exception as e:
        print_error(f"Connexion échouée : {e}")
        return
    
    # Log du run
    run_id = log_run_start(client, "calculate_index")
    
    try:
        # Date des prix
        print_step(2, "Recherche des prix")
        price_date = get_latest_price_date(client)
        print_success(f"Date des prix : {price_date}")
        
        current_month = get_current_month()
        print(f"   Mois courant : {current_month}")
        
        # Vérifie si rebalancement nécessaire
        need_rebalance = args.rebalance
        
        if not need_rebalance:
            # Vérifie s'il existe des constituants pour ce mois
            response = client.from_("constituents_monthly") \
                .select("index_code", count="exact") \
                .eq("month", current_month) \
                .limit(1) \
                .execute()
            
            if response.count == 0:
                need_rebalance = True
                print("   → Pas de constituants ce mois, rebalancement nécessaire")
        
        # Charge les cartes avec prix
        print_step(3, "Chargement des données")
        all_cards = get_cards_with_prices(client, price_date)
        print_success(f"{len(all_cards)} cartes avec prix NM")
        
        # Filtre les cartes rares
        rare_cards = filter_rare_cards(all_cards)
        print(f"   Cartes rares (>= Rare) : {len(rare_cards)}")
        
        # Filtre les outliers
        rare_cards = filter_outliers(rare_cards)
        print(f"   Après filtre outliers : {len(rare_cards)}")
        
        if not rare_cards:
            print_error("Aucune carte éligible !")
            return
        
        # Calcule chaque index
        print_step(4, "Calcul des indices")
        
        results = {}
        
        for index_code in ["RARE_100", "RARE_500", "RARE_ALL"]:
            print(f"\n   {'='*50}")
            print(f"   📈 {index_code}")
            print(f"   {'='*50}")
            
            # Rebalancement si nécessaire
            if need_rebalance:
                print(f"   🔄 Rebalancement...")
                
                # Sélectionne les constituants
                constituents = select_constituents(rare_cards.copy(), index_code)
                
                if not constituents:
                    print(f"   ⚠️ Aucun constituant")
                    continue
                
                # Calcule les poids
                constituents = calculate_weights(constituents)
                
                # Sauvegarde
                saved = save_constituents(client, index_code, current_month, constituents)
                print(f"   ✅ {saved} constituants sauvegardés")
            else:
                # Charge les constituants existants
                response = client.from_("constituents_monthly") \
                    .select("item_id, weight, composite_price, liquidity_score, ranking_score") \
                    .eq("index_code", index_code) \
                    .eq("month", current_month) \
                    .order("rank") \
                    .execute()
                
                constituents = []
                for row in response.data:
                    # Retrouve le nom de la carte
                    card_info = next((c for c in all_cards if c["card_id"] == row["item_id"]), None)
                    constituents.append({
                        "card_id": row["item_id"],
                        "name": card_info["name"] if card_info else "Unknown",
                        "weight": float(row["weight"]) if row["weight"] else 0,
                        "price": float(row["composite_price"]) if row["composite_price"] else 0,
                        "liquidity_score": float(row["liquidity_score"]) if row["liquidity_score"] else 0,
                        "ranking_score": float(row["ranking_score"]) if row["ranking_score"] else 0,
                    })
                
                print(f"   📋 {len(constituents)} constituants chargés")
            
            if not constituents:
                continue
            
            # Calcul Laspeyres
            index_value, calc_details = calculate_index_laspeyres(
                client, index_code, constituents, price_date
            )
            
            # Market cap
            market_cap = sum(c.get("price", 0) for c in constituents)
            
            print(f"   ✅ Valeur : {index_value:.2f}")
            print(f"   ✅ Méthode : {calc_details.get('method')}")
            if "change_pct" in calc_details:
                change = calc_details["change_pct"]
                arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                print(f"   {arrow} Variation : {change:+.2f}%")
            print(f"   💰 Market cap : ${market_cap:,.2f}")
            
            # Top 5
            print(f"\n   📋 Top 5 constituants :")
            display_constituents = constituents[:5]
            for i, c in enumerate(display_constituents, 1):
                name = c.get('name', 'Unknown')[:30]
                price = c.get('price', 0)
                liq = c.get('liquidity_score', 0)
                weight = c.get('weight', 0) * 100
                print(f"      {i}. {name:<30} ${price:>8.2f} | liq={liq:.2f} | w={weight:.2f}%")
            
            # Sauvegarde valeur
            save_index_value(client, index_code, price_date, index_value,
                           len(constituents), market_cap, calc_details)
            
            results[index_code] = {
                "value": index_value,
                "constituents": len(constituents),
                "market_cap": market_cap,
                "method": calc_details.get("method"),
                "change_pct": calc_details.get("change_pct"),
            }
        
        # Vérification finale
        print_step(5, "Vérification")
        
        response = client.from_("index_values_weekly") \
            .select("*") \
            .order("week_date", desc=True) \
            .order("index_code") \
            .limit(9) \
            .execute()
        
        print("\n   📊 Dernières valeurs :")
        for row in response.data:
            change = f"{row['change_1w']:+.2f}%" if row.get('change_1w') else "N/A"
            print(f"      {row['index_code']:<10} | {row['week_date']} | {row['index_value']:>8.2f} | {change:>8} | {row['n_constituents']} cartes")
        
        # Log succès
        log_run_end(client, run_id, "success",
                    records_processed=len(results),
                    details=results)
        
        # Notification Discord
        summary_lines = []
        for code, data in results.items():
            change_str = f" ({data['change_pct']:+.2f}%)" if data.get('change_pct') else ""
            summary_lines.append(f"• {code}: {data['value']:.2f}{change_str}")
        
        send_discord_notification(
            "✅ Index Calculation - Succès",
            f"Indices calculés pour {price_date}:\n" + "\n".join(summary_lines)
        )
        
        # Résumé final
        print()
        print_header("📊 RÉSUMÉ FINAL")
        for code, data in results.items():
            change_str = f" ({data['change_pct']:+.2f}%)" if data.get('change_pct') else ""
            print(f"   {code}: {data['value']:.2f}{change_str} | {data['constituents']} constituants | ${data['market_cap']:,.0f}")
        print()
        print_success("Script terminé avec succès !")
        
    except Exception as e:
        print_error(f"Erreur : {e}")
        import traceback
        traceback.print_exc()
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ Index Calculation - Échec",
            f"Erreur : {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()