'use client'

import React, { useState, useMemo, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Area, AreaChart, CartesianGrid } from 'recharts';
import { getAllIndexHistory, getLatestIndexValues, getConstituents, getAllEligibleCards, getCardPriceHistory } from '../lib/api';
import { isSupabaseConfigured } from '../lib/supabase';

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

const MOCK_INDEX_DATA = {
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

const MOCK_CONSTITUENTS = {
  RARE_100: generateMockConstituents(100),
  RARE_500: generateMockConstituents(150),
  RARE_ALL: generateMockConstituents(150)
};

const generateCardPriceHistoryMock = (currentPrice, days = 180) => {
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

// ============================================================================
// DESIGN TOKENS
// ============================================================================

const colors = {
  bg: {
    primary: '#0a0a0f',
    secondary: '#12121a',
    tertiary: '#1a1a24',
    card: '#16161f',
    hover: '#1e1e2a'
  },
  text: {
    primary: '#f0f0f5',
    secondary: '#8888a0',
    muted: '#55556a'
  },
  accent: {
    gold: '#f5c842',
    goldDark: '#c9a435',
    blue: '#4a9eff',
    green: '#22c55e',
    red: '#ef4444',
    purple: '#a855f7'
  },
  border: '#2a2a3a',
  chart: {
    RARE_100: '#f5c842',
    RARE_500: '#4a9eff',
    RARE_ALL: '#a855f7'
  }
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

const formatNumber = (num, decimals = 2) => {
  if (num === null || num === undefined || isNaN(num)) return '—';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(num);
};

const formatCurrency = (num) => {
  if (num === null || num === undefined || isNaN(num)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(num);
};

// ============================================================================
// UTILITY COMPONENTS
// ============================================================================

const ChangeIndicator = ({ value, size = 'normal' }) => {
  if (value === null || value === undefined || isNaN(value)) {
    return <span style={{ color: colors.text.muted }}>—</span>;
  }
  
  const isPositive = value >= 0;
  const fontSize = size === 'large' ? '1.25rem' : size === 'small' ? '0.75rem' : '0.875rem';
  
  return (
    <span style={{
      color: isPositive ? colors.accent.green : colors.accent.red,
      fontSize,
      fontWeight: 600,
      fontFamily: "'JetBrains Mono', monospace"
    }}>
      {isPositive ? '▲' : '▼'} {Math.abs(value).toFixed(2)}%
    </span>
  );
};

const LoadingSpinner = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '40px'
  }}>
    <div style={{
      width: '40px',
      height: '40px',
      border: `3px solid ${colors.border}`,
      borderTopColor: colors.accent.gold,
      borderRadius: '50%',
      animation: 'spin 1s linear infinite'
    }} />
    <style>{`
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
    `}</style>
  </div>
);

const DataSourceBadge = ({ isLive }) => (
  <div style={{
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px',
    background: isLive ? `${colors.accent.green}20` : `${colors.accent.gold}20`,
    borderRadius: '4px',
    fontSize: '0.7rem',
    fontWeight: 600
  }}>
    <div style={{
      width: '6px',
      height: '6px',
      borderRadius: '50%',
      background: isLive ? colors.accent.green : colors.accent.gold
    }} />
    <span style={{ color: isLive ? colors.accent.green : colors.accent.gold }}>
      {isLive ? 'LIVE DATA' : 'MOCK DATA'}
    </span>
  </div>
);

const IndexBadge = ({ code, small = false }) => (
  <span style={{
    background: colors.chart[code] + '20',
    color: colors.chart[code],
    padding: small ? '2px 6px' : '4px 10px',
    borderRadius: '4px',
    fontSize: small ? '0.65rem' : '0.7rem',
    fontWeight: 600,
    letterSpacing: '0.02em'
  }}>
    {code}
  </span>
);

// ============================================================================
// CARD IMAGE COMPONENT
// ============================================================================

const getCardImageUrl = (tcgplayerId, size = 400) => {
  if (!tcgplayerId) return null;
  return `https://tcgplayer-cdn.tcgplayer.com/product/${tcgplayerId}_in_${size}x${size}.jpg`;
};

const CardImage = ({ tcgplayerId, name, size = 'small' }) => {
  const [imageError, setImageError] = React.useState(false);
  const [imageLoaded, setImageLoaded] = React.useState(false);
  
  const sizeStyles = {
    small: { width: '36px', height: '50px' },
    medium: { width: '60px', height: '84px' },
    large: { width: '100%', height: '280px' }
  };
  
  const imageUrl = getCardImageUrl(tcgplayerId, size === 'large' ? 800 : 400);
  
  if (!tcgplayerId || imageError) {
    return (
      <div style={{
        ...sizeStyles[size],
        background: `linear-gradient(135deg, ${colors.accent.gold}30, ${colors.accent.purple}30)`,
        borderRadius: size === 'large' ? '12px' : '4px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size === 'large' ? '2rem' : '0.8rem',
        color: colors.text.muted,
        border: `1px solid ${colors.border}`
      }}>
        🃏
      </div>
    );
  }
  
  return (
    <div style={{
      ...sizeStyles[size],
      position: 'relative',
      borderRadius: size === 'large' ? '12px' : '4px',
      overflow: 'hidden',
      background: `linear-gradient(135deg, ${colors.accent.gold}20, ${colors.accent.purple}20)`
    }}>
      {!imageLoaded && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '0.6rem',
          color: colors.text.muted
        }}>
          ...
        </div>
      )}
      <img
        src={imageUrl}
        alt={name || 'Pokemon Card'}
        loading="lazy"
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: imageLoaded ? 1 : 0,
          transition: 'opacity 0.3s'
        }}
        onLoad={() => setImageLoaded(true)}
        onError={() => setImageError(true)}
      />
    </div>
  );
};

