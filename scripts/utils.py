"""
Pokemon Market Indexes v2 - Utilities
=====================================
Utility functions shared by all scripts.
"""

import os
import sys
import requests
from datetime import datetime, date, timedelta
from postgrest import SyncPostgrestClient

# Add parent folder to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    SUPABASE_URL, 
    SUPABASE_KEY, 
    PPT_API_KEY, 
    PPT_BASE_URL,
    DISCORD_WEBHOOK_URL,
    CONDITION_WEIGHTS,
    VOLUME_DECAY_WEIGHTS,
    VOLUME_DECAY_SUM,
    VOLUME_CAP,
    LIQUIDITY_CAP,
)


# ============================================================
# Database Client
# ============================================================

def get_db_client() -> SyncPostgrestClient:
    """
    Creates and returns a Supabase client.
    
    Returns:
        SyncPostgrestClient: Client connected to Supabase
    
    Raises:
        ValueError: If credentials are missing
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY missing in .env")
    
    return SyncPostgrestClient(
        base_url=f"{SUPABASE_URL}/rest/v1",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )


# ============================================================
# PokemonPriceTracker API Client
# ============================================================

def ppt_request(endpoint: str, params: dict = None) -> dict:
    """
    Makes a request to the PokemonPriceTracker API.
    
    Args:
        endpoint: API endpoint (e.g.: "/v2/cards")
        params: Request parameters
    
    Returns:
        dict: JSON response
    
    Raises:
        requests.HTTPError: If the request fails
    """
    url = f"{PPT_BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {PPT_API_KEY}",
        "X-API-Key": PPT_API_KEY,
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    
    return response.json()


# ============================================================
# Database Pagination Helper
# ============================================================

def fetch_all_paginated(client, table: str, select: str = "*", 
                        filters: dict = None, page_size: int = 1000) -> list:
    """
    Fetches all rows from a table with pagination.
    
    Args:
        client: Supabase client
        table: Table name
        select: Columns to select
        filters: Filters to apply {"column": "value"}
        page_size: Page size
    
    Returns:
        list: All rows
    """
    all_rows = []
    offset = 0
    
    while True:
        query = client.from_(table).select(select).range(offset, offset + page_size - 1)
        
        # Apply filters
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        
        response = query.execute()
        
        if not response.data:
            break
        
        all_rows.extend(response.data)
        
        if len(response.data) < page_size:
            break
        
        offset += page_size
    
    return all_rows


# ============================================================
# Batch Insert Helper
# ============================================================

def batch_upsert(client, table: str, rows: list, 
                 batch_size: int = 500, on_conflict: str = None) -> dict:
    """
    Inserts rows in batches with upsert.
    
    Args:
        client: Supabase client
        table: Table name
        rows: Rows to insert
        batch_size: Batch size
        on_conflict: Columns for upsert
    
    Returns:
        dict: {"saved": int, "failed": int}
    """
    saved = 0
    failed = 0
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        
        try:
            if on_conflict:
                client.from_(table).upsert(batch, on_conflict=on_conflict).execute()
            else:
                client.from_(table).upsert(batch).execute()
            saved += len(batch)
        except Exception as e:
            # On error, try one by one
            for row in batch:
                try:
                    if on_conflict:
                        client.from_(table).upsert(row, on_conflict=on_conflict).execute()
                    else:
                        client.from_(table).upsert(row).execute()
                    saved += 1
                except:
                    failed += 1
    
    return {"saved": saved, "failed": failed}


# ============================================================
# Run Logging
# ============================================================

def log_run_start(client, run_type: str) -> int:
    """
    Records the start of a run.
    
    Returns:
        int: Run ID
    """
    try:
        response = client.from_("run_logs").insert({
            "run_type": run_type,
            "status": "running"
        }).execute()
        return response.data[0]["id"]
    except:
        return None


def log_run_end(client, run_id: int, status: str, 
                records_processed: int = 0, records_failed: int = 0,
                error_message: str = None, details: dict = None):
    """
    Records the end of a run.
    """
    if not run_id:
        return
    
    try:
        update_data = {
            "finished_at": datetime.utcnow().isoformat(),
            "status": status,
            "records_processed": records_processed,
            "records_failed": records_failed,
        }
        if error_message:
            update_data["error_message"] = error_message
        if details:
            update_data["details"] = details
        
        client.from_("run_logs").update(update_data).eq("id", run_id).execute()
    except:
        pass


# ============================================================
# Discord Notifications
# ============================================================

def send_discord_notification(title: str, description: str, 
                              color: int = 5763719, success: bool = True):
    """
    Sends a Discord notification.
    
    Args:
        title: Message title
        description: Description
        color: Color (green by default)
        success: True=green, False=red
    """
    if not DISCORD_WEBHOOK_URL:
        return
    
    if not success:
        color = 15548997  # Red
    
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Market Indexes v2"}
        }]
    }
    
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except:
        pass


# ============================================================
# Date Helpers
# ============================================================

def get_today() -> str:
    """Returns today's date in YYYY-MM-DD format."""
    return date.today().strftime("%Y-%m-%d")


def get_current_month() -> str:
    """Returns the first day of the current month in YYYY-MM-DD format."""
    return date.today().replace(day=1).strftime("%Y-%m-%d")


def get_last_sunday() -> str:
    """Returns the date of the last Sunday in YYYY-MM-DD format."""
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    return last_sunday.strftime("%Y-%m-%d")


