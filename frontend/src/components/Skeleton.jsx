import { memo } from 'react';

/**
 * Skeleton — iOS 18 redacted-style loading placeholder.
 * Variants: card, detail, list, chart, market-summary, learning-stat.
 */
function Skeleton({ variant = 'card', count = 1 }) {
  if (variant === 'card') {
    return (
      <div className="skeleton-list">
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="skeleton-card">
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <div className="skeleton-line" style={{ width: 38, height: 38, borderRadius: 10 }} />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="skeleton-line w-30 h-md" />
                <div className="skeleton-line w-50 h-sm" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === 'detail') {
    return (
      <div className="skeleton-detail">
        <div className="skeleton-line w-40 h-xl" />
        <div className="skeleton-line w-25 h-md" />
        <div className="skeleton-line w-80 h-lg" />
        <div className="skeleton-chart" />
        <div className="skeleton-line w-60 h-md" />
        <div className="skeleton-line w-50 h-md" />
        <div className="skeleton-line w-70 h-sm" />
      </div>
    );
  }

  if (variant === 'market-summary') {
    return (
      <div className="skeleton-market-summary">
        <div className="skeleton-market-row">
          <div className="skeleton-line w-30 h-md" />
          <div className="skeleton-line w-20 h-md" />
        </div>
        <div className="skeleton-market-row">
          <div className="skeleton-line w-40 h-lg" />
          <div className="skeleton-line w-15 h-sm" />
        </div>
        <div className="skeleton-line w-full h-sm" />
        <div className="skeleton-market-row">
          <div className="skeleton-line w-15 h-sm" />
          <div className="skeleton-line w-15 h-sm" />
        </div>
      </div>
    );
  }

  if (variant === 'chart') {
    return (
      <div style={{ padding: '0 16px' }}>
        <div className="skeleton-chart" />
      </div>
    );
  }

  if (variant === 'learning-stat') {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, padding: '0 16px' }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton-learning-stat">
            <div className="skeleton-line w-40 h-lg" style={{ margin: '0 auto 6px' }} />
            <div className="skeleton-line w-60 h-sm" style={{ margin: '0 auto' }} />
          </div>
        ))}
      </div>
    );
  }

  // skeleton-list (default fallback)
  return (
    <div className="skeleton-list">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton-line w-40 h-md" />
          <div className="skeleton-line w-80 h-sm" />
          <div className="skeleton-line w-25 h-sm" />
        </div>
      ))}
    </div>
  );
}

export default memo(Skeleton);
