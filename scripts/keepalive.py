"""
Pokemon Market Indexes v2 - Keepalive
=====================================
Simple script to ping the database and prevent Supabase free tier pause.
(Free tier pauses after 1 week of inactivity)

Usage:
    python scripts/keepalive.py
"""

import sys
import os

# Local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import get_db_client


def main():
    """Ping the database with a simple query to keep it active."""
    try:
        client = get_db_client()

        # Simple query to verify database is accessible
        result = client.from_("sets").select("set_id").limit(1).execute()

        if not result.data:
            print("⚠️ Warning: No data returned - database may be empty")
            return 1

        print(f"✅ Keepalive OK - Database is active ({len(result.data)} row returned)")
        return 0

    except Exception as e:
        print(f"❌ Keepalive failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
