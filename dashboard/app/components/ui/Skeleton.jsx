'use client';

import { colors } from '../../lib/theme';

export function Skeleton({ width = '100%', height = '20px', borderRadius = '4px', style = {} }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius,
        background: `linear-gradient(90deg, ${colors.bg.tertiary} 25%, ${colors.bg.hover} 50%, ${colors.bg.tertiary} 75%)`,
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        ...style
      }}
    />
  );
}

export function SkeletonCard() {
  return (
    <div style={{
      background: colors.bg.card,
      borderRadius: '12px',
      padding: '20px',
      border: `1px solid ${colors.border}`
    }}>
      <Skeleton width="60%" height="14px" style={{ marginBottom: '12px' }} />
      <Skeleton width="80%" height="32px" style={{ marginBottom: '8px' }} />
      <Skeleton width="40%" height="16px" />
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div style={{
      background: colors.bg.card,
      borderRadius: '12px',
      padding: '24px',
      border: `1px solid ${colors.border}`,
      height: '400px',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
        <Skeleton width="100px" height="32px" borderRadius="6px" />
        <Skeleton width="100px" height="32px" borderRadius="6px" />
        <Skeleton width="100px" height="32px" borderRadius="6px" />
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
        {[40, 60, 45, 80, 55, 70, 50, 65, 75, 60, 85, 70].map((h, i) => (
          <Skeleton key={i} width="100%" height={`${h}%`} borderRadius="4px 4px 0 0" />
        ))}
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 5 }) {
  return (
    <div style={{
      background: colors.bg.card,
      borderRadius: '12px',
      border: `1px solid ${colors.border}`,
      overflow: 'hidden'
    }}>
      <div style={{
        padding: '16px 20px',
        borderBottom: `1px solid ${colors.border}`,
        display: 'flex',
        gap: '16px'
      }}>
        <Skeleton width="40px" height="16px" />
        <Skeleton width="200px" height="16px" />
        <Skeleton width="80px" height="16px" />
        <Skeleton width="100px" height="16px" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{
          padding: '12px 20px',
          borderBottom: i < rows - 1 ? `1px solid ${colors.border}` : 'none',
          display: 'flex',
          gap: '16px',
          alignItems: 'center'
        }}>
          <Skeleton width="24px" height="24px" borderRadius="4px" />
          <Skeleton width="40px" height="56px" borderRadius="4px" />
          <Skeleton width="180px" height="16px" />
          <Skeleton width="60px" height="16px" />
          <Skeleton width="80px" height="16px" />
        </div>
      ))}
    </div>
  );
}
