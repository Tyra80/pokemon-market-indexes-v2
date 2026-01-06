'use client';

import React from 'react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { colors } from '../lib/theme';
import { formatNumber } from '../lib/utils';
import { ChangeIndicator, IndexBadge } from './ui';

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

  // Calculate change_1d from data if not available
  let change1d = latestData?.change_1d;
  if ((change1d === null || change1d === undefined) && data.length >= 2) {
    const yesterday = data[data.length - 2]?.value;
    const today = data[data.length - 1]?.value;
    if (yesterday && today) {
      change1d = ((today - yesterday) / yesterday) * 100;
    }
  }

  // Calculate change_1m from data if not available
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

export default IndexCard;
