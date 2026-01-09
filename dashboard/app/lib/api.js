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
      set: card.set_name || card.set_id || 'Unknown',
      setId: card.set_id,
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
      sales: price.monthly_volume || 0,
      change: price.change_24h || 0,
      // Flag pour l'index courant
      indexCode: indexCode,
      inRare100: indexCode === 'RARE_100',
      inRare500: indexCode === 'RARE_100' || indexCode === 'RARE_500',
      inRareAll: true
    }
  })

  return result
}

// Helper: Fetch all sets for name lookup
let setsCache = null
async function fetchAllSets() {
  if (setsCache) return setsCache
  
  if (!isSupabaseConfigured()) return {}
  
  const { data, error } = await supabase
    .from('sets')
    .select('set_id, name')
  
  if (error) {
    console.error('Error fetching sets:', error)
    return {}
  }
  
  // Create a map of set_id -> name
  setsCache = {}
  if (data) {
    data.forEach(s => {
      setsCache[s.set_id] = s.name
    })
  }
  
  return setsCache
}

// Helper: Fetch cards by IDs in batches (with set name lookup)
async function fetchCardsByIds(cardIds) {
  if (!isSupabaseConfigured() || !cardIds || cardIds.length === 0) return null
  
  // First, get all sets for name lookup
  const setsMap = await fetchAllSets()
  
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
      // Add set_name from lookup
      const cardsWithSetName = data.map(card => ({
        ...card,
        set_name: setsMap[card.set_id] || null
      }))
      allCards = allCards.concat(cardsWithSetName)
    }
  }
  
  return allCards
}

// Helper: Fetch latest prices by card IDs (with forward-fill, 24h change, and 30-day volume)
async function fetchLatestPricesByCardIds(cardIds) {
  if (!isSupabaseConfigured() || !cardIds || cardIds.length === 0) return null

  // Get the two most recent DISTINCT price dates for 24h change calculation
  // We paginate until we find at least 2 distinct dates (since each date has thousands of cards)
  const uniqueDates = new Set()
  let offset = 0
  const PAGE_SIZE = 1000

  while (uniqueDates.size < 2 && offset < 50000) {
    const { data: batch, error } = await supabase
      .from('card_prices_daily')
      .select('price_date')
      .order('price_date', { ascending: false })
      .range(offset, offset + PAGE_SIZE - 1)

    if (error || !batch || batch.length === 0) break

    batch.forEach(r => uniqueDates.add(r.price_date))
    offset += PAGE_SIZE
  }

  if (uniqueDates.size === 0) return null

  // Sort dates descending and take first 2
  const sortedDates = [...uniqueDates].sort((a, b) => b.localeCompare(a))
  const latestDate = sortedDates[0]
  const previousDate = sortedDates.length > 1 ? sortedDates[1] : null

  console.log(`Price dates for 24h change: latest=${latestDate}, previous=${previousDate}`)

  const BATCH_SIZE = 100
  let latestPrices = []
  let previousPrices = []

  // First pass: fetch prices for the latest date
  for (let i = 0; i < cardIds.length; i += BATCH_SIZE) {
    const batchIds = cardIds.slice(i, i + BATCH_SIZE)

    const { data, error } = await supabase
      .from('card_prices_daily')
      .select('card_id, price_date, market_price, nm_price, daily_volume')
      .eq('price_date', latestDate)
      .in('card_id', batchIds)

    if (error) {
      console.error('Error fetching prices batch:', error)
      continue
    }

    if (data) {
      latestPrices = latestPrices.concat(data)
    }
  }

  // Fetch previous day prices for 24h change calculation
  if (previousDate) {
    for (let i = 0; i < cardIds.length; i += BATCH_SIZE) {
      const batchIds = cardIds.slice(i, i + BATCH_SIZE)

      const { data, error } = await supabase
        .from('card_prices_daily')
        .select('card_id, market_price, nm_price')
        .eq('price_date', previousDate)
        .in('card_id', batchIds)

      if (error) {
        console.error('Error fetching previous prices batch:', error)
        continue
      }

      if (data) {
        previousPrices = previousPrices.concat(data)
      }
    }
  }

  // Create previous prices map
  const previousPricesMap = {}
  previousPrices.forEach(p => {
    previousPricesMap[p.card_id] = parseFloat(p.market_price || p.nm_price || 0)
  })

  // Forward-fill missing cards from latest date
  const foundIds = new Set(latestPrices.map(p => p.card_id))
  const missingIds = cardIds.filter(id => !foundIds.has(id))

  if (missingIds.length > 0) {
    console.log(`Forward-filling prices for ${missingIds.length} cards missing from latest date`)

    for (let i = 0; i < missingIds.length; i += BATCH_SIZE) {
      const batchIds = missingIds.slice(i, i + BATCH_SIZE)

      const { data, error } = await supabase
        .from('card_prices_daily')
        .select('card_id, price_date, market_price, nm_price, daily_volume')
        .in('card_id', batchIds)
        .order('price_date', { ascending: false })

      if (error) {
        console.error('Error fetching forward-fill prices:', error)
        continue
      }

      if (data) {
        const seenCards = new Set()
        data.forEach(p => {
          if (!seenCards.has(p.card_id)) {
            seenCards.add(p.card_id)
            latestPrices.push(p)
          }
        })
      }
    }
  }

  // Fetch 30-day volume for each card
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 32) // A bit more to account for D-2
  const thirtyDaysAgoStr = thirtyDaysAgo.toISOString().split('T')[0]

  let volumeData = []
  for (let i = 0; i < cardIds.length; i += BATCH_SIZE) {
    const batchIds = cardIds.slice(i, i + BATCH_SIZE)

    const { data, error } = await supabase
      .from('card_prices_daily')
      .select('card_id, daily_volume')
      .in('card_id', batchIds)
      .gte('price_date', thirtyDaysAgoStr)

    if (error) {
      console.error('Error fetching volume data:', error)
      continue
    }

    if (data) {
      volumeData = volumeData.concat(data)
    }
  }

  // Aggregate 30-day volume per card
  const volumeMap = {}
  volumeData.forEach(v => {
    if (!volumeMap[v.card_id]) {
      volumeMap[v.card_id] = 0
    }
    volumeMap[v.card_id] += parseFloat(v.daily_volume || 0)
  })

  // Enhance latest prices with change and monthly volume
  return latestPrices.map(p => {
    const currentPrice = parseFloat(p.market_price || p.nm_price || 0)
    const prevPrice = previousPricesMap[p.card_id]
    let change = 0

    if (prevPrice && prevPrice > 0 && currentPrice > 0) {
      change = ((currentPrice - prevPrice) / prevPrice) * 100
    }

    return {
      ...p,
      change_24h: change,
      monthly_volume: Math.round(volumeMap[p.card_id] || 0)
    }
  })
}

