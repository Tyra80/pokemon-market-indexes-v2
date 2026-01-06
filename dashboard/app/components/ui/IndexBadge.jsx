'use client';

import { colors } from '../../lib/theme';

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

export default IndexBadge;
