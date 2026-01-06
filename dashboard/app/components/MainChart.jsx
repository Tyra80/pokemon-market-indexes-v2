'use client';

import React from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { colors } from '../lib/theme';
import { formatNumber } from '../lib/utils';

const MainChart = ({ data, indexCode }) => {
  const [period, setPeriod] = React.useState('ITD');
  const color = colors.chart[indexCode];

  const filteredData = React.useMemo(() => {
    if (!data || data.length === 0) return [];

    if (period === 'ITD') return data;

    const now = new Date();
    let cutoffDate;

    if (period === '30D') {
      cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - 30);
    } else if (period === '1Y') {
      cutoffDate = new Date();
      cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
    }

    return data.filter(d => new Date(d.date) >= cutoffDate);
  }, [data, period]);

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

  const PeriodButton = ({ value, label }) => (
    <button
      onClick={() => setPeriod(value)}
      style={{
        padding: '6px 12px',
        borderRadius: '6px',
        border: 'none',
        background: period === value ? colors.accent.gold : colors.bg.tertiary,
        color: period === value ? colors.bg.primary : colors.text.secondary,
        fontSize: '0.75rem',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 0.2s'
      }}
    >
      {label}
    </button>
  );

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

        <div style={{ display: 'flex', gap: '8px' }}>
          <PeriodButton value="30D" label="30D" />
          <PeriodButton value="1Y" label="1Y" />
          <PeriodButton value="ITD" label="ITD" />
        </div>
      </div>

      <ResponsiveContainer width="100%" height={350}>
        <AreaChart data={filteredData}>
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

export default MainChart;
