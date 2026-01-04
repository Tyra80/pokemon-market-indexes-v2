"""
Pokemon Market Indexes v2 - Fetch Cards
=======================================
Récupère le référentiel des cartes depuis PokemonPriceTracker.

Basé sur la documentation API officielle:
- /sets : récupère la liste des sets (limit=500)
- /cards?set={name}&fetchAllInSet=true : récupère toutes les cartes d'un set

Usage:
    python scripts/fetch_cards.py
"""

import sys
import os
import time
import requests
from datetime import datetime

# Imports locaux
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.utils import (
    get_db_client, batch_upsert, 
    log_run_start, log_run_end, send_discord_notification, get_today,
    print_header, print_step, print_success, print_error
)
from config.settings import PPT_API_KEY, PPT_RATE_LIMIT

# Base URL de l'API (v2)
BASE_URL = "https://www.pokemonpricetracker.com/api/v2"

# Headers d'authentification (comme dans la doc)
HEADERS = {
    "Authorization": f"Bearer {PPT_API_KEY}",
}


def api_request(endpoint: str, params: dict = None, max_retries: int = 3) -> dict:
    """
    Effectue une requête à l'API PokemonPriceTracker avec retry automatique.
    """
    url = f"{BASE_URL}{endpoint}"
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=60)
            
            # Si rate limit, attendre et réessayer
            if response.status_code == 429:
                wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s
                print(f"   ⏳ Rate limit atteint, pause {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                continue
            raise
    
    return None


def fetch_all_sets() -> list:
    """
    Récupère tous les sets depuis /sets.
    Utilise limit=500 (max autorisé par l'API).
    """
    print("   Récupération des sets...")
    
    all_sets = []
    offset = 0
    limit = 500  # Max autorisé par l'API
    
    while True:
        try:
            data = api_request("/sets", {
                "limit": limit,
                "offset": offset,
                "sortBy": "releaseDate",
                "sortOrder": "desc"
            })
            
            # Si la requête a échoué
            if data is None:
                print(f"   ⚠️ Requête échouée à offset {offset}, on continue...")
                break
            
            sets = data.get("data", [])
            metadata = data.get("metadata", {})
            
            if not sets:
                break
            
            # Filtre les None
            valid_sets = [s for s in sets if s and isinstance(s, dict) and s.get("name")]
            all_sets.extend(valid_sets)
            
            print(f"   ... {len(all_sets)} sets chargés")
            
            # Vérifie s'il y a plus de données
            if not metadata.get("hasMore", False):
                break
            
            if len(sets) < limit:
                break
            
            offset += limit
            time.sleep(PPT_RATE_LIMIT["delay_between_requests"])
            
        except Exception as e:
            print(f"   ⚠️ Erreur: {e}")
            break
    
    return all_sets


def fetch_cards_for_set(set_name: str) -> list:
    """
    Récupère toutes les cartes d'un set via /cards?set={name}&fetchAllInSet=true.
    """
    try:
        data = api_request("/cards", {
            "set": set_name,
            "fetchAllInSet": "true",
        })
        
        # Si la requête a échoué (retourne None après retries)
        if data is None:
            return []
        
        cards = data.get("data", [])
        
        # Si data est un dict (une seule carte), le mettre dans une liste
        if isinstance(cards, dict):
            cards = [cards]
        
        # Filtre les None
        valid_cards = [c for c in cards if c and isinstance(c, dict)]
        
        return valid_cards
        
    except Exception as e:
        print(f"   ⚠️ Erreur: {e}")
        return []


def transform_set_to_db(set_data: dict) -> dict:
    """Transforme un set API en format DB."""
    if not set_data:
        return None
    
    # Utilise l'ID de l'API ou crée un slug du nom
    set_id = set_data.get("id") or set_data.get("tcgPlayerId")
    if not set_id:
        set_id = set_data.get("name", "unknown").lower().replace(" ", "-").replace(":", "")[:50]
    
    release_date = set_data.get("releaseDate")
    if release_date:
        release_date = release_date.replace("/", "-")[:10]  # Garde seulement YYYY-MM-DD
    
    return {
        "set_id": str(set_id),
        "name": set_data.get("name"),
        "series": set_data.get("series"),
        "release_date": release_date if release_date else None,
        "total_cards": set_data.get("cardCount"),
    }


def transform_card_to_db(card_data: dict) -> dict:
    """Transforme une carte API en format DB."""
    if not card_data:
        return None
    
    # ID unique: priorité à l'ID interne, puis tcgPlayerId
    ppt_id = card_data.get("id")
    tcgplayer_id = card_data.get("tcgPlayerId")
    
    if ppt_id:
        card_id = str(ppt_id)
    elif tcgplayer_id:
        card_id = f"tcg-{tcgplayer_id}"
    else:
        card_id = f"{card_data.get('setName', 'unknown')}-{card_data.get('cardNumber', 'unknown')}"
    
    # set_id: utilise setId de l'API ou crée un slug
    set_id = card_data.get("setId")
    if not set_id:
        set_name = card_data.get("setName", "unknown")
        set_id = set_name.lower().replace(" ", "-").replace(":", "")[:50]
    
    return {
        "card_id": card_id,
        "ppt_id": ppt_id,
        "tcgplayer_id": str(tcgplayer_id) if tcgplayer_id else None,
        "name": card_data.get("name"),
        "set_id": str(set_id),
        "card_number": card_data.get("cardNumber"),
        "rarity": card_data.get("rarity"),
        "variant": "normal",
        "card_type": card_data.get("cardType"),
        "hp": card_data.get("hp"),
        "artist": card_data.get("artist"),
        "is_eligible": True,
    }


def main():
    print_header("🃏 Pokemon Market Indexes - Fetch Cards (v6)")
    print(f"📅 Date : {get_today()}")
    print()
    print("⚠️  Ce script peut prendre 15-30 minutes.")
    print("   Tu peux l'interrompre avec Ctrl+C.")
    
    # Connexion
    print_step(1, "Connexion à Supabase")
    try:
        client = get_db_client()
        print_success("Connecté à Supabase")
    except Exception as e:
        print_error(f"Connexion échouée : {e}")
        return
    
    # Log du run
    run_id = log_run_start(client, "fetch_cards")
    
    total_sets = 0
    total_cards = 0
    
    try:
        # Récupère les sets
        print_step(2, "Récupération des sets")
        sets = fetch_all_sets()
        print_success(f"{len(sets)} sets trouvés")
        
        if len(sets) == 0:
            print_error("Aucun set trouvé ! Vérifie l'API key.")
            return
        
        # Sauvegarde les sets
        print_step(3, "Sauvegarde des sets")
        sets_db = [transform_set_to_db(s) for s in sets]
        sets_db = [s for s in sets_db if s is not None]
        
        result = batch_upsert(client, "sets", sets_db, on_conflict="set_id")
        print_success(f"{result['saved']} sets sauvegardés")
        total_sets = result['saved']
        
        # Récupère les cartes par set
        print_step(4, "Récupération des cartes")
        
        all_cards_db = []
        sets_with_cards = 0
        sets_without_cards = 0
        
        for i, set_data in enumerate(sets, 1):
            set_name = set_data.get("name")
            
            if not set_name:
                continue
            
            print(f"\n   [{i}/{len(sets)}] 📦 {set_name}")
            
            cards = fetch_cards_for_set(set_name)
            
            if cards:
                cards_db = [transform_card_to_db(c) for c in cards]
                cards_db = [c for c in cards_db if c is not None]
                all_cards_db.extend(cards_db)
                print(f"   ✅ {len(cards)} cartes")
                sets_with_cards += 1
            else:
                print(f"   ⚠️ Aucune carte")
                sets_without_cards += 1
            
            # Sauvegarde par batch de 2000 cartes
            if len(all_cards_db) >= 2000:
                result = batch_upsert(client, "cards", all_cards_db, on_conflict="card_id")
                print(f"\n   💾 Batch sauvegardé : {result['saved']} cartes")
                total_cards += result['saved']
                all_cards_db = []
            
            # Pause pour respecter rate limit (200 calls/min = 0.3s minimum)
            time.sleep(0.35)
        
        # Sauvegarde le dernier batch
        if all_cards_db:
            result = batch_upsert(client, "cards", all_cards_db, on_conflict="card_id")
            print(f"\n   💾 Dernier batch : {result['saved']} cartes")
            total_cards += result['saved']
        
        # Vérification
        print_step(5, "Vérification")
        
        response = client.from_("sets").select("*", count="exact").execute()
        print(f"   Sets en base : {response.count}")
        
        response = client.from_("cards").select("*", count="exact").execute()
        print(f"   Cartes en base : {response.count}")
        
        # Log succès
        log_run_end(client, run_id, "success", 
                    records_processed=total_cards,
                    details={
                        "sets": total_sets, 
                        "cards": total_cards,
                        "sets_with_cards": sets_with_cards,
                        "sets_without_cards": sets_without_cards
                    })
        
        # Notification Discord
        send_discord_notification(
            "✅ Fetch Cards - Succès",
            f"{total_sets} sets, {total_cards} cartes chargées."
        )
        
        print()
        print_header("📊 RÉSUMÉ")
        print(f"   Sets traités      : {total_sets}")
        print(f"   Sets avec cartes  : {sets_with_cards}")
        print(f"   Sets sans cartes  : {sets_without_cards}")
        print(f"   Cartes totales    : {total_cards}")
        print()
        print_success("Script terminé avec succès !")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interruption détectée (Ctrl+C)")
        print("   Les données déjà sauvegardées sont conservées.")
        log_run_end(client, run_id, "interrupted", records_processed=total_cards)
        
    except Exception as e:
        print_error(f"Erreur : {e}")
        log_run_end(client, run_id, "failed", error_message=str(e))
        send_discord_notification(
            "❌ Fetch Cards - Échec",
            f"Erreur : {str(e)[:200]}",
            success=False
        )
        raise


if __name__ == "__main__":
    main()