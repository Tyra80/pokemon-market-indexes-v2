'use client';

import React from 'react';
import { colors } from '../../lib/theme';
import { getCardImageUrl } from '../../lib/utils';

const CardImage = ({ tcgplayerId, name, size = 'small' }) => {
  const [imageError, setImageError] = React.useState(false);
  const [imageLoaded, setImageLoaded] = React.useState(false);

  const sizeStyles = {
    small: { width: '36px', height: '50px' },
    medium: { width: '60px', height: '84px' },
    large: { width: '100%', height: '320px' }
  };

  const objectFit = size === 'large' ? 'contain' : 'cover';
  const imageUrl = getCardImageUrl(tcgplayerId, size === 'large' ? 800 : 400);

  if (!tcgplayerId || imageError) {
    return (
      <div style={{
        ...sizeStyles[size],
        background: `linear-gradient(135deg, ${colors.accent.gold}30, ${colors.accent.purple}30)`,
        borderRadius: size === 'large' ? '12px' : '4px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size === 'large' ? '2rem' : '0.8rem',
        color: colors.text.muted,
        border: `1px solid ${colors.border}`
      }}>
        🃏
      </div>
    );
  }

  return (
    <div style={{
      ...sizeStyles[size],
      position: 'relative',
      borderRadius: size === 'large' ? '12px' : '4px',
      overflow: 'hidden',
      background: colors.bg.tertiary
    }}>
      {!imageLoaded && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '0.6rem',
          color: colors.text.muted
        }}>
          ...
        </div>
      )}
      <img
        src={imageUrl}
        alt={name || 'Pokemon Card'}
        loading="lazy"
        style={{
          width: '100%',
          height: '100%',
          objectFit: objectFit,
          opacity: imageLoaded ? 1 : 0,
          transition: 'opacity 0.3s'
        }}
        onLoad={() => setImageLoaded(true)}
        onError={() => setImageError(true)}
      />
    </div>
  );
};

export default CardImage;