const ExternalLinkButton = ({ href, children, variant = 'default' }) => {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '8px 14px',
    borderRadius: '6px',
    fontSize: '0.8rem',
    fontWeight: 500,
    textDecoration: 'none',
    transition: 'all 0.2s',
    cursor: 'pointer'
  };
  
  const variants = {
    default: {
      background: colors.bg.tertiary,
      color: colors.text.secondary,
      border: `1px solid ${colors.border}`
    },
    tcgplayer: {
      background: '#1a4d8c20',
      color: '#5b9bd5',
      border: '1px solid #1a4d8c40'
    },
    pokeprices: {
      background: `${colors.accent.gold}15`,
      color: colors.accent.gold,
      border: `1px solid ${colors.accent.gold}30`
    }
  };
  
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{ ...baseStyle, ...variants[variant] }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-1px)';
        e.currentTarget.style.opacity = '0.9';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.opacity = '1';
      }}
    >
      {children}
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
        <polyline points="15 3 21 3 21 9"/>
        <line x1="10" y1="14" x2="21" y2="3"/>
      </svg>
    </a>
  );
};

// ============================================================================
// NAVIGATION
// ============================================================================

const NavLink = ({ active, onClick, children }) => (
  <button
    onClick={onClick}
    style={{
      background: 'transparent',
      border: 'none',
      color: active ? colors.text.primary : colors.text.muted,
      fontSize: '0.9rem',
      fontWeight: active ? 600 : 400,
      cursor: 'pointer',
      padding: '8px 0',
      position: 'relative',
      transition: 'color 0.2s'
    }}
    onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = colors.text.secondary; }}
    onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = colors.text.muted; }}
  >
    {children}
    {active && (
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: colors.accent.gold,
        borderRadius: '1px'
      }} />
    )}
  </button>
);

const Header = ({ currentPage, onNavigate, isLive, lastUpdate }) => {
  return (
    <header style={{
      borderBottom: `1px solid ${colors.border}`,
      marginBottom: '32px'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '24px 0'
      }}>
        <div 
          style={{ display: 'flex', alignItems: 'center', gap: '16px', cursor: 'pointer' }}
          onClick={() => onNavigate('dashboard')}
        >
          <div style={{
            width: '48px',
            height: '48px',
            background: `linear-gradient(135deg, ${colors.accent.gold}, ${colors.accent.goldDark})`,
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 800,
            fontSize: '1.25rem',
            color: colors.bg.primary
          }}>
            PM
          </div>
          <div>
            <h1 style={{
              margin: 0,
              fontSize: '1.5rem',
              fontWeight: 700,
              color: colors.text.primary,
              letterSpacing: '-0.02em'
            }}>
              Pokémon Market Indexes
            </h1>
            <p style={{
              margin: 0,
              fontSize: '0.8rem',
              color: colors.text.muted
            }}>
              Daily collectibles market indicators
            </p>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          <nav style={{ display: 'flex', gap: '24px' }}>
            <NavLink active={currentPage === 'dashboard'} onClick={() => onNavigate('dashboard')}>
              Dashboard
            </NavLink>
            <NavLink active={currentPage === 'cards'} onClick={() => onNavigate('cards')}>
              All Cards
            </NavLink>
            <NavLink active={currentPage === 'methodology'} onClick={() => onNavigate('methodology')}>
              Methodology
            </NavLink>
          </nav>
          
          <div style={{
            height: '24px',
            width: '1px',
            background: colors.border
          }} />
          
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
            <DataSourceBadge isLive={isLive} />
            <div style={{ color: colors.text.muted, fontSize: '0.75rem' }}>
              {lastUpdate}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

// ============================================================================
// DASHBOARD COMPONENTS
// ============================================================================

const SparkLine = ({ data, color, height = 40 }) => {
  if (!data || data.length === 0) {
    return <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.text.muted }}>No data</div>;
  }
  
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data.slice(-30)}>
        <defs>
          <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#gradient-${color})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