# ============================================================
# Print Helpers
# ============================================================

def print_header(title: str):
    """Displays a formatted header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step: int, title: str):
    """Displays a step."""
    print()
    print(f"📌 Step {step}: {title}")
    print("-" * 60)


def print_success(message: str):
    """Displays a success message."""
    print(f"✅ {message}")


def print_error(message: str):
    """Displays an error message."""
    print(f"❌ {message}")


def print_warning(message: str):
    """Displays a warning."""
    print(f"⚠️  {message}")


def print_progress(current: int, total: int, prefix: str = ""):
    """Displays progress."""
    pct = current * 100 // total if total > 0 else 0
    print(f"   ⏳ {prefix}{current}/{total} ({pct}%)")


# ============================================================
# Liquidity Calculation (B + C + D)
# ============================================================

def calculate_liquidity_from_listings(nm_listings: int, lp_listings: int = 0, 
                                       mp_listings: int = 0, hp_listings: int = 0,
                                       dmg_listings: int = 0) -> float:
    """
    Calculates liquidity score based on listings (Method B - fallback).
    
    Formula: weighted_listings / LIQUIDITY_CAP
    """
    weighted = (
        (nm_listings or 0) * CONDITION_WEIGHTS.get("Near Mint", 1.0) +
        (lp_listings or 0) * CONDITION_WEIGHTS.get("Lightly Played", 0.8) +
        (mp_listings or 0) * CONDITION_WEIGHTS.get("Moderately Played", 0.6) +
        (hp_listings or 0) * CONDITION_WEIGHTS.get("Heavily Played", 0.4) +
        (dmg_listings or 0) * CONDITION_WEIGHTS.get("Damaged", 0.2)
    )
    
    return min(weighted / LIQUIDITY_CAP, 1.0)


def calculate_liquidity_from_volume(volumes: list) -> float:
    """
    Calculates liquidity score with temporal decay (Method C).
    
    Args:
        volumes: List of volumes for the last 7 days [day0, day-1, day-2, ..., day-6]
                 May contain None for missing days
    
    Returns:
        float: Liquidity score between 0 and 1
    """
    if not volumes:
        return 0.0
    
    weighted_volume = 0.0
    weight_sum = 0.0
    
    for i, vol in enumerate(volumes[:7]):  # Max 7 days
        if vol is not None and vol > 0:
            weight = VOLUME_DECAY_WEIGHTS.get(i, 0.05)
            weighted_volume += vol * weight
            weight_sum += weight
    
    if weight_sum == 0:
        return 0.0
    
    # Normalize by sum of weights used and cap
    normalized_volume = weighted_volume / weight_sum
    
    return min(normalized_volume / VOLUME_CAP, 1.0)


def calculate_liquidity_smart(client, card_id: str, current_date: str,
                               nm_listings: int = 0, lp_listings: int = 0,
                               mp_listings: int = 0, hp_listings: int = 0,
                               dmg_listings: int = 0) -> tuple:
    """
    Calculates smart liquidity score (B + C combined).
    
    Priority:
    1. If volume history available → Method C (decay)
    2. Otherwise → Method B (listings)
    
    Args:
        client: Supabase client
        card_id: Card ID
        current_date: Current date (YYYY-MM-DD)
        nm_listings, lp_listings, etc.: Current listings (fallback)
    
    Returns:
        tuple: (liquidity_score, method_used)
    """
    from datetime import datetime, timedelta
    
    # Try to get volumes for last 7 days
    try:
        current = datetime.strptime(current_date, "%Y-%m-%d").date()
        dates = [(current - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        
        # Query to get volumes
        response = client.from_("card_prices_daily") \
            .select("price_date, daily_volume") \
            .eq("card_id", card_id) \
            .in_("price_date", dates) \
            .execute()
        
        if response.data:
            # Organize volumes by date
            volumes_by_date = {r["price_date"]: r.get("daily_volume") for r in response.data}
            volumes = [volumes_by_date.get(d) for d in dates]
            
            # Count days with volume
            valid_volumes = [v for v in volumes if v is not None and v > 0]
            
            if len(valid_volumes) >= 2:  # At least 2 days with data
                score = calculate_liquidity_from_volume(volumes)
                return round(score, 4), "volume_decay"
    
    except Exception as e:
        pass  # Fallback to listings
    
    # Fallback to listings
    score = calculate_liquidity_from_listings(nm_listings, lp_listings, mp_listings, hp_listings, dmg_listings)
    return round(score, 4), "listings_fallback"


def get_avg_volume_30d(client, card_id: str, current_date: str) -> float:
    """
    Calculates average volume over last 30 days (Method D - for rebalancing).
    
    Returns:
        float: Average daily volume (0 if no data)
    """
    from datetime import datetime, timedelta
    
    try:
        current = datetime.strptime(current_date, "%Y-%m-%d").date()
        start_date = (current - timedelta(days=30)).strftime("%Y-%m-%d")
        
        response = client.from_("card_prices_daily") \
            .select("daily_volume") \
            .eq("card_id", card_id) \
            .gte("price_date", start_date) \
            .lte("price_date", current_date) \
            .not_.is_("daily_volume", "null") \
            .execute()
        
        if response.data:
            volumes = [r["daily_volume"] for r in response.data if r["daily_volume"]]
            if volumes:
                return sum(volumes) / 30  # Average over 30 days
        
        return 0.0
        
    except Exception:
        return 0.0
