"""
Pokemon Market Indexes v2 - Health Check
========================================
Verifies that the system is functioning correctly.

Checks:
1. Database connectivity
2. Data freshness (latest prices, index values)
3. Data consistency (constituent counts, weights)
4. API connectivity (PPT API credits)

Usage:
    python scripts/healthcheck.py
    python scripts/healthcheck.py --verbose
"""

import sys
import os
import argparse
from datetime import date, datetime, timedelta

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, ppt_request,
    print_header, print_step, print_success, print_error, print_warning,
    send_discord_notification
)
from config.settings import INDEX_CONFIG, INCEPTION_DATE


# =============================================================================
# HEALTH CHECKS
# =============================================================================

def check_database_connection(client) -> tuple[bool, str]:
    """Check if database is accessible."""
    try:
        response = client.from_("sets").select("set_id").limit(1).execute()
        if response.data is not None:
            return True, "Database connection OK"
        return False, "Database returned no data"
    except Exception as e:
        return False, f"Database connection failed: {e}"


def check_latest_prices(client, max_age_days: int = 3) -> tuple[bool, str, dict]:
    """Check if price data is recent."""
    try:
        response = client.from_("card_prices_daily") \
            .select("price_date") \
            .order("price_date", desc=True) \
            .limit(1) \
            .execute()

        if not response.data:
            return False, "No price data found", {}

        latest_date = datetime.strptime(response.data[0]["price_date"], "%Y-%m-%d").date()
        age_days = (date.today() - latest_date).days

        details = {
            "latest_price_date": str(latest_date),
            "age_days": age_days,
        }

        # Account for J-2 strategy: prices are always 2 days behind
        effective_age = age_days - 2

        if effective_age <= max_age_days:
            return True, f"Latest prices: {latest_date} ({age_days}d ago, J-2 OK)", details
        else:
            return False, f"Prices are stale: {latest_date} ({age_days}d ago)", details

    except Exception as e:
        return False, f"Price check failed: {e}", {}


def check_latest_index(client, max_age_days: int = 3) -> tuple[bool, str, dict]:
    """Check if index values are recent."""
    try:
        response = client.from_("index_values_daily") \
            .select("value_date, index_code, index_value") \
            .order("value_date", desc=True) \
            .limit(3) \
            .execute()

        if not response.data:
            return False, "No index values found", {}

        latest_date = datetime.strptime(response.data[0]["value_date"], "%Y-%m-%d").date()
        age_days = (date.today() - latest_date).days

        # Get values for each index
        index_values = {}
        for row in response.data:
            if row["value_date"] == str(latest_date):
                index_values[row["index_code"]] = row["index_value"]

        details = {
            "latest_index_date": str(latest_date),
            "age_days": age_days,
            "values": index_values,
        }

        # Account for J-2 strategy
        effective_age = age_days - 2

        if effective_age <= max_age_days:
            values_str = ", ".join(f"{k}: {v:.2f}" for k, v in index_values.items())
            return True, f"Latest index: {latest_date} ({values_str})", details
        else:
            return False, f"Index is stale: {latest_date} ({age_days}d ago)", details

    except Exception as e:
        return False, f"Index check failed: {e}", {}


def check_constituents(client) -> tuple[bool, str, dict]:
    """Check constituent data integrity."""
    try:
        current_month = date.today().replace(day=1).strftime("%Y-%m-%d")

        details = {"month": current_month, "indexes": {}}
        all_ok = True
        issues = []

        for index_code in ["RARE_100", "RARE_500", "RARE_ALL"]:
            response = client.from_("constituents_monthly") \
                .select("item_id, weight") \
                .eq("index_code", index_code) \
                .eq("month", current_month) \
                .execute()

            count = len(response.data) if response.data else 0
            expected = INDEX_CONFIG.get(index_code, {}).get("size")

            # Calculate weight sum
            weight_sum = sum(float(r["weight"]) for r in response.data) if response.data else 0

            details["indexes"][index_code] = {
                "count": count,
                "expected": expected,
                "weight_sum": round(weight_sum, 4),
            }

            # Check count
            if expected and count != expected:
                issues.append(f"{index_code}: {count}/{expected} constituents")
                all_ok = False
            elif count == 0:
                issues.append(f"{index_code}: no constituents")
                all_ok = False

            # Check weights sum to ~1.0 (allowing small rounding error)
            if count > 0 and abs(weight_sum - 1.0) > 0.001:
                issues.append(f"{index_code}: weights sum to {weight_sum:.4f}")
                all_ok = False

        if all_ok:
            counts = ", ".join(f"{k}: {v['count']}" for k, v in details["indexes"].items())
            return True, f"Constituents OK ({counts})", details
        else:
            return False, f"Constituent issues: {'; '.join(issues)}", details

    except Exception as e:
        return False, f"Constituent check failed: {e}", {}


