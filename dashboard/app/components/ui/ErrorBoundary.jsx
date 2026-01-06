'use client';

import { Component } from 'react';
import { colors } from '../../lib/theme';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '32px',
          background: colors.bg.card,
          borderRadius: '12px',
          border: `1px solid ${colors.accent.red}`,
          textAlign: 'center',
          margin: '16px 0'
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '16px' }}>Something went wrong</div>
          <p style={{ color: colors.text.secondary, marginBottom: '16px' }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              background: colors.accent.gold,
              color: colors.bg.primary,
              border: 'none',
              padding: '8px 16px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 500
            }}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