const IndexCard = ({ code, name, data, latestData, isSelected, onClick }) => {
  const latestValue = latestData?.index_value || data[data.length - 1]?.value || 100;
  
  // Calculer change_1d depuis les données si non disponible
  let change1d = latestData?.change_1d;
  if ((change1d === null || change1d === undefined) && data.length >= 2) {
    const yesterday = data[data.length - 2]?.value;
    const today = data[data.length - 1]?.value;
    if (yesterday && today) {
      change1d = ((today - yesterday) / yesterday) * 100;
    }
  }
  
  // Calculer change_1m depuis les données si non disponible
  let change1m = latestData?.change_1m;
  if ((change1m === null || change1m === undefined) && data.length >= 30) {
    const monthAgo = data[data.length - 30]?.value;
    const today = data[data.length - 1]?.value;
    if (monthAgo && today) {
      change1m = ((today - monthAgo) / monthAgo) * 100;
    }
  }
  
  const totalChange = change1m;
  
  return (
    <div
      onClick={onClick}
      style={{
        background: isSelected ? colors.bg.tertiary : colors.bg.card,
        border: `1px solid ${isSelected ? colors.chart[code] : colors.border}`,
        borderRadius: '12px',
        padding: '20px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'relative',
        overflow: 'hidden'
      }}
      onMouseEnter={(e) => {
        if (!isSelected) e.currentTarget.style.borderColor = colors.chart[code] + '60';
      }}
      onMouseLeave={(e) => {
        if (!isSelected) e.currentTarget.style.borderColor = colors.border;
      }}
    >
      {isSelected && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '3px',
          background: colors.chart[code]
        }} />
      )}
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
        <div>
          <div style={{
            fontSize: '0.75rem',
            color: colors.text.muted,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            marginBottom: '4px'
          }}>
            {name}
          </div>
          <div style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            color: colors.text.primary,
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            {formatNumber(latestValue)}
          </div>
        </div>
        <IndexBadge code={code} />
      </div>
      
      <SparkLine data={data} color={colors.chart[code]} />
      
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        marginTop: '12px',
        paddingTop: '12px',
        borderTop: `1px solid ${colors.border}`
      }}>
        <div>
          <div style={{ fontSize: '0.7rem', color: colors.text.muted, marginBottom: '2px' }}>24H</div>
          <ChangeIndicator value={change1d} size="small" />
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.7rem', color: colors.text.muted, marginBottom: '2px' }}>30D</div>
          <ChangeIndicator value={totalChange} size="small" />
        </div>
      </div>
    </div>
  );
};

const MainChart = ({ data, indexCode }) => {
  const color = colors.chart[indexCode];
  
  if (!data || data.length === 0) {
    return (
      <div style={{
        background: colors.bg.card,
        border: `1px solid ${colors.border}`,
        borderRadius: '12px',
        padding: '24px',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '400px',
        color: colors.text.muted
      }}>
        No chart data available
      </div>
    );
  }
  
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.[0]) return null;
    
    return (
      <div style={{
        background: colors.bg.secondary,
        border: `1px solid ${colors.border}`,
        borderRadius: '8px',
        padding: '12px 16px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.5)'
      }}>
        <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '4px' }}>
          {label}
        </div>
        <div style={{
          color: color,
          fontSize: '1.25rem',
          fontWeight: 700,
          fontFamily: "'JetBrains Mono', monospace"
        }}>
          {formatNumber(payload[0].value)}
        </div>
      </div>
    );
  };
  
  return (
    <div style={{
      background: colors.bg.card,
      border: `1px solid ${colors.border}`,
      borderRadius: '12px',
      padding: '24px'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '24px'
      }}>
        <h3 style={{
          margin: 0,
          fontSize: '1rem',
          color: colors.text.secondary,
          fontWeight: 500
        }}>
          Index Performance
        </h3>
      </div>
      
      <ResponsiveContainer width="100%" height={350}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="mainChartGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.2} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
          <XAxis
            dataKey="displayDate"
            axisLine={false}
            tickLine={false}
            tick={{ fill: colors.text.muted, fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: colors.text.muted, fontSize: 11 }}
            domain={['dataMin - 5', 'dataMax + 5']}
            tickFormatter={(v) => formatNumber(v, 0)}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2.5}
            fill="url(#mainChartGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

