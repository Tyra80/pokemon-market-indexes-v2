"""
Pokemon Market Indexes v2 - Utilities
=====================================
Fonctions utilitaires partagées par tous les scripts.
"""

import os
import sys
import requests
from datetime import datetime, date, timedelta
from postgrest import SyncPostgrestClient

# Ajoute le dossier parent au path pour les imports
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
    Crée et retourne un client Supabase.
    
    Returns:
        SyncPostgrestClient: Client connecté à Supabase
    
    Raises:
        ValueError: Si les credentials sont manquants
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL ou SUPABASE_KEY manquant dans .env")
    
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
    Effectue une requête à l'API PokemonPriceTracker.
    
    Args:
        endpoint: Endpoint API (ex: "/v2/cards")
        params: Paramètres de requête
    
    Returns:
        dict: Réponse JSON
    
    Raises:
        requests.HTTPError: Si la requête échoue
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
    Récupère toutes les lignes d'une table avec pagination.
    
    Args:
        client: Client Supabase
        table: Nom de la table
        select: Colonnes à sélectionner
        filters: Filtres à appliquer {"column": "value"}
        page_size: Taille des pages
    
    Returns:
        list: Toutes les lignes
    """
    all_rows = []
    offset = 0
    
    while True:
        query = client.from_(table).select(select).range(offset, offset + page_size - 1)
        
        # Applique les filtres
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
    Insère des lignes en batch avec upsert.

    Args:
        client: Client Supabase
        table: Nom de la table
        rows: Lignes à insérer
        batch_size: Taille des batches
        on_conflict: Colonnes pour l'upsert

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
    Enregistre le début d'une exécution.

    Returns:
        int: ID du run, or None if logging failed
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
    Enregistre la fin d'une exécution.
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
            update_data["error_message"] = error_message[:500]  # Truncate long errors
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
    Envoie une notification Discord.

    Args:
        title: Titre du message
        description: Description
        color: Couleur (vert par défaut)
        success: True=vert, False=rouge
    """
    if not DISCORD_WEBHOOK_URL:
        return

    if not success:
        color = 15548997  # Rouge

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
    """Retourne la date du jour au format YYYY-MM-DD."""
    return date.today().strftime("%Y-%m-%d")


def get_current_month() -> str:
    """Retourne le premier jour du mois courant au format YYYY-MM-DD."""
    return date.today().replace(day=1).strftime("%Y-%m-%d")


def get_last_sunday() -> str:
    """Retourne la date du dernier dimanche au format YYYY-MM-DD."""
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    return last_sunday.strftime("%Y-%m-%d")


# ============================================================
# Print Helpers
# ============================================================

def print_header(title: str):
    """Affiche un header formaté."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step: int, title: str):
    """Affiche une étape."""
    print()
    print(f"📌 Étape {step} : {title}")
    print("-" * 60)


def print_success(message: str):
    """Affiche un message de succès."""
    print(f"✅ {message}")


def print_error(message: str):
    """Affiche un message d'erreur."""
    print(f"❌ {message}")


def print_warning(message: str):
    """Affiche un avertissement."""
    print(f"⚠️  {message}")


def print_progress(current: int, total: int, prefix: str = ""):
    """Affiche la progression."""
    pct = current * 100 // total if total > 0 else 0
    print(f"   ⏳ {prefix}{current}/{total} ({pct}%)")
