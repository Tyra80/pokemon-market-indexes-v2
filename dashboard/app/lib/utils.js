// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

export const formatNumber = (num, decimals = 2) => {
  if (num === null || num === undefined || isNaN(num)) return '—';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  }).format(num);
};

export const formatCurrency = (num) => {
  if (num === null || num === undefined || isNaN(num)) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(num);
};

export const getCardImageUrl = (tcgplayerId, size = 400) => {
  if (!tcgplayerId) return null;
  return `https://tcgplayer-cdn.tcgplayer.com/product/${tcgplayerId}_in_${size}x${size}.jpg`;
};