const ConstituentRow = ({ card, rank, onClick, isSelected }) => {
  return (
    <tr
      onClick={() => onClick(card)}
      style={{
        cursor: 'pointer',
        background: isSelected ? colors.bg.tertiary : 'transparent',
        transition: 'background 0.15s'
      }}
      onMouseEnter={(e) => e.currentTarget.style.background = colors.bg.hover}
      onMouseLeave={(e) => e.currentTarget.style.background = isSelected ? colors.bg.tertiary : 'transparent'}
    >
      <td style={{ padding: '14px 16px', borderBottom: `1px solid ${colors.border}` }}>
        <span style={{
          color: colors.text.muted,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '0.8rem'
        }}>
          #{rank}
        </span>
      </td>
      <td style={{ padding: '14px 16px', borderBottom: `1px solid ${colors.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <CardImage tcgplayerId={card.tcgplayerId} name={card.name} size="small" />
          <div>
            <div style={{ color: colors.text.primary, fontWeight: 600, marginBottom: '2px' }}>
              {card.name}
            </div>
            <div style={{ color: colors.text.muted, fontSize: '0.75rem' }}>
              {card.set} · {card.number}
            </div>
          </div>
        </div>
      </td>
      <td style={{ padding: '14px 16px', borderBottom: `1px solid ${colors.border}` }}>
        <span style={{
          background: colors.bg.tertiary,
          padding: '4px 8px',
          borderRadius: '4px',
          fontSize: '0.7rem',
          color: colors.text.secondary
        }}>
          {card.rarity}
        </span>
      </td>
      <td style={{
        padding: '14px 16px',
        borderBottom: `1px solid ${colors.border}`,
        fontFamily: "'JetBrains Mono', monospace",
        textAlign: 'right'
      }}>
        {formatCurrency(card.price)}
      </td>
      <td style={{
        padding: '14px 16px',
        borderBottom: `1px solid ${colors.border}`,
        textAlign: 'right'
      }}>
        <ChangeIndicator value={card.change} size="small" />
      </td>
      <td style={{
        padding: '14px 16px',
        borderBottom: `1px solid ${colors.border}`,
        fontFamily: "'JetBrains Mono', monospace",
        textAlign: 'right',
        color: colors.text.secondary
      }}>
        {card.weight ? `${(card.weight * 100).toFixed(2)}%` : '—'}
      </td>
      <td style={{
        padding: '14px 16px',
        borderBottom: `1px solid ${colors.border}`,
        fontFamily: "'JetBrains Mono', monospace",
        textAlign: 'right',
        color: colors.text.muted
      }}>
        {card.sales?.toLocaleString() || '—'}
      </td>
    </tr>
  );
};

const ConstituentsTable = ({ constituents, onCardClick, selectedCard, limit = 10, loading }) => {
  if (loading) {
    return (
      <div style={{
        background: colors.bg.card,
        border: `1px solid ${colors.border}`,
        borderRadius: '12px',
        overflow: 'hidden'
      }}>
        <LoadingSpinner />
      </div>
    );
  }
  
  const displayedCards = constituents?.slice(0, limit) || [];
  
  return (
    <div style={{
      background: colors.bg.card,
      border: `1px solid ${colors.border}`,
      borderRadius: '12px',
      overflow: 'hidden'
    }}>
      <div style={{
        padding: '20px 24px',
        borderBottom: `1px solid ${colors.border}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h3 style={{
          margin: 0,
          fontSize: '1rem',
          color: colors.text.secondary,
          fontWeight: 500
        }}>
          Top Constituents
        </h3>
        <span style={{
          color: colors.text.muted,
          fontSize: '0.8rem'
        }}>
          Showing {displayedCards.length} of {constituents?.length || 0} cards
        </span>
      </div>
      
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: colors.bg.secondary }}>
              {['#', 'Card', 'Rarity', 'Price', '24h', 'Weight', 'Sales/Mo'].map((header, i) => (
                <th
                  key={header}
                  style={{
                    padding: '12px 16px',
                    textAlign: i >= 3 ? 'right' : 'left',
                    color: colors.text.muted,
                    fontWeight: 500,
                    fontSize: '0.7rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    borderBottom: `1px solid ${colors.border}`
                  }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayedCards.map((card, i) => (
              <ConstituentRow
                key={card.id}
                card={card}
                rank={card.rank || i + 1}
                onClick={onCardClick}
                isSelected={selectedCard?.id === card.id}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const CardDetailPanel = ({ card, onClose, priceHistory, loadingHistory }) => {
  const tcgplayerUrl = card.tcgplayerId 
    ? `https://www.tcgplayer.com/product/${card.tcgplayerId}`
    : `https://www.tcgplayer.com/search/pokemon/product?q=${encodeURIComponent(card.name)}`;
  const pokepricesUrl = card.pptId 
    ? `https://pokemonprices.com/card/${card.pptId}`
    : `https://pokemonprices.com/search?q=${encodeURIComponent(card.name)}`;
  
  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      bottom: 0,
      width: '480px',
      background: colors.bg.secondary,
      borderLeft: `1px solid ${colors.border}`,
      padding: '24px',
      overflowY: 'auto',
      zIndex: 1000,
      animation: 'slideIn 0.3s ease'
    }}>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
      
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '24px'
      }}>
        <div>
          <h2 style={{
            margin: 0,
            fontSize: '1.5rem',
            color: colors.text.primary,
            marginBottom: '4px'
          }}>
            {card.name}
          </h2>
          <div style={{ color: colors.text.muted, fontSize: '0.875rem' }}>
            {card.set} · {card.number}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: colors.text.muted,
            fontSize: '1.5rem',
            cursor: 'pointer',
            padding: '4px 8px',
            lineHeight: 1
          }}
        >
          ×
        </button>
      </div>
      
      <div style={{
        display: 'flex',
        gap: '12px',
        marginBottom: '20px'
      }}>
        <ExternalLinkButton href={tcgplayerUrl} variant="tcgplayer">
          View on TCGPlayer
        </ExternalLinkButton>
        <ExternalLinkButton href={pokepricesUrl} variant="pokeprices">
          View on PokePrices
        </ExternalLinkButton>
      </div>
      
      <div style={{ marginBottom: '24px' }}>
        <CardImage tcgplayerId={card.tcgplayerId} name={card.name} size="large" />
      </div>
      
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div style={{
          background: colors.bg.tertiary,
          padding: '16px',
          borderRadius: '8px'
        }}>
          <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '4px' }}>
            CURRENT PRICE
          </div>
          <div style={{
            color: colors.text.primary,
            fontSize: '1.5rem',
            fontWeight: 700,
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            {formatCurrency(card.price)}
          </div>
        </div>
        <div style={{
          background: colors.bg.tertiary,
          padding: '16px',
          borderRadius: '8px'
        }}>
          <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '4px' }}>
            24H CHANGE
          </div>
          <ChangeIndicator value={card.change} size="large" />
        </div>
        <div style={{
          background: colors.bg.tertiary,
          padding: '16px',
          borderRadius: '8px'
        }}>
          <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '4px' }}>
            INDEX WEIGHT
          </div>
          <div style={{
            color: colors.accent.gold,
            fontSize: '1.25rem',
            fontWeight: 600,
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            {card.weight ? `${(card.weight * 100).toFixed(2)}%` : '—'}
          </div>
        </div>
        <div style={{
          background: colors.bg.tertiary,
          padding: '16px',
          borderRadius: '8px'
        }}>
          <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '4px' }}>
            LIQUIDITY SCORE
          </div>
          <div style={{
            color: colors.accent.blue,
            fontSize: '1.25rem',
            fontWeight: 600,
            fontFamily: "'JetBrains Mono', monospace"
          }}>
            {card.liquidityScore?.toFixed(2) || card.sales?.toLocaleString() || '—'}
          </div>
        </div>
      </div>
      
      <div style={{
        background: colors.bg.card,
        border: `1px solid ${colors.border}`,
        borderRadius: '12px',
        padding: '20px'
      }}>
        <h4 style={{
          margin: '0 0 16px 0',
          color: colors.text.secondary,
          fontWeight: 500,
          fontSize: '0.875rem'
        }}>
          Price History (6 Months)
        </h4>
        {loadingHistory ? (
          <LoadingSpinner />
        ) : priceHistory && priceHistory.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={priceHistory}>
              <defs>
                <linearGradient id="cardPriceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colors.accent.gold} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={colors.accent.gold} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border} vertical={false} />
              <XAxis
                dataKey="displayDate"
                axisLine={false}
                tickLine={false}
                tick={{ fill: colors.text.muted, fontSize: 10 }}
                interval={29}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: colors.text.muted, fontSize: 10 }}
                tickFormatter={(v) => `$${v}`}
              />
              <Tooltip
                contentStyle={{
                  background: colors.bg.secondary,
                  border: `1px solid ${colors.border}`,
                  borderRadius: '8px'
                }}
                labelStyle={{ color: colors.text.muted }}
                formatter={(value) => [formatCurrency(value), 'Price']}
              />
              <Area
                type="monotone"
                dataKey="price"
                stroke={colors.accent.gold}
                strokeWidth={2}
                fill="url(#cardPriceGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ textAlign: 'center', color: colors.text.muted, padding: '40px' }}>
            No price history available
          </div>
        )}
      </div>
      
      <div style={{
        marginTop: '20px',
        padding: '16px',
        background: colors.bg.tertiary,
        borderRadius: '8px'
      }}>
        <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '8px' }}>
          APPEARS IN INDEXES
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {card.inRare100 && <IndexBadge code="RARE_100" />}
          {card.inRare500 && <IndexBadge code="RARE_500" />}
          {card.inRareAll && <IndexBadge code="RARE_ALL" />}
          {!card.inRare100 && !card.inRare500 && !card.inRareAll && (
            <span style={{ color: colors.text.muted, fontSize: '0.8rem' }}>None currently</span>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// PAGE: DASHBOARD
// ============================================================================

const DashboardPage = ({ 
  indexData, 
  latestValues, 
  constituents, 
  onCardClick, 
  selectedCard,
  loading 
}) => {
  const [selectedIndex, setSelectedIndex] = useState('RARE_100');
  
  const indexConfigs = [
    { code: 'RARE_100', name: 'Rare Cards Top 100' },
    { code: 'RARE_500', name: 'Rare Cards Top 500' },
    { code: 'RARE_ALL', name: 'Rare Cards All Liquid' }
  ];
  
  return (
    <>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '20px',
        marginBottom: '32px'
      }}>
        {indexConfigs.map(({ code, name }) => (
          <IndexCard
            key={code}
            code={code}
            name={name}
            data={indexData[code] || []}
            latestData={latestValues?.[code]}
            isSelected={selectedIndex === code}
            onClick={() => setSelectedIndex(code)}
          />
        ))}
      </div>
      
      <div style={{ marginBottom: '32px' }}>
        <MainChart
          data={indexData[selectedIndex] || []}
          indexCode={selectedIndex}
        />
      </div>
      
      <ConstituentsTable
        constituents={constituents[selectedIndex]}
        onCardClick={onCardClick}
        selectedCard={selectedCard}
        limit={20}
        loading={loading}
      />
    </>
  );
};

