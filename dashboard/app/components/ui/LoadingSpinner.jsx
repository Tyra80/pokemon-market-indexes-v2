'use client';

import { colors } from '../../lib/theme';

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

export default LoadingSpinner;
