'use client';

import { colors } from '../lib/theme';
import { formatCurrency } from '../lib/utils';
import { ChangeIndicator, LoadingSpinner, CardImage } from './ui';

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

export default ConstituentsTable;
