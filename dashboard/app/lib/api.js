import { supabase, isSupabaseConfigured } from './supabase'

// ============================================================================
// HELPER: Pagination Supabase (limite 1000 par requête)
// ============================================================================

async function fetchAllPaginated(table, select, filters = {}, orderBy = null) {
  if (!isSupabaseConfigured()) return null
  
  const PAGE_SIZE = 1000
  let allData = []
  let offset = 0
  
  while (true) {
    let query = supabase.from(table).select(select).range(offset, offset + PAGE_SIZE - 1)
    
    // Apply filters
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        query = query.eq(key, value)
      }
    }
    
    // Apply order
    if (orderBy) {
      query = query.order(orderBy.column, { ascending: orderBy.ascending ?? true })
    }
    
    const { data, error } = await query
    
    if (error) {
      console.error(`Error fetching ${table}:`, error)
      return allData.length > 0 ? allData : null
    }
    
    if (!data || data.length === 0) break
    
    allData = allData.concat(data)
    
    if (data.length < PAGE_SIZE) break
    
    offset += PAGE_SIZE
  }
  
  return allData
}

// ============================================================================
// INDEX VALUES
// ============================================================================

/**
 * Récupère l'historique des valeurs d'un index
 */
export async function getIndexHistory(indexCode, days = 90) {
  if (!isSupabaseConfigured()) return null
  
  const { data, error } = await supabase
    .from('index_values_daily')
    .select('value_date, index_value, change_1d, change_1w, change_1m, n_constituents, total_market_cap')
    .eq('index_code', indexCode)
    .order('value_date', { ascending: true })
    .limit(days)
  
  if (error) {
    console.error('Error fetching index history:', error)
    return null
  }
  
  return data
}

/**
 * Récupère les dernières valeurs de tous les index
 */
export async function getLatestIndexValues() {
  if (!isSupabaseConfigured()) return null
  
  // Get latest date first
  const { data: latestDate, error: dateError } = await supabase
    .from('index_values_daily')
    .select('value_date')
    .order('value_date', { ascending: false })
    .limit(1)
    .single()
  
  if (dateError || !latestDate) {
    console.error('Error fetching latest date:', dateError)
    return null
  }
  
  // Get all indexes for that date
  const { data, error } = await supabase
    .from('index_values_daily')
    .select('*')
    .eq('value_date', latestDate.value_date)
    .in('index_code', ['RARE_100', 'RARE_500', 'RARE_ALL'])
  
  if (error) {
    console.error('Error fetching latest index values:', error)
    return null
  }
  
  // Convert to map
  const latestByIndex = {}
  data.forEach(row => {
    latestByIndex[row.index_code] = row
  })
  
  return latestByIndex
}

/**
 * Récupère l'historique de tous les index pour le graphique
 */
