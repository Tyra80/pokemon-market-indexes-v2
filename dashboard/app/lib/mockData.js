// ============================================================================
// MOCK DATA - Fallback when Supabase is not configured or has no data
// ============================================================================

const generateIndexData = (baseValue, volatility, trend, days = 90) => {
  const data = [];
  let value = baseValue;
  const startDate = new Date('2025-10-01');

  for (let i = 0; i < days; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + i);

    const randomChange = (Math.random() - 0.5) * volatility;
    const trendChange = trend * (1 + Math.random() * 0.5);
    value = Math.max(80, value + randomChange + trendChange);

    data.push({
      date: date.toISOString().split('T')[0],
      value: Math.round(value * 100) / 100,
      displayDate: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    });
  }
  return data;
};

export const MOCK_INDEX_DATA = {
  RARE_100: generateIndexData(100, 3, 0.15),
  RARE_500: generateIndexData(100, 2, 0.10),
  RARE_ALL: generateIndexData(100, 1.5, 0.08)
};

const generateMockConstituents = (count) => {
  const pokemonNames = [
    'Charizard ex', 'Pikachu ex', 'Umbreon ex', 'Mew ex', 'Gardevoir ex', 'Arceus VSTAR', 'Rayquaza ex', 'Gengar ex', 'Miraidon ex', 'Lucario ex',
    'Eevee', 'Snorlax', 'Dragonite', 'Mewtwo', 'Gyarados', 'Alakazam', 'Blastoise', 'Venusaur', 'Jolteon', 'Flareon'
  ];
  const sets = ['Surging Sparks', 'Stellar Crown', 'Twilight Masquerade', 'Temporal Forces', 'Paldea Evolved'];
  const rarities = ['Special Art Rare', 'Ultra Rare', 'Illustration Rare', 'Holo Rare', 'Rare'];

  return Array.from({ length: count }, (_, i) => ({
    id: `mock-card-${i}`,
    name: pokemonNames[i % pokemonNames.length],
    set: sets[i % sets.length],
    number: `${100 + i}/191`,
    rarity: rarities[Math.floor(i / 20) % rarities.length],
    price: Math.round((100 - i * 0.8) * 100) / 100,
    change: Math.round((Math.random() - 0.5) * 20 * 10) / 10,
    weight: Math.round((0.03 - i * 0.0002) * 10000) / 10000,
    sales: Math.floor(200 + Math.random() * 800),
    rank: i + 1,
    tcgplayerId: `${400000 + i}`,
    inRare100: i < 100,
    inRare500: true,
    inRareAll: true
  }));
};

export const MOCK_CONSTITUENTS = {
  RARE_100: generateMockConstituents(100),
  RARE_500: generateMockConstituents(150),
  RARE_ALL: generateMockConstituents(150)
};

export const generateCardPriceHistoryMock = (currentPrice, days = 180) => {
  const data = [];
  let price = currentPrice * (0.7 + Math.random() * 0.3);
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  for (let i = 0; i < days; i++) {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + i);

    const change = (Math.random() - 0.48) * (currentPrice * 0.03);
    price = Math.max(currentPrice * 0.3, Math.min(currentPrice * 1.5, price + change));

    data.push({
      date: date.toISOString().split('T')[0],
      price: Math.round(price * 100) / 100,
      displayDate: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    });
  }
  return data;
};
