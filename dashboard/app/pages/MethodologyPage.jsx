'use client';

import { colors } from '../lib/theme';
import { IndexBadge } from '../components/ui';

const Section = ({ title, children }) => (
  <div style={{ marginBottom: '40px' }}>
    <h2 style={{
      color: colors.text.primary,
      fontSize: '1.25rem',
      fontWeight: 600,
      marginBottom: '16px',
      paddingBottom: '12px',
      borderBottom: `1px solid ${colors.border}`
    }}>
      {title}
    </h2>
    <div style={{ color: colors.text.secondary, lineHeight: 1.7 }}>
      {children}
    </div>
  </div>
);

const InfoBox = ({ title, items }) => (
  <div style={{
    background: colors.bg.tertiary,
    border: `1px solid ${colors.border}`,
    borderRadius: '8px',
    padding: '16px 20px',
    marginBottom: '16px'
  }}>
    <div style={{
      color: colors.accent.gold,
      fontWeight: 600,
      marginBottom: '10px',
      fontSize: '0.9rem'
    }}>
      {title}
    </div>
    <div style={{ fontSize: '0.875rem' }}>
      {items.map((item, i) => (
        <div key={i} style={{ marginBottom: i < items.length - 1 ? '6px' : 0 }}>
          * {item}
        </div>
      ))}
    </div>
  </div>
);

const MethodologyPage = () => {
  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '40px' }}>
        <h1 style={{
          color: colors.text.primary,
          fontSize: '2rem',
          fontWeight: 700,
          marginBottom: '12px'
        }}>
          Index Methodology
        </h1>
        <p style={{ color: colors.text.muted, fontSize: '1rem' }}>
          Complete documentation of how the Pokemon Market Indexes are constructed and maintained.
        </p>
      </div>

      <Section title="Overview">
        <p>
          The Pokemon Market Indexes are a family of transparent market indicators designed to track
          the Pokemon TCG collectibles market. They focus exclusively on raw (non-graded) cards and
          provide reliable benchmarks for collectors, investors, and market analysts.
        </p>
      </Section>

      <Section title="Index Family">
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '20px'
        }}>
          {[
            { code: 'RARE_100', name: 'Rare Cards Top 100', desc: 'Top 100 cards by composite score.' },
            { code: 'RARE_500', name: 'Rare Cards Top 500', desc: 'Top 500 cards by composite score.' },
            { code: 'RARE_ALL', name: 'Rare Cards All Liquid', desc: 'All cards meeting strict liquidity requirements.' }
          ].map(({ code, name, desc }) => (
            <div key={code} style={{
              background: colors.bg.card,
              border: `1px solid ${colors.chart[code]}40`,
              borderRadius: '12px',
              padding: '20px'
            }}>
              <IndexBadge code={code} />
              <h4 style={{ color: colors.text.primary, margin: '12px 0 8px' }}>{name}</h4>
              <p style={{ fontSize: '0.85rem', margin: 0 }}>{desc}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Eligibility Criteria">
        <InfoBox title="Universe" items={[
          'Raw Pokemon cards only (no graded items)',
          'Rarity >= Rare (excludes Commons and Uncommons)',
          'Near Mint condition'
        ]} />
        <InfoBox title="Maturity Requirements" items={[
          '>=60 days since set release date',
          '2 consecutive months of eligibility confirmation',
          'Anti-novelty filter to prevent hype distortion'
        ]} />
        <InfoBox title="Liquidity Thresholds" items={[
          'RARE_100: >=10 sales/month (5 for existing constituents)',
          'RARE_500: >=20 sales/month (10 for existing constituents)',
          'RARE_ALL: >=20 sales/month (strict, no tolerance)'
        ]} />
      </Section>

      <Section title="Scoring & Selection">
        <p style={{ marginBottom: '16px' }}>
          Cards are ranked using a composite score that balances price and market activity:
        </p>
        <div style={{
          background: colors.bg.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '8px',
          padding: '20px',
          fontFamily: "'JetBrains Mono', monospace",
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          <span style={{ color: colors.accent.gold }}>Score</span>
          <span style={{ color: colors.text.muted }}> = </span>
          <span style={{ color: colors.text.primary }}>Composite Price</span>
          <span style={{ color: colors.text.muted }}> x </span>
          <span style={{ color: colors.text.primary }}>Liquidity Score</span>
        </div>
      </Section>

      <Section title="Liquidity Estimation">
        <p style={{ marginBottom: '16px' }}>
          Multi-signal approach to estimate liquidity:
        </p>
        {[
          { pct: '50%', color: colors.accent.blue, name: 'Market Activity (Churn)', desc: 'Listing disappearances interpreted as implicit sales' },
          { pct: '30%', color: colors.accent.purple, name: 'Market Presence (Listings)', desc: 'Number and continuity of active listings' },
          { pct: '20%', color: colors.accent.gold, name: 'Price Signal Quality', desc: 'Frequency of price updates and relative stability' }
        ].map(({ pct, color, name, desc }) => (
          <div key={name} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            background: colors.bg.tertiary,
            padding: '14px 18px',
            borderRadius: '8px',
            marginBottom: '12px'
          }}>
            <div style={{
              width: '40px',
              height: '40px',
              background: color + '20',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: color,
              fontWeight: 700
            }}>
              {pct}
            </div>
            <div>
              <div style={{ color: colors.text.primary, fontWeight: 600, marginBottom: '2px' }}>{name}</div>
              <div style={{ fontSize: '0.8rem' }}>{desc}</div>
            </div>
          </div>
        ))}
      </Section>

      <Section title="Disclaimers">
        <div style={{
          background: `${colors.accent.gold}10`,
          border: `1px solid ${colors.accent.gold}30`,
          borderRadius: '8px',
          padding: '20px'
        }}>
          <p style={{ margin: '0 0 12px 0' }}>
            <strong>For Informational Purposes Only:</strong> The Pokemon Market Indexes do not constitute investment advice.
          </p>
          <p style={{ margin: '0 0 12px 0' }}>
            <strong>No Guarantees:</strong> Past performance is not indicative of future results.
          </p>
          <p style={{ margin: 0 }}>
            <strong>Estimated Liquidity:</strong> Liquidity figures are estimates, not exact transaction volumes.
          </p>
        </div>
      </Section>

      <div style={{
        textAlign: 'center',
        padding: '32px',
        borderTop: `1px solid ${colors.border}`,
        marginTop: '40px'
      }}>
        <p style={{ color: colors.text.muted, fontSize: '0.85rem', margin: 0 }}>
          Methodology Version 1.0 - Last Updated: January 2026
        </p>
      </div>
    </div>
  );
};

export default MethodologyPage;