export async function getAllIndexHistory(days = 90) {
  if (!isSupabaseConfigured()) return null
  
  const data = await fetchAllPaginated(
    'index_values_daily',
    'index_code, value_date, index_value',
    {},
    { column: 'value_date', ascending: true }
  )
  
  if (!data) return null
  
  // Filter by index codes
  const filtered = data.filter(row => ['RARE_100', 'RARE_500', 'RARE_ALL'].includes(row.index_code))
  
  // Group by index_code
  const byIndex = {
    RARE_100: [],
    RARE_500: [],
    RARE_ALL: []
  }
  
  filtered.forEach(row => {
    if (byIndex[row.index_code]) {
      byIndex[row.index_code].push({
        date: row.value_date,
        value: parseFloat(row.index_value),
        displayDate: new Date(row.value_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      })
    }
  })
  
  return byIndex
}

// ============================================================================
// CONSTITUENTS
// ============================================================================

/**
 * Récupère les constituants actuels d'un index avec les infos des cartes
 */
export async function getConstituents(indexCode) {
  if (!isSupabaseConfigured()) return null
  
  // D'abord, trouver le mois le plus récent pour cet index
  const { data: latestMonth, error: monthError } = await supabase
    .from('constituents_monthly')
    .select('month')
    .eq('index_code', indexCode)
    .order('month', { ascending: false })
    .limit(1)
    .single()
  
  if (monthError || !latestMonth) {
    console.error('Error fetching latest month:', monthError)
    return null
  }
  
  // Récupérer les constituants de ce mois (avec pagination)
  const constituents = await fetchAllPaginated(
    'constituents_monthly',
    'item_id, rank, weight, composite_price, liquidity_score, ranking_score, is_new',
    { index_code: indexCode, month: latestMonth.month },
    { column: 'rank', ascending: true }
  )
  
  if (!constituents || constituents.length === 0) {
    console.error('No constituents found')
    return null
  }
  
  // Récupérer les infos des cartes (avec pagination par batch)
  const cardIds = constituents.map(c => c.item_id)
  const cards = await fetchCardsByIds(cardIds)
  
  // Récupérer les prix actuels
  const prices = await fetchLatestPricesByCardIds(cardIds)
  
  // Créer les maps
  const cardsMap = {}
  if (cards) {
    cards.forEach(c => { cardsMap[c.card_id] = c })
  }
  
  const pricesMap = {}
  if (prices) {
    prices.forEach(p => { 
      if (!pricesMap[p.card_id]) {
        pricesMap[p.card_id] = p 
      }
    })
  }
  
  // Merger les données
  const result = constituents.map(c => {
    const card = cardsMap[c.item_id] || {}
    const price = pricesMap[c.item_id] || {}
    
    return {
      id: c.item_id,
      name: card.name || c.item_id,
      set: card.set_id || 'Unknown',
      number: card.card_number || '',
      rarity: card.rarity || 'Rare',
      price: parseFloat(price.market_price || c.composite_price || 0),
      weight: parseFloat(c.weight || 0),
      rank: c.rank,
      liquidityScore: parseFloat(c.liquidity_score || 0),
      rankingScore: parseFloat(c.ranking_score || 0),
      isNew: c.is_new,
      tcgplayerId: card.tcgplayer_id,
      pptId: card.ppt_id,
      sales: price.daily_volume || 0,
      change: 0
    }
  })
  
  return result
}

// Helper: Fetch cards by IDs in batches
async function fetchCardsByIds(cardIds) {
  if (!isSupabaseConfigured() || !cardIds || cardIds.length === 0) return null
  
  const BATCH_SIZE = 100
  let allCards = []
  
  for (let i = 0; i < cardIds.length; i += BATCH_SIZE) {
    const batchIds = cardIds.slice(i, i + BATCH_SIZE)
    
    const { data, error } = await supabase
      .from('cards')
      .select('card_id, name, set_id, card_number, rarity, tcgplayer_id, ppt_id')
      .in('card_id', batchIds)
    
    if (error) {
      console.error('Error fetching cards batch:', error)
      continue
    }
    
    if (data) {
      allCards = allCards.concat(data)
    }
  }
  
  return allCards
}

// Helper: Fetch latest prices by card IDs
async function fetchLatestPricesByCardIds(cardIds) {
  if (!isSupabaseConfigured() || !cardIds || cardIds.length === 0) return null
  
  // Get latest price date
  const { data: latestDate, error: dateError } = await supabase
    .from('card_prices_daily')
    .select('price_date')
    .order('price_date', { ascending: false })
    .limit(1)
    .single()
  
  if (dateError || !latestDate) return null
  
  const BATCH_SIZE = 100
  let allPrices = []
  
  for (let i = 0; i < cardIds.length; i += BATCH_SIZE) {
    const batchIds = cardIds.slice(i, i + BATCH_SIZE)
    
    const { data, error } = await supabase
      .from('card_prices_daily')
      .select('card_id, price_date, market_price, nm_price, daily_volume')
      .eq('price_date', latestDate.price_date)
      .in('card_id', batchIds)
    
    if (error) {
      console.error('Error fetching prices batch:', error)
      continue
    }
    
    if (data) {
      allPrices = allPrices.concat(data)
    }
  }
  
  return allPrices
}

// ============================================================================
// ALL CARDS
// ============================================================================

/**
 * Récupère toutes les cartes éligibles avec leurs prix et index membership
 */
export async function getAllEligibleCards() {
  if (!isSupabaseConfigured()) return null
  
  // Récupérer les cartes éligibles (avec pagination)
  const cards = await fetchAllPaginated(
    'cards',
    'card_id, name, set_id, card_number, rarity, tcgplayer_id, ppt_id',
    { is_eligible: true },
    { column: 'name', ascending: true }
  )
  
  if (!cards || cards.length === 0) {
    console.error('No eligible cards found')
    return null
  }
  
  // Récupérer les constituants actuels pour savoir dans quels index chaque carte est
  const allConstituents = await fetchAllPaginated(
    'constituents_monthly',
    'item_id, index_code, month',
    {},
    { column: 'month', ascending: false }
  )
  
  // Trouver le mois le plus récent
  const latestMonth = allConstituents?.[0]?.month
  const currentConstituents = allConstituents?.filter(c => c.month === latestMonth) || []
  
  // Créer un map des index par carte
  const cardIndexes = {}
  currentConstituents.forEach(c => {
    if (!cardIndexes[c.item_id]) {
      cardIndexes[c.item_id] = { inRare100: false, inRare500: false, inRareAll: false }
    }
    if (c.index_code === 'RARE_100') cardIndexes[c.item_id].inRare100 = true
    if (c.index_code === 'RARE_500') cardIndexes[c.item_id].inRare500 = true
    if (c.index_code === 'RARE_ALL') cardIndexes[c.item_id].inRareAll = true
  })
  
  // Récupérer les derniers prix
  const cardIds = cards.map(c => c.card_id)
  const prices = await fetchLatestPricesByCardIds(cardIds)
  
  const pricesMap = {}
  if (prices) {
    prices.forEach(p => {
      if (!pricesMap[p.card_id]) {
        pricesMap[p.card_id] = p
      }
    })
  }
  
  // Merger
  const result = cards.map(card => {
    const price = pricesMap[card.card_id] || {}
    const indexes = cardIndexes[card.card_id] || { inRare100: false, inRare500: false, inRareAll: false }
    
    return {
      id: card.card_id,
      name: card.name || card.card_id,
      set: card.set_id || 'Unknown',
      number: card.card_number || '',
      rarity: card.rarity || 'Rare',
      price: parseFloat(price.market_price || price.nm_price || 0),
      tcgplayerId: card.tcgplayer_id,
      pptId: card.ppt_id,
      change: 0,
      ...indexes
    }
  })
  
  return result
}

// ============================================================================
// CARD DETAILS
// ============================================================================

/**
 * Récupère l'historique des prix d'une carte
 */
export async function getCardPriceHistory(cardId, days = 180) {
  if (!isSupabaseConfigured()) return null
  
  const { data, error } = await supabase
    .from('card_prices_daily')
    .select('price_date, market_price, nm_price, daily_volume')
    .eq('card_id', cardId)
    .order('price_date', { ascending: true })
    .limit(days)
  
  if (error) {
    console.error('Error fetching card price history:', error)
    return null
  }
  
  return data.map(row => ({
    date: row.price_date,
    price: parseFloat(row.market_price || row.nm_price || 0),
    displayDate: new Date(row.price_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }))
}

/**
 * Récupère les détails d'une carte
 */
export async function getCardDetails(cardId) {
  if (!isSupabaseConfigured()) return null
  
  const { data, error } = await supabase
    .from('cards')
    .select('*')
    .eq('card_id', cardId)
    .single()
  
  if (error) {
    console.error('Error fetching card details:', error)
    return null
  }
  
  return data
}