def check_api_credits(verbose: bool = False) -> tuple[bool, str, dict]:
    """Check PPT API credits remaining."""
    try:
        response = ppt_request("/v2/account/credits")
        credits = response.get("remaining", 0)
        total = response.get("total", 200000)
        usage_pct = (1 - credits / total) * 100 if total > 0 else 0

        details = {
            "remaining": credits,
            "total": total,
            "usage_pct": round(usage_pct, 1),
        }

        if credits > 10000:
            return True, f"API credits OK: {credits:,} remaining ({usage_pct:.1f}% used)", details
        elif credits > 1000:
            return True, f"API credits LOW: {credits:,} remaining", details
        else:
            return False, f"API credits CRITICAL: {credits:,} remaining", details

    except Exception as e:
        return False, f"API check failed: {e}", {}


def check_data_gaps(client, days_to_check: int = 7) -> tuple[bool, str, dict]:
    """Check for missing data in recent days."""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days_to_check)

        response = client.from_("card_prices_daily") \
            .select("price_date") \
            .gte("price_date", start_date.strftime("%Y-%m-%d")) \
            .lte("price_date", end_date.strftime("%Y-%m-%d")) \
            .execute()

        # Get unique dates
        dates_with_data = set(r["price_date"] for r in response.data) if response.data else set()

        # Expected dates (excluding weekends? No, we fetch daily)
        expected_dates = set()
        current = start_date
        while current <= end_date:
            expected_dates.add(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        # Find gaps (accounting for J-2: today and yesterday won't have data yet)
        j2_cutoff = (end_date - timedelta(days=2)).strftime("%Y-%m-%d")
        expected_with_j2 = {d for d in expected_dates if d <= j2_cutoff}
        missing = expected_with_j2 - dates_with_data

        details = {
            "days_checked": days_to_check,
            "dates_with_data": len(dates_with_data),
            "missing_dates": sorted(list(missing)),
        }

        if not missing:
            return True, f"No data gaps in last {days_to_check} days", details
        else:
            return False, f"Data gaps found: {', '.join(sorted(missing))}", details

    except Exception as e:
        return False, f"Gap check failed: {e}", {}


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Health check for Pokemon Market Indexes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--notify", action="store_true", help="Send Discord notification on failure")
    args = parser.parse_args()

    print_header("Pokemon Market Indexes - Health Check")
    print(f"Date: {date.today()}")
    print()

    # Connect to database
    print_step(1, "Database Connection")
    try:
        client = get_db_client()
        print_success("Connected to Supabase")
    except Exception as e:
        print_error(f"Cannot connect: {e}")
        if args.notify:
            send_discord_notification(
                "Health Check - CRITICAL",
                f"Database connection failed: {e}",
                success=False
            )
        sys.exit(1)

    # Run checks
    checks = [
        ("Database", lambda: check_database_connection(client)),
        ("Latest Prices", lambda: check_latest_prices(client)),
        ("Latest Index", lambda: check_latest_index(client)),
        ("Constituents", lambda: check_constituents(client)),
        ("API Credits", lambda: check_api_credits(args.verbose)),
        ("Data Gaps", lambda: check_data_gaps(client)),
    ]

    results = []
    all_ok = True

    print_step(2, "Running Checks")
    for name, check_fn in checks:
        result = check_fn()
        ok = result[0]
        message = result[1]
        details = result[2] if len(result) > 2 else {}

        results.append({"name": name, "ok": ok, "message": message, "details": details})

        if ok:
            print_success(f"{name}: {message}")
        else:
            print_error(f"{name}: {message}")
            all_ok = False

        if args.verbose and details:
            for k, v in details.items():
                print(f"      {k}: {v}")

    # Summary
    print()
    print("=" * 60)
    passed = sum(1 for r in results if r["ok"])
    failed = len(results) - passed

    if all_ok:
        print_success(f"All {passed} checks passed!")
    else:
        print_error(f"{failed}/{len(results)} checks failed")
        if args.notify:
            failures = [r for r in results if not r["ok"]]
            failure_msgs = "\n".join(f"- {r['name']}: {r['message']}" for r in failures)
            send_discord_notification(
                "Health Check - FAILED",
                f"{failed} check(s) failed:\n{failure_msgs}",
                success=False
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
