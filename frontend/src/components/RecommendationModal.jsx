import { memo } from 'react';
import SignalBadge from './SignalBadge';

/**
 * RecommendationModal — full-screen modal listing all BUY/SELL recommendations.
 *
 * Props:
 *   @param {boolean}  open               — modal visibility
 *   @param {Function} onClose            — () => void
 *   @param {Array}    recommendedStocks  — array of { symbol, name, sector, signal, signal_strength }
 *   @param {Function} onSelectStock      — (stock) => void, opens stock detail and closes modal
 */
function RecommendationModal({ open, onClose, recommendedStocks = [], onSelectStock }) {
  if (!open) return null;

  return (
    <div className="recommendation-modal-backdrop" onClick={onClose}>
      <div className="recommendation-modal" onClick={e => e.stopPropagation()}>
        <div className="recommendation-modal-header">
          <div>
            <b>Semua Sinyal</b>
            <span>{recommendedStocks.length} rekomendasi aktif</span>
          </div>
          <button onClick={onClose}>Tutup</button>
        </div>
        <div className="recommendation-modal-list">
          {recommendedStocks.map(stock => (
            <button
              key={stock.symbol}
              className="recommendation-modal-item"
              onClick={() => {
                onClose();
                onSelectStock?.(stock);
              }}
            >
              <div>
                <b>{stock.symbol}</b>
                <span>{stock.name || stock.sector}</span>
              </div>
              <SignalBadge signal={stock.signal} strength={stock.signal_strength} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default memo(RecommendationModal);
