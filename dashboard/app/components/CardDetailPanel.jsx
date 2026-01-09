'use client';

import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { colors } from '../lib/theme';
import { formatCurrency } from '../lib/utils';
import { ChangeIndicator, LoadingSpinner, CardImage, IndexBadge, ExternalLinkButton } from './ui';

const CardDetailPanel = ({ card, onClose, priceHistory, loadingHistory }) => {
  const tcgplayerUrl = card.tcgplayerId
    ? `https://www.tcgplayer.com/product/${card.tcgplayerId}`
    : `https://www.tcgplayer.com/search/pokemon/product?q=${encodeURIComponent(card.name)}`;

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
          x
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
          {card.inRare5000 && <IndexBadge code="RARE_5000" />}
          {!card.inRare100 && !card.inRare500 && !card.inRare5000 && (
            <span style={{ color: colors.text.muted, fontSize: '0.8rem' }}>None currently</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default CardDetailPanel;
