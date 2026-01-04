"""
Pokemon Market Indexes v2 - Fetch FX Rates
==========================================
Fetches EUR/USD exchange rates from Frankfurter API (free, unlimited).

Frankfurter API:
- Base URL: https://api.frankfurter.dev/v1
- Endpoints: /latest, /{date}
- No authentication required
- Unlimited requests

Usage:
    python scripts/fetch_fx_rates.py
"""

import sys
import os
import requests
from datetime import datetime, date, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client,
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import FRANKFURTER_URL


def fetch_latest_rate() -> dict:
    """
    Fetches the latest EUR/USD exchange rate.
    
    Returns:
        dict: {date: "YYYY-MM-DD", rate: float}
    """
    url = f"{FRANKFURTER_URL}/latest"
    params = {"from": "EUR", "to": "USD"}
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    return {
        "date": data.get("date"),
        "rate": data.get("rates", {}).get("USD"),
    }


def fetch_historical_rates(start_date: str, end_date: str) -> list:
    """
    Fetches historical EUR/USD rates for a date range.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        list: [{date: "YYYY-MM-DD", rate: float}, ...]
    """
    url = f"{FRANKFURTER_URL}/{start_date}..{end_date}"
    params = {"from": "EUR", "to": "USD"}
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    rates = []
    for rate_date, rate_data in data.get("rates", {}).items():
        rates.append({
            "date": rate_date,
            "rate": rate_data.get("USD"),
        })
    
    return sorted(rates, key=lambda x: x["date"])


def main():
    # Set date once at the start of the run
    today_str = get_today()
    today_date = date.fromisoformat(today_str)

    print_header("💱 Pokemon Market Indexes - Fetch FX Rates")
    print(f"📅 Date: {today_str}")
    print(f"🌐 Source: Frankfurter API (free)")
    print()

    # Connection
    print_step(1, "Connecting to Supabase")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return
    
    # Log run
    run_id = log_run_start(client, "fetch_fx_rates")
    
    try:
        # Fetch latest rate
        print_step(2, "Fetching latest EUR/USD rate")
        latest = fetch_latest_rate()
        print_success(f"EUR/USD = {latest['rate']:.4f} ({latest['date']})")
        
        # Check last rate in database
        print_step(3, "Checking database")
        response = client.from_("fx_rates_daily") \
            .select("rate_date") \
            .order("rate_date", desc=True) \
            .limit(1) \
            .execute()
        
        rates_to_save = []
        
        if response.data:
            last_date = response.data[0]["rate_date"]
            print(f"   Last rate in DB: {last_date}")
            
            # Calculate missing days
            last = date.fromisoformat(last_date)

            if last < today_date - timedelta(days=1):
                # Fetch missing days
                start = (last + timedelta(days=1)).strftime("%Y-%m-%d")
                end = today_str
                
                print(f"   Fetching missing rates: {start} to {end}")
                historical = fetch_historical_rates(start, end)
                
                for rate in historical:
                    rates_to_save.append({
                        "rate_date": rate["date"],
                        "eurusd": rate["rate"],
                    })
                
                print_success(f"{len(historical)} missing rates fetched")
        else:
            # First run - fetch last 30 days
            print("   Empty database, fetching last 30 days")
            start = (today_date - timedelta(days=30)).strftime("%Y-%m-%d")
            end = today_str
            
            historical = fetch_historical_rates(start, end)
            
            for rate in historical:
                rates_to_save.append({
                    "rate_date": rate["date"],
                    "eurusd": rate["rate"],
                })
            
            print_success(f"{len(historical)} rates fetched")
        
        # Always add latest rate
        rates_to_save.append({
            "rate_date": latest["date"],
            "eurusd": latest["rate"],
        })
        
        # Save to database
        print_step(4, "Saving rates")
        
        saved = 0
        for rate in rates_to_save:
            try:
                client.from_("fx_rates_daily").upsert(
                    rate, on_conflict="rate_date"
                ).execute()
                saved += 1
            except Exception as e:
                print(f"   ⚠️ Error saving {rate['rate_date']}: {e}")
        
        print_success(f"{saved} rates saved")
        
        # Verification
        print_step(5, "Verification")
        
        response = client.from_("fx_rates_daily") \
            .select("*") \
            .order("rate_date", desc=True) \
            .limit(5) \
            .execute()
        
        print("   Last 5 rates:")
        for row in response.data:
            print(f"      {row['rate_date']} : EUR/USD = {row['eurusd']:.4f}")
        
        # Log success
        log_run_end(client, run_id, "success", records_processed=saved)
        
        # Discord notification (optional for FX)
        # send_discord_notification(
        #     "✅ Fetch FX Rates - Success",
        #     f"EUR/USD = {latest['rate']:.4f}\n{saved} rates saved"
        # )
        
        print()
        print_header("📊 SUMMARY")
        print(f"   Rates saved   : {saved}")
        print(f"   Latest rate   : EUR/USD = {latest['rate']:.4f}")
        print()
        print_success("Script completed successfully!")
        
    except Exception as e:
        print_error(f"Error: {e}")
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ Fetch FX Rates - Failed",
            f"Error: {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()
