'use client';

import { colors } from '../../lib/theme';

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

export default DataSourceBadge;
