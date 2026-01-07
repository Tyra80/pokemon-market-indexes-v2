"""
Pokemon Market Indexes v2 - Reinitialize Index
===============================================
Full reinitialization of all indexes from scratch.

This script:
1. Verifies data availability (volumes, prices)
2. Clears existing index data (constituents + values)
3. Runs initialize_index.py to set base 100 at inception
4. Runs calculate_index_history.py to fill all historical values

Use this after:
- Major methodology changes
- Data corrections (backfill volumes, etc.)
- Fresh start needed

Usage:
    python scripts_oneshot/reinitialize_index.py
    python scripts_oneshot/reinitialize_index.py --skip-verify  # Skip verification
    python scripts_oneshot/reinitialize_index.py --dry-run      # Show what would be done
"""

import sys
import os
import argparse
from datetime import date, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import get_db_client, print_header, print_step, print_success, print_error
from config.settings import INCEPTION_DATE

# =============================================================================
# VERIFICATION
# =============================================================================

def verify_data_availability(client) -> bool:
    """Verify that we have sufficient data to reinitialize."""
    print_step(1, "Verifying data availability")

    issues = []

    # Check inception date has prices
    response = client.from_("card_prices_daily") \
        .select("card_id", count="exact") \
        .eq("price_date", INCEPTION_DATE) \
        .not_.is_("nm_price", "null") \
        .limit(1) \
        .execute()

    inception_cards = response.count or 0
    print(f"   Inception date ({INCEPTION_DATE}): {inception_cards} cards with NM price")

    if inception_cards < 1000:
        issues.append(f"Insufficient cards at inception ({inception_cards} < 1000)")

    # Check recent dates have volumes
    recent_dates = []
    today = date.today()
    for i in range(1, 8):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        recent_dates.append(d)

    print(f"\n   Checking volume data for recent dates:")
    for d in recent_dates[:5]:
        response = client.from_("card_prices_daily") \
            .select("card_id", count="exact") \
            .eq("price_date", d) \
            .not_.is_("daily_volume", "null") \
            .gt("daily_volume", 0) \
            .limit(1) \
            .execute()

        with_vol = response.count or 0
        status = "OK" if with_vol > 500 else "LOW" if with_vol > 0 else "MISSING"
        print(f"   {d}: {with_vol} cards with volume [{status}]")

        if with_vol < 100:
            issues.append(f"Low volume data for {d} ({with_vol} cards)")

    # Check eligible cards
    response = client.from_("cards") \
        .select("card_id", count="exact") \
        .eq("is_eligible", True) \
        .execute()

    eligible = response.count or 0
    print(f"\n   Eligible cards: {eligible}")

    if eligible < 100:
        issues.append(f"Too few eligible cards ({eligible} < 100)")

    if issues:
        print()
        print_error("Data verification failed:")
        for issue in issues:
            print(f"   - {issue}")
        return False

    print()
    print_success("Data verification passed!")
    return True


# =============================================================================
# CLEAR DATA
# =============================================================================

def clear_index_data(client, dry_run: bool = False) -> dict:
    """Clear all existing index data."""
    print_step(2, "Clearing existing index data")

    stats = {"constituents": 0, "values": 0}

    # Count existing data
    const_response = client.from_("constituents_monthly") \
        .select("*", count="exact") \
        .limit(1) \
        .execute()
    stats["constituents"] = const_response.count or 0

    values_response = client.from_("index_values_daily") \
        .select("*", count="exact") \
        .limit(1) \
        .execute()
    stats["values"] = values_response.count or 0

    print(f"   Found {stats['constituents']} constituent records")
    print(f"   Found {stats['values']} index value records")

    if dry_run:
        print("   [DRY RUN] Would delete all records")
        return stats

    # Delete constituents
    if stats["constituents"] > 0:
        client.from_("constituents_monthly").delete().neq("month", "1900-01-01").execute()
        print_success(f"Deleted {stats['constituents']} constituent records")

    # Delete index values
    if stats["values"] > 0:
        client.from_("index_values_daily").delete().neq("value_date", "1900-01-01").execute()
        print_success(f"Deleted {stats['values']} index value records")

    return stats


# =============================================================================
# REINITIALIZE
# =============================================================================

def run_initialize_index(dry_run: bool = False):
    """Run initialize_index.py."""
    print_step(3, "Running initialize_index.py")

    if dry_run:
        print("   [DRY RUN] Would run: python scripts_oneshot/initialize_index.py")
        return True

    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts_oneshot/initialize_index.py"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=False
    )

    return result.returncode == 0


def run_calculate_history(dry_run: bool = False):
    """Run calculate_index_history.py."""
    print_step(4, "Running calculate_index_history.py")

    if dry_run:
        print("   [DRY RUN] Would run: python scripts_oneshot/calculate_index_history.py")
        return True

    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts_oneshot/calculate_index_history.py"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=False
    )

    return result.returncode == 0


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Reinitialize Pokemon Market Indexes")
    parser.add_argument("--skip-verify", action="store_true", help="Skip data verification")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    args = parser.parse_args()

    print_header("Pokemon Market Indexes - Full Reinitialization")
    print(f"Inception date: {INCEPTION_DATE}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Connect
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return 1

    # Verify data
    if not args.skip_verify:
        if not verify_data_availability(client):
            print()
            print_error("Reinitialization aborted due to data issues.")
            print("Run with --skip-verify to force (not recommended)")
            return 1
    else:
        print_step(1, "Skipping data verification (--skip-verify)")

    # Clear existing data
    clear_index_data(client, dry_run=args.dry_run)

    # Initialize
    print()
    if not run_initialize_index(dry_run=args.dry_run):
        print_error("initialize_index.py failed!")
        return 1

    # Calculate history
    print()
    if not run_calculate_history(dry_run=args.dry_run):
        print_error("calculate_index_history.py failed!")
        return 1

    # Summary
    print()
    print_header("REINITIALIZATION COMPLETE")

    if not args.dry_run:
        # Show final stats
        for index_code in ["RARE_100", "RARE_500", "RARE_ALL"]:
            response = client.from_("index_values_daily") \
                .select("value_date, index_value") \
                .eq("index_code", index_code) \
                .order("value_date", desc=True) \
                .limit(1) \
                .execute()

            if response.data:
                latest = response.data[0]
                print(f"   {index_code}: {latest['index_value']:.2f} (as of {latest['value_date']})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
