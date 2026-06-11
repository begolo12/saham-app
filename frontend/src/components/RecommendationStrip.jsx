import { memo } from 'react';
import SignalBadge from './SignalBadge';

/**
 * RecommendationStrip — horizontal scrollable strip of top signal pills.
 *
 * Props:
 *   @param {Array}    recommendedStocks — array of { symbol, signal, signal_strength, ... }
 *   @param {Function} onSelectStock     — (stock) => void, opens stock detail
 *   @param {Function} onShowMore        — () => void, opens recommendation modal
 */
function RecommendationStrip({ recommendedStocks = [], onSelectStock, onShowMore }) {
  if (recommendedStocks.length === 0) return null;

  return (
    <div className="recommendation-strip">
      <div className="recommendation-strip-head">
        <span>Sinyal Terkuat Hari Ini</span>
        <button onClick={onShowMore}>See More</button>
      </div>
      <div className="recommendation-strip-list">
        {recommendedStocks.slice(0, 5).map(stock => (
          <button key={stock.symbol} className="recommendation-pill" onClick={() => onSelectStock?.(stock)}>
            <b>{stock.symbol}</b>
            <SignalBadge signal={stock.signal} strength={stock.signal_strength} />
          </button>
        ))}
      </div>
    </div>
  );
}

export default memo(RecommendationStrip);
