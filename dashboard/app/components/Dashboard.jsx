'use client';

import { useState, useEffect } from 'react';
import { colors } from '../lib/theme';
import { MOCK_INDEX_DATA, MOCK_CONSTITUENTS, generateCardPriceHistoryMock } from '../lib/mockData';
import { getAllIndexHistory, getLatestIndexValues, getConstituents, getAllEligibleCards, getCardPriceHistory } from '../lib/api';
import { isSupabaseConfigured } from '../lib/supabase';

import Header from './Header';
import CardDetailPanel from './CardDetailPanel';
import { DashboardPage, AllCardsPage, MethodologyPage } from '../pages';

export default function PokemonMarketDashboard() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedCard, setSelectedCard] = useState(null);
  const [cardPriceHistory, setCardPriceHistory] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const [indexData, setIndexData] = useState(MOCK_INDEX_DATA);
  const [latestValues, setLatestValues] = useState(null);
  const [constituents, setConstituents] = useState(MOCK_CONSTITUENTS);
  const [allCards, setAllCards] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }));

  useEffect(() => {
    async function fetchData() {
      setLoading(true);

      if (!isSupabaseConfigured()) {
        console.log('Supabase not configured, using mock data');
        setLoading(false);
        return;
      }

      try {
        const indexHistory = await getAllIndexHistory();
        if (indexHistory && Object.values(indexHistory).some(arr => arr.length > 0)) {
          setIndexData(indexHistory);
          setIsLive(true);
        }

        const latest = await getLatestIndexValues();
        if (latest) {
          setLatestValues(latest);

          const dates = Object.values(latest).map(v => v?.value_date).filter(Boolean);
          if (dates.length > 0) {
            const mostRecent = dates.sort().reverse()[0];
            setLastUpdate(new Date(mostRecent).toLocaleDateString('en-US', {
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            }));
          }
        }

        const [rare100, rare500, rare5000] = await Promise.all([
          getConstituents('RARE_100'),
          getConstituents('RARE_500'),
          getConstituents('RARE_5000')
        ]);

        if (rare100 || rare500 || rare5000) {
          setConstituents({
            RARE_100: rare100 || MOCK_CONSTITUENTS.RARE_100,
            RARE_500: rare500 || MOCK_CONSTITUENTS.RARE_500,
            RARE_5000: rare5000 || MOCK_CONSTITUENTS.RARE_5000
          });
        }

        const cards = await getAllEligibleCards();
        if (cards) {
          setAllCards(cards);
        }

      } catch (error) {
        console.error('Error fetching data:', error);
      }

      setLoading(false);
    }

    fetchData();
  }, []);

  useEffect(() => {
    async function fetchCardHistory() {
      if (!selectedCard) {
        setCardPriceHistory(null);
        return;
      }

      setLoadingHistory(true);

      if (isSupabaseConfigured()) {
        const history = await getCardPriceHistory(selectedCard.id);
        if (history && history.length > 0) {
          setCardPriceHistory(history);
        } else {
          setCardPriceHistory(generateCardPriceHistoryMock(selectedCard.price || 50));
        }
      } else {
        setCardPriceHistory(generateCardPriceHistoryMock(selectedCard.price || 50));
      }

      setLoadingHistory(false);
    }

    fetchCardHistory();
  }, [selectedCard]);

  const handleCardClick = (card) => {
    setSelectedCard(card);
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'methodology':
        return <MethodologyPage />;
      case 'cards':
        return (
          <AllCardsPage
            allCards={allCards || MOCK_CONSTITUENTS.RARE_5000}
            onCardClick={handleCardClick}
            selectedCard={selectedCard}
            loading={loading}
          />
        );
      default:
        return (
          <DashboardPage
            indexData={indexData}
            latestValues={latestValues}
            constituents={constituents}
            onCardClick={handleCardClick}
            selectedCard={selectedCard}
            loading={loading}
          />
        );
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: colors.bg.primary,
      color: colors.text.primary,
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
    }}>
      <div style={{
        maxWidth: '1400px',
        margin: '0 auto',
        padding: '0 32px'
      }}>
        <Header
          currentPage={currentPage}
          onNavigate={setCurrentPage}
          isLive={isLive}
          lastUpdate={lastUpdate}
        />

        {renderPage()}

        <footer style={{
          padding: '24px 0',
          borderTop: `1px solid ${colors.border}`,
          textAlign: 'center',
          marginTop: '48px',
          marginBottom: '32px'
        }}>
          <p style={{ color: colors.text.muted, fontSize: '0.75rem', margin: 0 }}>
            Pokemon Market Indexes - Data for informational purposes only - Not investment advice
          </p>
        </footer>
      </div>

      {selectedCard && (
        <>
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.5)',
              zIndex: 999
            }}
            onClick={() => setSelectedCard(null)}
          />
          <CardDetailPanel
            card={selectedCard}
            onClose={() => setSelectedCard(null)}
            priceHistory={cardPriceHistory}
            loadingHistory={loadingHistory}
          />
        </>
      )}
    </div>
  );
}
