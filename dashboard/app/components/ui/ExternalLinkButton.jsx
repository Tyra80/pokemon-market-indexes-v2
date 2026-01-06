'use client';

import { colors } from '../../lib/theme';

const ExternalLinkButton = ({ href, children, variant = 'default' }) => {
  const baseStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '8px 14px',
    borderRadius: '6px',
    fontSize: '0.8rem',
    fontWeight: 500,
    textDecoration: 'none',
    transition: 'all 0.2s',
    cursor: 'pointer'
  };

  const variants = {
    default: {
      background: colors.bg.tertiary,
      color: colors.text.secondary,
      border: `1px solid ${colors.border}`
    },
    tcgplayer: {
      background: '#1a4d8c20',
      color: '#5b9bd5',
      border: '1px solid #1a4d8c40'
    },
    pokeprices: {
      background: `${colors.accent.gold}15`,
      color: colors.accent.gold,
      border: `1px solid ${colors.accent.gold}30`
    }
  };

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{ ...baseStyle, ...variants[variant] }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-1px)';
        e.currentTarget.style.opacity = '0.9';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.opacity = '1';
      }}
    >
      {children}
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
        <polyline points="15 3 21 3 21 9"/>
        <line x1="10" y1="14" x2="21" y2="3"/>
      </svg>
    </a>
  );
};

export default ExternalLinkButton;