// ============================================================================
// ALL CARDS
// ============================================================================

/**
 * Récupère les cartes présentes dans les index (constituants actuels)
 */
export async function getAllEligibleCards() {
  if (!isSupabaseConfigured()) return null
  
  // First, get all sets for name lookup
  const setsMap = await fetchAllSets()
  
  // Récupérer les constituants actuels pour savoir quelles cartes sont dans les index
  const allConstituents = await fetchAllPaginated(
    'constituents_monthly',
    'item_id, index_code, month, weight, rank',
    {},
    { column: 'month', ascending: false }
  )
  
  if (!allConstituents || allConstituents.length === 0) {
    console.error('No constituents found')
    return null
  }
  
  // Trouver le mois le plus récent
  const latestMonth = allConstituents[0]?.month
  const currentConstituents = allConstituents.filter(c => c.month === latestMonth)
  
  // Créer un map des index par carte + récupérer les IDs uniques
  const cardIndexes = {}
  const uniqueCardIds = new Set()
  
  currentConstituents.forEach(c => {
    uniqueCardIds.add(c.item_id)

    if (!cardIndexes[c.item_id]) {
      cardIndexes[c.item_id] = {
        inRare100: false,
        inRare500: false,
        inRareAll: false,
        weight: 0,
        rank: 999
      }
    }
    if (c.index_code === 'RARE_100') {
      cardIndexes[c.item_id].inRare100 = true
      cardIndexes[c.item_id].weight = c.weight || 0
      cardIndexes[c.item_id].rank = c.rank || 999
    }
    if (c.index_code === 'RARE_500') {
      cardIndexes[c.item_id].inRare500 = true
      if (!cardIndexes[c.item_id].inRare100) {
        cardIndexes[c.item_id].weight = c.weight || 0
        cardIndexes[c.item_id].rank = c.rank || 999
      }
    }
    if (c.index_code === 'RARE_ALL') {
      cardIndexes[c.item_id].inRareAll = true
      // Only set weight/rank from RARE_ALL if not already in RARE_100 or RARE_500
      if (!cardIndexes[c.item_id].inRare100 && !cardIndexes[c.item_id].inRare500) {
        cardIndexes[c.item_id].weight = c.weight || 0
        cardIndexes[c.item_id].rank = c.rank || 999
      }
    }
  })
  
  const cardIds = Array.from(uniqueCardIds)
  
  console.log(`Found ${cardIds.length} unique cards in indexes for month ${latestMonth}`)
  
  // Récupérer les infos des cartes
  const cards = await fetchCardsByIds(cardIds)
  
  if (!cards || cards.length === 0) {
    console.error('No cards found')
    return null
  }
  
  // Récupérer les derniers prix
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
    const indexes = cardIndexes[card.card_id] || { inRare100: false, inRare500: false, inRareAll: false, weight: 0, rank: 999 }

    return {
      id: card.card_id,
      name: card.name || card.card_id,
      set: card.set_name || card.set_id || 'Unknown',
      setId: card.set_id,
      number: card.card_number || '',
      rarity: card.rarity || 'Rare',
      price: parseFloat(price.market_price || price.nm_price || 0),
      tcgplayerId: card.tcgplayer_id,
      pptId: card.ppt_id,
      change: price.change_24h || 0,
      sales: price.monthly_volume || 0,
      weight: indexes.weight,
      rank: indexes.rank,
      ...indexes
    }
  })
  
  // Trier par rank (les mieux classés en premier)
  result.sort((a, b) => a.rank - b.rank)
  
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
