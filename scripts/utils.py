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
    DISCORD_WEBHOOK_URL
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
        dict: {"saved": int, "failed": int, "errors": list}
    """
    saved = 0
    failed = 0
    errors = []

    total_batches = (len(rows) + batch_size - 1) // batch_size

    for batch_num, i in enumerate(range(0, len(rows), batch_size), 1):
        batch = rows[i:i + batch_size]

        try:
            if on_conflict:
                client.from_(table).upsert(batch, on_conflict=on_conflict).execute()
            else:
                client.from_(table).upsert(batch).execute()
            saved += len(batch)
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️ Batch {batch_num}/{total_batches} failed for table '{table}': {error_msg[:100]}")

            # Fall back to one-by-one insert with error tracking
            batch_saved = 0
            batch_failed = 0

            for row in batch:
                try:
                    if on_conflict:
                        client.from_(table).upsert(row, on_conflict=on_conflict).execute()
                    else:
                        client.from_(table).upsert(row).execute()
                    saved += 1
                    batch_saved += 1
                except Exception as row_error:
                    failed += 1
                    batch_failed += 1
                    # Track first few errors for debugging
                    if len(errors) < 5:
                        # Get identifier from row for debugging
                        row_id = row.get("card_id") or row.get("item_id") or row.get("id") or "unknown"
                        errors.append({
                            "row_id": row_id,
                            "error": str(row_error)[:200]
                        })

            if batch_failed > 0:
                print(f"   ⚠️ Individual insert: {batch_saved} saved, {batch_failed} failed")

    # Log summary if there were failures
    if failed > 0:
        print(f"   ⚠️ batch_upsert to '{table}': {saved} saved, {failed} failed")
        if errors:
            print(f"   ⚠️ Sample errors:")
            for err in errors[:3]:
                print(f"      - {err['row_id']}: {err['error'][:80]}")

    return {"saved": saved, "failed": failed, "errors": errors}


# ============================================================
# Run Logging
# ============================================================

def log_run_start(client, run_type: str) -> int:
    """
    Records the start of a run.

    Returns:
        int: Run ID, or None if logging failed
    """
    try:
        response = client.from_("run_logs").insert({
            "run_type": run_type,
            "status": "running"
        }).execute()
        return response.data[0]["id"]
    except Exception as e:
        print(f"   ⚠️ Could not log run start: {str(e)[:100]}")
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
            update_data["error_message"] = error_message[:500]
        if details:
            update_data["details"] = details

        client.from_("run_logs").update(update_data).eq("id", run_id).execute()
    except Exception as e:
        print(f"   ⚠️ Could not log run end: {str(e)[:100]}")


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
            "description": description[:2000],  # Discord limit
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Pokemon Market Indexes v2"}
        }]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Log but don't fail the main process
        print(f"   ⚠️ Discord notification failed: {str(e)[:100]}")


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