// ============================================================================
// PAGE: ALL CARDS
// ============================================================================

const AllCardsPage = ({ allCards, onCardClick, selectedCard, loading }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterIndex, setFilterIndex] = useState('all');
  const [filterRarity, setFilterRarity] = useState('all');
  const [sortBy, setSortBy] = useState('price');
  const [sortOrder, setSortOrder] = useState('desc');
  
  const filteredCards = useMemo(() => {
    if (!allCards) return [];
    
    let cards = [...allCards];
    
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      cards = cards.filter(c => 
        c.name?.toLowerCase().includes(term) ||
        c.set?.toLowerCase().includes(term)
      );
    }
    
    if (filterIndex === 'RARE_100') cards = cards.filter(c => c.inRare100);
    else if (filterIndex === 'RARE_500') cards = cards.filter(c => c.inRare500);
    
    if (filterRarity !== 'all') {
      cards = cards.filter(c => c.rarity === filterRarity);
    }
    
    cards.sort((a, b) => {
      const aVal = a[sortBy] || 0;
      const bVal = b[sortBy] || 0;
      const modifier = sortOrder === 'desc' ? -1 : 1;
      return (aVal - bVal) * modifier;
    });
    
    return cards;
  }, [allCards, searchTerm, filterIndex, filterRarity, sortBy, sortOrder]);
  
  const rarities = ['Special Art Rare', 'Ultra Rare', 'Illustration Rare', 'Holo Rare', 'Rare'];
  
  if (loading) {
    return <LoadingSpinner />;
  }
  
  return (
    <div>
      <div style={{
        background: `${colors.accent.blue}10`,
        border: `1px solid ${colors.accent.blue}30`,
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={colors.accent.blue} strokeWidth="2" style={{ flexShrink: 0, marginTop: '2px' }}>
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
          <div>
            <h4 style={{ margin: '0 0 8px 0', color: colors.text.primary, fontSize: '1rem' }}>
              About Eligible Cards
            </h4>
            <p style={{ margin: 0, color: colors.text.secondary, fontSize: '0.875rem', lineHeight: 1.6 }}>
              This list shows cards meeting index eligibility criteria: minimum maturity (≥60 days), minimum liquidity (≥10-20 sales/month), rarity ≥ Rare, and Near Mint condition only.
            </p>
          </div>
        </div>
      </div>
      
      <div style={{
        background: colors.bg.card,
        border: `1px solid ${colors.border}`,
        borderRadius: '12px',
        padding: '20px',
        marginBottom: '24px'
      }}>
        <div style={{
          display: 'flex',
          gap: '16px',
          flexWrap: 'wrap',
          alignItems: 'center'
        }}>
          <div style={{ flex: '1 1 250px' }}>
            <input
              type="text"
              placeholder="Search cards..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                background: colors.bg.secondary,
                border: `1px solid ${colors.border}`,
                borderRadius: '8px',
                color: colors.text.primary,
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>
          
          <select
            value={filterIndex}
            onChange={(e) => setFilterIndex(e.target.value)}
            style={{
              padding: '10px 14px',
              background: colors.bg.secondary,
              border: `1px solid ${colors.border}`,
              borderRadius: '8px',
              color: colors.text.primary,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            <option value="all">All Indexes</option>
            <option value="RARE_100">RARE_100 Only</option>
            <option value="RARE_500">RARE_500 Only</option>
          </select>
          
          <select
            value={filterRarity}
            onChange={(e) => setFilterRarity(e.target.value)}
            style={{
              padding: '10px 14px',
              background: colors.bg.secondary,
              border: `1px solid ${colors.border}`,
              borderRadius: '8px',
              color: colors.text.primary,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            <option value="all">All Rarities</option>
            {rarities.map(r => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          
          <select
            value={`${sortBy}-${sortOrder}`}
            onChange={(e) => {
              const [by, order] = e.target.value.split('-');
              setSortBy(by);
              setSortOrder(order);
            }}
            style={{
              padding: '10px 14px',
              background: colors.bg.secondary,
              border: `1px solid ${colors.border}`,
              borderRadius: '8px',
              color: colors.text.primary,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            <option value="price-desc">Price: High to Low</option>
            <option value="price-asc">Price: Low to High</option>
            <option value="change-desc">Change: High to Low</option>
            <option value="change-asc">Change: Low to High</option>
          </select>
        </div>
        
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: `1px solid ${colors.border}`,
          color: colors.text.muted,
          fontSize: '0.8rem'
        }}>
          Showing {filteredCards.length} eligible cards
        </div>
      </div>
      
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: '16px'
      }}>
        {filteredCards.slice(0, 50).map((card) => (
          <div
            key={card.id}
            onClick={() => onCardClick(card)}
            style={{
              background: colors.bg.card,
              border: `1px solid ${colors.border}`,
              borderRadius: '12px',
              padding: '16px',
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = colors.accent.gold + '60';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = colors.border;
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{ display: 'flex', gap: '14px' }}>
              <CardImage tcgplayerId={card.tcgplayerId} name={card.name} size="medium" />
              
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  color: colors.text.primary,
                  fontWeight: 600,
                  marginBottom: '4px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  {card.name}
                </div>
                <div style={{ color: colors.text.muted, fontSize: '0.75rem', marginBottom: '8px' }}>
                  {card.set}
                </div>
                
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
                  {card.inRare100 && <IndexBadge code="RARE_100" small />}
                  {card.inRare500 && !card.inRare100 && <IndexBadge code="RARE_500" small />}
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{
                    color: colors.text.primary,
                    fontWeight: 700,
                    fontFamily: "'JetBrains Mono', monospace"
                  }}>
                    {formatCurrency(card.price)}
                  </span>
                  <ChangeIndicator value={card.change} size="small" />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {filteredCards.length > 50 && (
        <div style={{
          textAlign: 'center',
          padding: '32px',
          color: colors.text.muted
        }}>
          Showing first 50 cards. Use filters to narrow down results.
        </div>
      )}
    </div>
  );
};

// ============================================================================
// PAGE: METHODOLOGY
// ============================================================================

const MethodologyPage = () => {
  const Section = ({ title, children }) => (
    <div style={{ marginBottom: '40px' }}>
      <h2 style={{
        color: colors.text.primary,
        fontSize: '1.25rem',
        fontWeight: 600,
        marginBottom: '16px',
        paddingBottom: '12px',
        borderBottom: `1px solid ${colors.border}`
      }}>
        {title}
      </h2>
      <div style={{ color: colors.text.secondary, lineHeight: 1.7 }}>
        {children}
      </div>
    </div>
  );
  
  const InfoBox = ({ title, items }) => (
    <div style={{
      background: colors.bg.tertiary,
      border: `1px solid ${colors.border}`,
      borderRadius: '8px',
      padding: '16px 20px',
      marginBottom: '16px'
    }}>
      <div style={{
        color: colors.accent.gold,
        fontWeight: 600,
        marginBottom: '10px',
        fontSize: '0.9rem'
      }}>
        {title}
      </div>
      <div style={{ fontSize: '0.875rem' }}>
        {items.map((item, i) => (
          <div key={i} style={{ marginBottom: i < items.length - 1 ? '6px' : 0 }}>
            • {item}
          </div>
        ))}
      </div>
    </div>
  );
  
  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '40px' }}>
        <h1 style={{
          color: colors.text.primary,
          fontSize: '2rem',
          fontWeight: 700,
          marginBottom: '12px'
        }}>
          Index Methodology
        </h1>
        <p style={{ color: colors.text.muted, fontSize: '1rem' }}>
          Complete documentation of how the Pokémon Market Indexes are constructed and maintained.
        </p>
      </div>
      
      <Section title="Overview">
        <p>
          The Pokémon Market Indexes are a family of transparent market indicators designed to track 
          the Pokémon TCG collectibles market. They focus exclusively on raw (non-graded) cards and 
          provide reliable benchmarks for collectors, investors, and market analysts.
        </p>
      </Section>
      
      <Section title="Index Family">
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '20px'
        }}>
          {[
            { code: 'RARE_100', name: 'Rare Cards Top 100', desc: 'Top 100 cards by composite score.' },
            { code: 'RARE_500', name: 'Rare Cards Top 500', desc: 'Top 500 cards by composite score.' },
            { code: 'RARE_ALL', name: 'Rare Cards All Liquid', desc: 'All cards meeting strict liquidity requirements.' }
          ].map(({ code, name, desc }) => (
            <div key={code} style={{
              background: colors.bg.card,
              border: `1px solid ${colors.chart[code]}40`,
              borderRadius: '12px',
              padding: '20px'
            }}>
              <IndexBadge code={code} />
              <h4 style={{ color: colors.text.primary, margin: '12px 0 8px' }}>{name}</h4>
              <p style={{ fontSize: '0.85rem', margin: 0 }}>{desc}</p>
            </div>
          ))}
        </div>
      </Section>
      
      <Section title="Eligibility Criteria">
        <InfoBox title="Universe" items={[
          'Raw Pokémon cards only (no graded items)',
          'Rarity ≥ Rare (excludes Commons and Uncommons)',
          'Near Mint condition'
        ]} />
        <InfoBox title="Maturity Requirements" items={[
          '≥60 days since set release date',
          '2 consecutive months of eligibility confirmation',
          'Anti-novelty filter to prevent hype distortion'
        ]} />
        <InfoBox title="Liquidity Thresholds" items={[
          'RARE_100: ≥10 sales/month (5 for existing constituents)',
          'RARE_500: ≥20 sales/month (10 for existing constituents)',
          'RARE_ALL: ≥20 sales/month (strict, no tolerance)'
        ]} />
      </Section>
      
      <Section title="Scoring & Selection">
        <p style={{ marginBottom: '16px' }}>
          Cards are ranked using a composite score that balances price and market activity:
        </p>
        <div style={{
          background: colors.bg.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '8px',
          padding: '20px',
          fontFamily: "'JetBrains Mono', monospace",
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <span style={{ color: colors.accent.gold }}>Score</span>
          <span style={{ color: colors.text.muted }}> = </span>
          <span style={{ color: colors.text.primary }}>Composite Price</span>
          <span style={{ color: colors.text.muted }}> × </span>
          <span style={{ color: colors.text.primary }}>Liquidity Score</span>
        </div>
      </Section>
      
      <Section title="Liquidity Estimation">
        <p style={{ marginBottom: '16px' }}>
          Multi-signal approach to estimate liquidity:
        </p>
        {[
          { pct: '50%', color: colors.accent.blue, name: 'Market Activity (Churn)', desc: 'Listing disappearances interpreted as implicit sales' },
          { pct: '30%', color: colors.accent.purple, name: 'Market Presence (Listings)', desc: 'Number and continuity of active listings' },
          { pct: '20%', color: colors.accent.gold, name: 'Price Signal Quality', desc: 'Frequency of price updates and relative stability' }
        ].map(({ pct, color, name, desc }) => (
          <div key={name} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            background: colors.bg.tertiary,
            padding: '14px 18px',
            borderRadius: '8px',
            marginBottom: '12px'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              background: color + '20',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: color,
              fontWeight: 700
            }}>
              {pct}
            </div>
            <div>
              <div style={{ color: colors.text.primary, fontWeight: 600, marginBottom: '2px' }}>{name}</div>
              <div style={{ fontSize: '0.8rem' }}>{desc}</div>
            </div>
          </div>
        ))}
      </Section>
      
      <Section title="Disclaimers">
        <div style={{
          background: `${colors.accent.gold}10`,
          border: `1px solid ${colors.accent.gold}30`,
          borderRadius: '8px',
          padding: '20px'
        }}>
          <p style={{ margin: '0 0 12px 0' }}>
            <strong>For Informational Purposes Only:</strong> The Pokémon Market Indexes do not constitute investment advice.
          </p>
          <p style={{ margin: '0 0 12px 0' }}>
            <strong>No Guarantees:</strong> Past performance is not indicative of future results.
          </p>
          <p style={{ margin: 0 }}>
            <strong>Estimated Liquidity:</strong> Liquidity figures are estimates, not exact transaction volumes.
          </p>
        </div>
      </Section>
      
      <div style={{
        textAlign: 'center',
        padding: '32px',
        borderTop: `1px solid ${colors.border}`,
        marginTop: '40px'
      }}>
        <p style={{ color: colors.text.muted, fontSize: '0.85rem', margin: 0 }}>
          Methodology Version 1.0 — Last Updated: January 2026
        </p>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN APP
// ============================================================================

export default function PokemonMarketDashboard() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardPriceHistory, setCardPriceHistory] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
  const [indexData, setIndexData] = useState(MOCK_INDEX_DATA);
  const [latestValues, setLatestValues] = useState(null);
  const [constituents, setConstituents] = useState(MOCK_CONSTITUENTS);
  const [allCards, setAllCards] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }));
  
  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      
      if (!isSupabaseConfigured()) {
        console.log('Supabase not configured, using mock data');
        setLoading(false);
        return;
      }
      
      try {
        const indexHistory = await getAllIndexHistory();
        if (indexHistory && Object.values(indexHistory).some(arr => arr.length > 0)) {
          setIndexData(indexHistory);
          setIsLive(true);
        }
        
        const latest = await getLatestIndexValues();
        if (latest) {
          setLatestValues(latest);
          
          const dates = Object.values(latest).map(v => v?.value_date).filter(Boolean);
          if (dates.length > 0) {
            const mostRecent = dates.sort().reverse()[0];
            setLastUpdate(new Date(mostRecent).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            }));
          }
        }
        
        const [rare100, rare500, rareAll] = await Promise.all([
          getConstituents('RARE_100'),
          getConstituents('RARE_500'),
          getConstituents('RARE_ALL')
        ]);
        
        if (rare100 || rare500 || rareAll) {
          setConstituents({
            RARE_100: rare100 || MOCK_CONSTITUENTS.RARE_100,
            RARE_500: rare500 || MOCK_CONSTITUENTS.RARE_500,
            RARE_ALL: rareAll || MOCK_CONSTITUENTS.RARE_ALL
          });
        }
        
        const cards = await getAllEligibleCards();
        if (cards) {
          setAllCards(cards);
        }
        
      } catch (error) {
        console.error('Error fetching data:', error);
      }
      
      setLoading(false);
    }
    
    fetchData();
  }, []);
  
  useEffect(() => {
    async function fetchCardHistory() {
      if (!selectedCard) {
        setCardPriceHistory(null);
        return;
      }
      
      setLoadingHistory(true);
      
      if (isSupabaseConfigured()) {
        const history = await getCardPriceHistory(selectedCard.id);
        if (history && history.length > 0) {
          setCardPriceHistory(history);
        } else {
          setCardPriceHistory(generateCardPriceHistoryMock(selectedCard.price || 50));
        }
      } else {
        setCardPriceHistory(generateCardPriceHistoryMock(selectedCard.price || 50));
      }
      
      setLoadingHistory(false);
    }
    
    fetchCardHistory();
  }, [selectedCard]);
  
  const handleCardClick = (card) => {
    setSelectedCard(card);
  };
  
  const renderPage = () => {
    switch (currentPage) {
      case 'methodology':
        return <MethodologyPage />;
      case 'cards':
        return (
          <AllCardsPage 
            allCards={allCards || MOCK_CONSTITUENTS.RARE_ALL} 
            onCardClick={handleCardClick} 
            selectedCard={selectedCard}
            loading={loading}
          />
        );
      default:
        return (
          <DashboardPage 
            indexData={indexData}
            latestValues={latestValues}
            constituents={constituents}
            onCardClick={handleCardClick} 
            selectedCard={selectedCard}
            loading={loading}
          />
        );
    }
  };
  
  return (
    <div style={{
      minHeight: '100vh',
      background: colors.bg.primary,
      color: colors.text.primary,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
    }}>
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '0 32px'
      }}>
        <Header 
          currentPage={currentPage} 
          onNavigate={setCurrentPage}
          isLive={isLive}
          lastUpdate={lastUpdate}
        />
        
        {renderPage()}
        
        <footer style={{
          padding: '24px 0',
          borderTop: `1px solid ${colors.border}`,
          textAlign: 'center',
          marginTop: '48px',
          marginBottom: '32px'
        }}>
          <p style={{ color: colors.text.muted, fontSize: '0.75rem', margin: 0 }}>
            Pokémon Market Indexes · Data for informational purposes only · Not investment advice
          </p>
        </footer>
      </div>
      
      {selectedCard && (
        <>
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              zIndex: 999
            }}
            onClick={() => setSelectedCard(null)}
          />
          <CardDetailPanel
            card={selectedCard}
            onClose={() => setSelectedCard(null)}
            priceHistory={cardPriceHistory}
            loadingHistory={loadingHistory}
          />
        </>
      )}
    </div>
  );
}
