'use client';

import { useState, useMemo } from 'react';
import { colors } from '../lib/theme';
import { formatCurrency } from '../lib/utils';
import { ChangeIndicator, CardImage, IndexBadge, ErrorBoundary, SkeletonTable, Skeleton } from '../components/ui';

const RARITIES = ['Special Art Rare', 'Ultra Rare', 'Illustration Rare', 'Holo Rare', 'Rare'];

const AllCardsPageSkeleton = () => (
  <div>
    <Skeleton width="100%" height="100px" borderRadius="12px" style={{ marginBottom: '24px' }} />
    <Skeleton width="100%" height="80px" borderRadius="12px" style={{ marginBottom: '24px' }} />
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
      gap: '16px'
    }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} width="100%" height="120px" borderRadius="12px" />
      ))}
    </div>
  </div>
);

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

  if (loading) {
    return <AllCardsPageSkeleton />;
  }

  return (
    <ErrorBoundary>
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
              Index Constituents
            </h4>
            <p style={{ margin: 0, color: colors.text.secondary, fontSize: '0.875rem', lineHeight: 1.6 }}>
              This list shows all cards currently included in at least one index (RARE_100, RARE_500, or RARE_ALL). Cards are sorted by their index rank.
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
            {RARITIES.map(r => (
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
          Showing {filteredCards.length} cards in indexes
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
    </ErrorBoundary>
  );
};

export default AllCardsPage;
