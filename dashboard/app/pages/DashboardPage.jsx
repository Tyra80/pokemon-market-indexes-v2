'use client';

import { useState } from 'react';
import IndexCard from '../components/IndexCard';
import MainChart from '../components/MainChart';
import ConstituentsTable from '../components/ConstituentsTable';
import { ErrorBoundary, SkeletonCard, SkeletonChart, SkeletonTable } from '../components/ui';

const INDEX_CONFIGS = [
  { code: 'RARE_100', name: 'Rare Cards Top 100' },
  { code: 'RARE_500', name: 'Rare Cards Top 500' },
  { code: 'RARE_5000', name: 'Rare Cards Top 5000' }
];

const DashboardPage = ({
  indexData,
  latestValues,
  constituents,
  onCardClick,
  selectedCard,
  loading
}) => {
  const [selectedIndex, setSelectedIndex] = useState('RARE_100');

  if (loading) {
    return (
      <>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '20px',
          marginBottom: '32px'
        }}>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
        <div style={{ marginBottom: '32px' }}>
          <SkeletonChart />
        </div>
        <SkeletonTable rows={10} />
      </>
    );
  }

  return (
    <ErrorBoundary>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '20px',
        marginBottom: '32px'
      }}>
        {INDEX_CONFIGS.map(({ code, name }) => (
          <IndexCard
            key={code}
            code={code}
            name={name}
            data={indexData[code] || []}
            latestData={latestValues?.[code]}
            isSelected={selectedIndex === code}
            onClick={() => setSelectedIndex(code)}
          />
        ))}
      </div>

      <div style={{ marginBottom: '32px' }}>
        <MainChart
          data={indexData[selectedIndex] || []}
          indexCode={selectedIndex}
        />
      </div>

      <ConstituentsTable
        constituents={constituents[selectedIndex]}
        onCardClick={onCardClick}
        selectedCard={selectedCard}
        limit={20}
        loading={loading}
      />
    </ErrorBoundary>
  );
};

export default DashboardPage;
