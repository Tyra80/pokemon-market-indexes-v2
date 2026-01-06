'use client';

import { colors } from '../../lib/theme';

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

export default ChangeIndicator;
