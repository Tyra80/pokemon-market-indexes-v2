# 🚀 Guide de Setup Complet - Pokemon Market Indexes v2

Ce guide te permet de configurer tout le projet **from scratch**.

---

## 📋 Prérequis

Avant de commencer, assure-toi d'avoir :

- ✅ **Python 3.11+** installé ([Télécharger](https://www.python.org/downloads/))
- ✅ **VS Code** installé ([Télécharger](https://code.visualstudio.com/))
- ✅ **Git** installé ([Télécharger](https://git-scm.com/downloads))
- ✅ Un compte **GitHub** ([Créer](https://github.com/signup))
- ✅ Un compte **Supabase** ([Créer](https://supabase.com/))
- ✅ Une clé API **PokemonPriceTracker** Business

---

## 🧹 Étape 0 : Nettoyage (si tu avais une version précédente)

### Supprimer l'ancien dossier local
```powershell
# Ouvre PowerShell et exécute :
Remove-Item -Recurse -Force C:\Users\demai\Desktop\pokemon-index-project
```

### Supprimer l'ancien projet Supabase
1. Va sur [Supabase Dashboard](https://supabase.com/dashboard)
2. Clique sur ton projet
3. **Settings** (engrenage) → **General**
4. Scroll en bas → **Delete project**
5. Tape le nom du projet pour confirmer

### Supprimer l'ancien repo GitHub (optionnel)
1. Va sur ton repo GitHub
2. **Settings** → Scroll tout en bas → **Delete this repository**

---

## 📁 Étape 1 : Créer le dossier du projet

### 1.1 Crée le dossier
```powershell
# Ouvre PowerShell
cd C:\Users\demai\Desktop
mkdir pokemon-market-indexes-v2
cd pokemon-market-indexes-v2
```

### 1.2 Ouvre dans VS Code
```powershell
code .
```

---

## 🗃️ Étape 2 : Créer le projet Supabase

### 2.1 Crée un nouveau projet
1. Va sur [Supabase Dashboard](https://supabase.com/dashboard)
2. Clique **New Project**
3. Remplis :
   - **Name** : `pokemon-market-indexes-v2`
   - **Database Password** : génère un mot de passe fort (note-le !)
   - **Region** : `West EU (Ireland)` ou le plus proche de toi
4. Clique **Create new project**
5. ⏳ Attends 2-3 minutes que le projet se crée

### 2.2 Récupère les credentials
1. Une fois créé, va dans **Settings** (engrenage) → **API**
2. Note ces valeurs (tu en auras besoin) :
   - **Project URL** : `https://xxxxx.supabase.co`
   - **anon public** key : `eyJhbGciOiJI...` (longue chaîne)

### 2.3 Crée les tables
1. Dans Supabase, va dans **SQL Editor** (icône de code)
2. Clique **New query**
3. Copie-colle **TOUT** le contenu du fichier `sql/001_schema.sql`
4. Clique **Run** (ou Ctrl+Enter)
5. Tu devrais voir : `Schema v2 créé avec succès!`

**Vérification :**
- Va dans **Table Editor** (icône de table)
- Tu dois voir 9 tables : `sets`, `cards`, `sealed_products`, etc.

---

## 🐍 Étape 3 : Configurer Python

### 3.1 Crée l'environnement virtuel
Dans le terminal VS Code (Ctrl+`) :
```powershell
python -m venv venv
```

### 3.2 Active l'environnement
```powershell
.\venv\Scripts\Activate
```
Tu dois voir `(venv)` au début de la ligne.

### 3.3 Installe les dépendances
```powershell
pip install -r requirements.txt
```

---

## ⚙️ Étape 4 : Configurer les variables d'environnement

### 4.1 Crée le fichier .env
Dans VS Code, crée un fichier `.env` à la racine du projet :

```env
# Supabase
SUPABASE_URL=https://ton-projet.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# PokemonPriceTracker API
PPT_API_KEY=pokeprice_business_ta_cle_api

# Discord (optionnel - pour les notifications)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
```

**⚠️ IMPORTANT :** Remplace les valeurs par tes vraies credentials !

### 4.2 Vérifie que .env est ignoré par Git
Le fichier `.gitignore` contient déjà `.env`, donc tes secrets ne seront jamais pushés sur GitHub.

---

## 🧪 Étape 5 : Tester la connexion

### 5.1 Teste la connexion Supabase
Crée un fichier `test_connection.py` temporaire :

```python
from scripts.utils import get_db_client

try:
    client = get_db_client()
    result = client.from_("sets").select("*").limit(1).execute()
    print("✅ Connexion Supabase OK !")
except Exception as e:
    print(f"❌ Erreur : {e}")
```

Exécute :
```powershell
python test_connection.py
```

Tu dois voir : `✅ Connexion Supabase OK !`

Supprime le fichier de test après.

---

## 📊 Étape 6 : Premier chargement des données

### 6.1 Charger les taux de change (1 minute)
```powershell
python scripts/fetch_fx_rates.py
```

**Résultat attendu :**
```
✅ 30 taux sauvegardés
📊 Derniers taux :
   2026-01-03 : 1.0312
   ...
```

### 6.2 Charger les cartes (30-60 minutes)
```powershell
python scripts/fetch_cards.py
```

**⚠️ Ce script prend du temps !** Tu peux le laisser tourner et faire autre chose.

**Résultat attendu :**
```
📦 Sets traités  : ~200
🃏 Cartes totales: ~23,000
```

### 6.3 Charger les prix (30-45 minutes)
```powershell
python scripts/fetch_prices.py
```

**Résultat attendu :**
```
💰 ~15,000 prix récupérés
```

### 6.4 Calculer les indices (2 minutes)
```powershell
python scripts/calculate_index.py
```

**Résultat attendu :**
```
📈 RARE_100 : 100.00 (100 constituants)
📈 RARE_500 : 100.00 (500 constituants)
📈 RARE_ALL : 100.00 (xxxx constituants)
```

---

## 🐙 Étape 7 : Configurer GitHub

### 7.1 Initialise Git
```powershell
git init
git add .
git commit -m "Initial commit - Pokemon Market Indexes v2"
```

### 7.2 Crée le repo GitHub
1. Va sur [GitHub](https://github.com/new)
2. **Repository name** : `pokemon-market-indexes`
3. **Private** (recommandé)
4. Ne coche PAS "Add README"
5. Clique **Create repository**

### 7.3 Connecte ton repo local
GitHub te montre les commandes. Exécute :
```powershell
git remote add origin https://github.com/TON_USERNAME/pokemon-market-indexes.git
git branch -M main
git push -u origin main
```

### 7.4 Configure les secrets GitHub
1. Sur GitHub, va dans ton repo → **Settings** → **Secrets and variables** → **Actions**
2. Clique **New repository secret** et ajoute :

| Name | Value |
|------|-------|
| `SUPABASE_URL` | `https://ton-projet.supabase.co` |
| `SUPABASE_KEY` | `eyJhbGciOiJI...` |
| `PPT_API_KEY` | `pokeprice_business_...` |
| `DISCORD_WEBHOOK_URL` | `https://discord.com/api/webhooks/...` |

---

## 🤖 Étape 8 : Activer l'automatisation

### 8.1 Vérifie que les workflows sont présents
Dans ton repo GitHub, va dans **Actions**. Tu dois voir :
- Daily FX Rates
- Daily Prices
- Weekly Index Calculation
- Weekly Cards Update
- Keepalive

### 8.2 Lance un workflow manuellement (test)
1. Clique sur **Daily FX Rates**
2. Clique **Run workflow** → **Run workflow**
3. Attends 1-2 minutes
4. ✅ Le workflow doit passer au vert

### 8.3 Planning automatique
Les workflows se lanceront automatiquement :

| Workflow | Fréquence | Heure (Paris) |
|----------|-----------|---------------|
| FX Rates | Quotidien | 17h00 |
| Prices | Quotidien | 07h00 |
| Index Calculation | Dimanche | 01h00 |
| Cards Update | Dimanche | 04h00 |
| Keepalive | Tous les 5 jours | 13h00 |

---

## 🔔 Étape 9 : Configurer Discord (optionnel)

Si tu veux recevoir des notifications :

### 9.1 Crée un webhook Discord
1. Dans Discord, va dans les paramètres de ton serveur
2. **Intégrations** → **Webhooks** → **Nouveau webhook**
3. Nomme-le "Pokemon Indexes"
4. Copie l'URL du webhook

### 9.2 Ajoute-le aux secrets GitHub
- Retourne dans GitHub → Settings → Secrets
- Ajoute `DISCORD_WEBHOOK_URL` avec l'URL copiée

---

## ✅ Étape 10 : Vérification finale

### Checklist

- [ ] Supabase : 9 tables créées
- [ ] Supabase : fx_rates_daily contient des données
- [ ] Supabase : cards contient ~23,000 lignes
- [ ] Supabase : card_prices_daily contient des données
- [ ] Supabase : index_values_weekly contient RARE_100, RARE_500, RARE_ALL
- [ ] GitHub : Repo créé et code pushé
- [ ] GitHub : 4 secrets configurés
- [ ] GitHub Actions : Workflow FX testé manuellement ✅

---

## 🎉 C'est terminé !

Ton système est maintenant opérationnel :

1. **Chaque jour** à 7h : les prix sont mis à jour
2. **Chaque jour** à 17h : le taux EUR/USD est mis à jour
3. **Chaque dimanche** : les indices sont recalculés

Tu peux consulter les données dans :
- **Supabase** → Table Editor → `index_values_weekly`
- **GitHub** → Actions (voir les logs d'exécution)
- **Discord** (si configuré) → notifications automatiques

---

## 🆘 Troubleshooting

### "Module not found"
```powershell
# Vérifie que l'environnement virtuel est activé
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### "Connection refused" / "Invalid API key"
- Vérifie tes credentials dans `.env`
- Vérifie les secrets GitHub

### "Rate limit exceeded"
- L'API PokemonPriceTracker a une limite de 200k req/jour
- Attends minuit UTC pour le reset

### Workflow GitHub échoue
1. Va dans Actions → clique sur le workflow échoué
2. Clique sur le job → regarde les logs
3. L'erreur est généralement visible dans les dernières lignes

---

## 📚 Pour aller plus loin

- [Documentation méthodologie](METHODOLOGY.md)
- [Schéma base de données](DATABASE.md)
- [API PokemonPriceTracker](https://www.pokemonpricetracker.com/docs)
