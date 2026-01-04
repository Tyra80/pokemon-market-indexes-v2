"""
Pokemon Market Indexes v2 - Fetch FX Rates
==========================================
Récupère les taux de change EUR/USD depuis l'API Frankfurter (BCE).

Usage:
    python scripts/fetch_fx_rates.py
"""

import sys
import os
import requests
from datetime import date, timedelta

# Imports locaux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert, log_run_start, log_run_end,
    send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import FRANKFURTER_URL


def fetch_latest_rate() -> dict:
    """Récupère le dernier taux EUR/USD."""
    url = f"{FRANKFURTER_URL}/latest"
    params = {"from": "EUR", "to": "USD"}
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    return {
        "date": data["date"],
        "eurusd": data["rates"]["USD"]
    }


def fetch_historical_rates(start_date: str, end_date: str) -> list:
    """
    Récupère les taux historiques entre deux dates.
    
    Args:
        start_date: Date de début (YYYY-MM-DD)
        end_date: Date de fin (YYYY-MM-DD)
    
    Returns:
        Liste de {"date": str, "eurusd": float}
    """
    url = f"{FRANKFURTER_URL}/{start_date}..{end_date}"
    params = {"from": "EUR", "to": "USD"}
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    rates = []
    
    for rate_date, rate_values in data.get("rates", {}).items():
        rates.append({
            "date": rate_date,
            "eurusd": rate_values["USD"]
        })
    
    return sorted(rates, key=lambda x: x["date"])


def save_fx_rates(client, rates: list) -> dict:
    """Sauvegarde les taux dans la base."""
    rows = [
        {
            "rate_date": r["date"],
            "eurusd": r["eurusd"],
            "source": "ecb"
        }
        for r in rates
    ]
    
    return batch_upsert(client, "fx_rates_daily", rows, on_conflict="rate_date")


def main():
    print_header("🔄 Pokemon Market Indexes - Fetch FX Rates")
    print(f"📅 Date : {get_today()}")
    
    # Connexion
    print_step(1, "Connexion à Supabase")
    try:
        client = get_db_client()
        print_success("Connecté à Supabase")
    except Exception as e:
        print_error(f"Connexion échouée : {e}")
        return
    
    # Log du run
    run_id = log_run_start(client, "fetch_fx")
    
    try:
        # Récupère les 30 derniers jours
        print_step(2, "Récupération des taux FX")
        
        today = date.today()
        start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        
        rates = fetch_historical_rates(start_date, end_date)
        print_success(f"{len(rates)} taux récupérés")
        
        # Sauvegarde
        print_step(3, "Sauvegarde dans Supabase")
        result = save_fx_rates(client, rates)
        print_success(f"{result['saved']} taux sauvegardés")
        
        if result['failed'] > 0:
            print_error(f"{result['failed']} échecs")
        
        # Vérification
        print_step(4, "Vérification")
        response = client.from_("fx_rates_daily") \
            .select("*") \
            .order("rate_date", desc=True) \
            .limit(5) \
            .execute()
        
        print("📊 Derniers taux :")
        for row in response.data:
            print(f"   {row['rate_date']} : {row['eurusd']}")
        
        # Log succès
        log_run_end(client, run_id, "success", 
                    records_processed=result['saved'],
                    records_failed=result['failed'])
        
        # Notification Discord
        send_discord_notification(
            "✅ FX Rates - Succès",
            f"{result['saved']} taux de change mis à jour."
        )
        
        print()
        print_success("Script terminé avec succès !")
        
    except Exception as e:
        print_error(f"Erreur : {e}")
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ FX Rates - Échec",
            f"Erreur : {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()
