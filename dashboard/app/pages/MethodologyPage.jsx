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

const FormulaBox = ({ label, formula }) => (
  <div style={{
    background: colors.bg.card,
    border: `1px solid ${colors.border}`,
    borderRadius: '8px',
    padding: '20px',
    fontFamily: "'JetBrains Mono', monospace",
    textAlign: 'center',
    marginBottom: '20px'
  }}>
    <span style={{ color: colors.accent.gold }}>{label}</span>
    <span style={{ color: colors.text.muted }}> = </span>
    <span style={{ color: colors.text.primary }}>{formula}</span>
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
          Pokemon Market Indexes track the price performance of rare Pokemon Trading Card Game (TCG) cards.
          Like stock market indexes (S&P 500, NASDAQ), they provide a single number that represents how the
          overall market is performing.
        </p>
        <p style={{ marginTop: '12px' }}>
          <strong>Base Value:</strong> 100 (set on December 6th, 2025)
        </p>
        <p style={{ marginTop: '8px' }}>
          If the index reads <strong>105</strong>, the market has gained 5% since inception.
          If it reads <strong>95</strong>, the market has declined 5%.
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
            { code: 'RARE_100', name: 'RARE 100', desc: 'Top 100 most valuable and liquid cards (blue-chip).' },
            { code: 'RARE_500', name: 'RARE 500', desc: 'Top 500 cards for broader market view.' },
            { code: 'RARE_ALL', name: 'RARE ALL', desc: 'All eligible cards meeting liquidity requirements.' }
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
          'Price between $0.10 and $100,000',
          'Set maturity: 30+ days since release'
        ]} />
        <InfoBox title="Eligible Rarities" items={[
          'Standard Rares: Rare, Holo Rare, Shiny Holo Rare',
          'Ultra/Secret: Ultra Rare, Secret Rare, Hyper Rare',
          'Illustration: Illustration Rare, Special Illustration Rare, Double Rare',
          'Special: Amazing Rare, Radiant Rare, ACE SPEC Rare, Prism Rare'
        ]} />
      </Section>

      <Section title="Liquidity Requirements">
        <p style={{ marginBottom: '16px' }}>
          A card that rarely sells can have a misleading price. We need cards that trade regularly
          to get reliable price signals. We use a multi-factor liquidity score (0 to 1).
        </p>

        {[
          { pct: '50%', color: colors.accent.blue, name: 'Volume (Sales Activity)', desc: 'Weighted sales volume over the last 7 days with decay' },
          { pct: '30%', color: colors.accent.purple, name: 'Listings (Market Presence)', desc: 'Number of available listings by condition' },
          { pct: '20%', color: colors.accent.gold, name: 'Consistency (Trading Regularity)', desc: 'Days with at least one sale / total days' }
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

        <InfoBox title="30-Day Trading Activity (Method D)" items={[
          'Average volume >= 0.5 sales/day (about 15 sales per month)',
          'Trading days >= 10 days out of 30 with at least one sale',
          'Both criteria must be met for index eligibility',
          'No minimum liquidity threshold - ranking score does the selection'
        ]} />
      </Section>

      <Section title="Scoring & Selection">
        <p style={{ marginBottom: '16px' }}>
          Cards are ranked using a composite score that balances price and liquidity:
        </p>
        <FormulaBox label="Ranking Score" formula="Price x Liquidity Score" />
        <p>
          This formula favors cards that are both valuable AND liquid. A $1,000 card with 0.8 liquidity
          (score: 800) ranks higher than a $2,000 card with 0.3 liquidity (score: 600).
        </p>
      </Section>

      <Section title="Weighting Method">
        <p style={{ marginBottom: '16px' }}>
          Each card's weight in the index is proportional to its price times liquidity:
        </p>
        <FormulaBox label="Weight" formula="(Price x Liquidity) / Sum(Price x Liquidity)" />
        <p>
          This liquidity-adjusted approach reduces the impact of illiquid cards that could swing
          the index based on a single noisy sale.
        </p>
      </Section>

      <Section title="Index Calculation">
        <p style={{ marginBottom: '16px' }}>
          We use the <strong>Laspeyres Chain-Linking Method</strong>, the same approach used by major
          financial indexes. It answers: "How much would yesterday's portfolio be worth at today's prices?"
        </p>
        <FormulaBox label="Index Today" formula="Index Yesterday x (Weighted Prices Today / Weighted Prices Yesterday)" />
        <p>
          We require at least 70% of constituents to have valid prices for the calculation.
          This prevents a few missing cards from distorting the index.
        </p>
      </Section>

      <Section title="Data Schedule (J-2 Strategy)">
        <p style={{ marginBottom: '16px' }}>
          We use a <strong>J-2 strategy</strong>: prices and volumes are fetched for 2 days ago
          to ensure complete sales data.
        </p>
        <InfoBox title="Why J-2?" items={[
          'TCGplayer consolidates sales at end of US day (~08:00 UTC next day)',
          'Using J-2 gives 24-48 hours for volume data to fully consolidate',
          'This guarantees accurate sales volume for liquidity calculations'
        ]} />
        <p style={{ marginTop: '16px' }}>
          <strong>Example:</strong> On January 7th, the index is calculated using January 5th prices.
        </p>
        <div style={{
          background: colors.bg.tertiary,
          border: `1px solid ${colors.border}`,
          borderRadius: '8px',
          padding: '16px',
          marginTop: '16px',
          fontSize: '0.875rem'
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '8px' }}>
            <div style={{ fontWeight: 600, color: colors.text.primary }}>Operation</div>
            <div style={{ fontWeight: 600, color: colors.text.primary }}>Time (UTC)</div>
            <div style={{ fontWeight: 600, color: colors.text.primary }}>Description</div>

            <div>Price fetch</div>
            <div>12:00</div>
            <div>Fetch J-2 prices and sales volume</div>

            <div>Index calculation</div>
            <div>13:00</div>
            <div>Calculate daily index values</div>

            <div>Rebalancing</div>
            <div>3rd of month</div>
            <div>Monthly constituent refresh</div>
          </div>
        </div>
      </Section>

      <Section title="Rebalancing">
        <InfoBox title="Monthly Rebalancing" items={[
          'Occurs on the 3rd of each month',
          'Uses 1st of month prices (available on 3rd with J-2)',
          'Weights are fixed for the entire month'
        ]} />
        <p style={{ marginTop: '12px' }}>
          <strong>Why the 3rd?</strong> With J-2 strategy, on the 3rd we have prices from the 1st,
          allowing us to rebalance with the new month's first prices.
        </p>
      </Section>

      <Section title="Data Sources">
        <div style={{
          background: colors.bg.tertiary,
          border: `1px solid ${colors.border}`,
          borderRadius: '8px',
          padding: '16px',
          fontSize: '0.875rem'
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: '8px' }}>
            <div style={{ fontWeight: 600, color: colors.text.primary }}>Data</div>
            <div style={{ fontWeight: 600, color: colors.text.primary }}>Source</div>
            <div style={{ fontWeight: 600, color: colors.text.primary }}>Frequency</div>

            <div>Card prices</div>
            <div>TCGplayer (via PokemonPriceTracker API)</div>
            <div>Daily</div>

            <div>Sales volume</div>
            <div>TCGplayer (via PokemonPriceTracker API)</div>
            <div>Daily</div>

            <div>Card metadata</div>
            <div>TCGdex API</div>
            <div>On-demand</div>
          </div>
        </div>
        <p style={{ marginTop: '16px' }}>
          <strong>Reference Price:</strong> We use Near Mint (NM) price as the standard condition
          for collectible cards.
        </p>
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
          <p style={{ margin: '0 0 12px 0' }}>
            <strong>US Market Only:</strong> Currently uses TCGplayer data (US). Cardmarket (EU) planned for future.
          </p>
          <p style={{ margin: 0 }}>
            <strong>Daily Updates:</strong> Not real-time; prices are daily closing values from 2 days prior.
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
          Methodology Version 2.1 - Last Updated: January 2026
        </p>
        <p style={{ color: colors.text.muted, fontSize: '0.75rem', marginTop: '8px' }}>
          Inception Date: December 6th, 2025 | Base Value: 100
        </p>
      </div>
    </div>
  );
};

export default MethodologyPage;
