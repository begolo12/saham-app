import { memo } from 'react';
import SignalStats from './SignalStats';

/**
 * MarketSummary — IHSG card with index price, change %, and 52-week range bar.
 *
 * Props:
 *   @param {object}   marketSummary — { name, price, change_percent, low_52w, high_52w, stale? }
 *   @param {{ beli: number, jual: number, tahan: number }} signalStats
 */
function MarketSummary({ marketSummary = {}, signalStats }) {
  const ihsgPrice = Number(marketSummary.price || 0);
  const ihsgChangePct = Number(marketSummary.change_percent || 0);
  const ihsgIsPositive = ihsgChangePct > 0;
  const ihsgIsNegative = ihsgChangePct < 0;
  const ihsgColor = ihsgIsPositive ? '#34C759' : ihsgIsNegative ? '#FF3B30' : '#8E8E93';
  const ihsgLow = Number(marketSummary.low_52w || 0);
  const ihsgHigh = Number(marketSummary.high_52w || 0);
  const ihsgRangePct = ihsgHigh > ihsgLow && ihsgPrice > 0
    ? Math.max(0, Math.min(100, ((ihsgPrice - ihsgLow) / (ihsgHigh - ihsgLow)) * 100))
    : 50;

  return (
    <div className="market-summary">
      <div className="market-summary-header">
        <h3>Ringkasan Pasar</h3>
        {signalStats && <SignalStats stats={signalStats} />}
      </div>
      <div className="market-summary-body">
        <div className="market-index">
          <span className="market-index-name">{marketSummary.name || 'IHSG'}</span>
          <span className="market-index-price">
            {ihsgPrice ? ihsgPrice.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Data tertunda'}
          </span>
          <span className="market-index-change" style={{ color: ihsgColor }}>
            {ihsgIsPositive ? '+' : ''}{ihsgChangePct.toFixed(2)}%
            {marketSummary.stale ? ' · tertunda' : ''}
          </span>
        </div>
        <div className="market-range">
          <p className="market-range-label">Range 52 Minggu</p>
          <div className="market-range-bar">
            <div className="market-range-fill" style={{ width: `${ihsgRangePct}%` }} />
          </div>
          <div className="market-range-values">
            <span>{marketSummary.low_52w?.toLocaleString('id-ID', { maximumFractionDigits: 2 })}</span>
            <span>{marketSummary.high_52w?.toLocaleString('id-ID', { maximumFractionDigits: 2 })}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default memo(MarketSummary);
