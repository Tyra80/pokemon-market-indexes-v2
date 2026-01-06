'use client';

import { colors } from '../lib/theme';
import { DataSourceBadge } from './ui';

const NavLink = ({ active, onClick, children }) => (
  <button
    onClick={onClick}
    style={{
      background: 'transparent',
      border: 'none',
      color: active ? colors.text.primary : colors.text.muted,
      fontSize: '0.9rem',
      fontWeight: active ? 600 : 400,
      cursor: 'pointer',
      padding: '8px 0',
      position: 'relative',
      transition: 'color 0.2s'
    }}
    onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = colors.text.secondary; }}
    onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = colors.text.muted; }}
  >
    {children}
    {active && (
      <div style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: colors.accent.gold,
        borderRadius: '1px'
      }} />
    )}
  </button>
);

const Header = ({ currentPage, onNavigate, isLive, lastUpdate }) => {
  return (
    <header style={{
      borderBottom: `1px solid ${colors.border}`,
      marginBottom: '32px'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '24px 0'
      }}>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: '16px', cursor: 'pointer' }}
          onClick={() => onNavigate('dashboard')}
        >
          <div style={{
            width: '48px',
            height: '48px',
            background: `linear-gradient(135deg, ${colors.accent.gold}, ${colors.accent.goldDark})`,
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 800,
            fontSize: '1.25rem',
            color: colors.bg.primary
          }}>
            PM
          </div>
          <div>
            <h1 style={{
              margin: 0,
              fontSize: '1.5rem',
              fontWeight: 700,
              color: colors.text.primary,
              letterSpacing: '-0.02em'
            }}>
              Pokemon Market Indexes
            </h1>
            <p style={{
              margin: 0,
              fontSize: '0.8rem',
              color: colors.text.muted
            }}>
              Daily collectibles market indicators
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          <nav style={{ display: 'flex', gap: '24px' }}>
            <NavLink active={currentPage === 'dashboard'} onClick={() => onNavigate('dashboard')}>
              Dashboard
            </NavLink>
            <NavLink active={currentPage === 'cards'} onClick={() => onNavigate('cards')}>
              All Cards
            </NavLink>
            <NavLink active={currentPage === 'methodology'} onClick={() => onNavigate('methodology')}>
              Methodology
            </NavLink>
          </nav>

          <div style={{
            height: '24px',
            width: '1px',
            background: colors.border
          }} />

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
            <DataSourceBadge isLive={isLive} />
            <div style={{ color: colors.text.muted, fontSize: '0.75rem' }}>
              {lastUpdate}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
