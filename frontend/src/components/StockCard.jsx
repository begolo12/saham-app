import { useState, useEffect, useRef, memo } from 'react';
import SignalBadge from './SignalBadge';
import { lightHaptic } from '../utils/haptic';
import { LIQUIDITY_THRESHOLD } from '../constants';

const SECTOR_COLORS = {
  finance: { bg: 'rgba(52,199,89,0.12)', text: '#34C759' },
  technology: { bg: 'rgba(0,122,255,0.12)', text: '#007AFF' },
  energy: { bg: 'rgba(255,149,0,0.12)', text: '#FF9500' },
  consumer: { bg: 'rgba(255,59,48,0.12)', text: '#FF3B30' },
  infrastructure: { bg: 'rgba(175,82,222,0.12)', text: '#AF52DE' },
  property: { bg: 'rgba(255,214,10,0.12)', text: '#FFD60A' },
  basic: { bg: 'rgba(52,199,89,0.12)', text: '#34C759' },
  mining: { bg: 'rgba(255,149,0,0.12)', text: '#FF9500' },
  agriculture: { bg: 'rgba(52,199,89,0.12)', text: '#30D158' },
  misc: { bg: 'rgba(255,255,255,0.05)', text: '#bbb' },
};

const ICON_GRADIENTS = [
  ['#007AFF', '#5856D6'],
  ['#34C759', '#30D158'],
  ['#FF3B30', '#FF453A'],
  ['#FF9500', '#FF9F0A'],
  ['#AF52DE', '#5E5CE6'],
  ['#FFD60A', '#FFCC00'],
  ['#30B0C7', '#32D74B'],
  ['#FF375F', '#FF6482'],
  ['#5E5CE6', '#BF5AF2'],
  ['#00C7BE', '#30D158'],
];

function getSectorStyle(sector) {
  if (!sector) return SECTOR_COLORS.misc;
  const key = sector.toLowerCase();
  for (const [k, v] of Object.entries(SECTOR_COLORS)) {
    if (key.includes(k)) return v;
  }
  return SECTOR_COLORS.misc;
}

function getIconGradient(symbol) {
  let hash = 0;
  for (let i = 0; i < (symbol || '').length; i++) hash = ((hash << 5) - hash) + symbol.charCodeAt(i);
  return ICON_GRADIENTS[Math.abs(hash) % ICON_GRADIENTS.length];
}

function fmtPrice(price) {
  if (price == null) return '-';
  return 'Rp ' + Number(price).toLocaleString('id-ID', { minimumFractionDigits: 0 });
}

function StockCard({ stock, onClick, watchlist, onToggleWatchlist, index = 0, gridView = false }) {
  const changeNum = stock.change_percent ?? stock.change ?? 0;
  const isPositive = changeNum >= 0;
  const price = stock.price ?? 0;
  const signal = stock.signal || 'HOLD';
  const strength = stock.signal_strength ?? stock.strength ?? 50;
  const sector = stock.sector || '';
  const sectorStyle = getSectorStyle(sector);
  const [grad1, grad2] = getIconGradient(stock.symbol || '');
  const isWatched = watchlist?.includes(stock.symbol);

  // Price flash
  const [flashClass, setFlash] = useState('');
  const prevPrice = useRef(price);
  useEffect(() => {
    if (prevPrice.current !== price && prevPrice.current !== 0) {
      setFlash(price > prevPrice.current ? 'flash-green' : 'flash-red');
      const t = setTimeout(() => setFlash(''), 700);
      prevPrice.current = price;
      return () => clearTimeout(t);
    }
    prevPrice.current = price;
  }, [price]);

  const delay = Math.min(index * 0.04, 0.6);

  return (
    <div
      className={`stock-card${gridView ? ' grid-view-item' : ''}`}
      onClick={() => onClick?.(stock)}
      style={{ animationDelay: `${delay}s` }}
    >
      {gridView ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div className="stock-icon" style={{ background: `linear-gradient(135deg, ${grad1}, ${grad2})`, width: 34, height: 34, fontSize: 14 }}>
              {stock.symbol?.[0] || '?'}
            </div>
            <div className="stock-info" style={{ flex: 1 }}>
              <span className="stock-symbol" style={{ fontSize: 14 }}>{stock.symbol}</span>
              {sector && (
                <span className="sector-badge" style={{ background: sectorStyle.bg, color: sectorStyle.text }}>
                  {sector}
                </span>
              )}
            </div>
          </div>
          <span className={`stock-price ${flashClass}`} style={{ fontSize: 18 }}>
            {fmtPrice(price)}
          </span>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="stock-change" style={{ color: isPositive ? '#34C759' : '#FF3B30', fontSize: 13 }}>
              {isPositive ? '+' : ''}{changeNum.toFixed(2)}%
            </span>
             {stock.volume != null && (
               <span style={{ fontSize: 10, color: '#636366', marginTop: 2 }}>
                 {stock.volume < LIQUIDITY_THRESHOLD ? '⚠ Vol: ' : 'Vol: '}
                 {Number(stock.volume).toLocaleString('id-ID')}
               </span>
             )}
            <button
              className={`star-btn${isWatched ? ' active' : ''}`}
              onClick={(e) => { e.stopPropagation(); lightHaptic(); onToggleWatchlist?.(stock.symbol); }}
              style={{ fontSize: 16 }}
            >
              {isWatched ? '★' : '☆'}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="stock-card-top">
            <div className="stock-card-left">
              <div className="stock-icon" style={{ background: `linear-gradient(135deg, ${grad1}, ${grad2})` }}>
                {stock.symbol?.[0] || '?'}
              </div>
              <div className="stock-info">
                <span className="stock-symbol">{stock.symbol}</span>
                {stock.name && stock.name !== stock.symbol && (
                  <span className="stock-name">{stock.name}</span>
                )}
                {sector && (
                  <span className="sector-badge" style={{ background: sectorStyle.bg, color: sectorStyle.text }}>
                    {sector}
                  </span>
                )}
              </div>
            </div>
            <div className="stock-card-right">
              <span className={`stock-price ${flashClass}`}>{fmtPrice(price)}</span>
              <span className="stock-change" style={{ color: isPositive ? '#34C759' : '#FF3B30' }}>
                {isPositive ? '+' : ''}{changeNum.toFixed(2)}%
              </span>
            </div>
          </div>
          <div className="stock-card-bottom">
            <button
              className={`star-btn${isWatched ? ' active' : ''}`}
              onClick={(e) => { e.stopPropagation(); lightHaptic(); onToggleWatchlist?.(stock.symbol); }}
            >
              {isWatched ? '★' : '☆'}
            </button>
             <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
               {stock.volume != null && (
                 <span style={{ fontSize: 10, color: '#636366' }}>
                   {stock.volume < LIQUIDITY_THRESHOLD ? '⚠ ' : ''}Vol: {Number(stock.volume).toLocaleString('id-ID')}
                 </span>
               )}
               {stock.potential_score != null && (
                 <span style={{ fontSize: 10, color: '#8E8E93' }}>
                   Potensi: {Math.round(stock.potential_score)}
                 </span>
               )}
             </div>
            <SignalBadge signal={signal} strength={strength} />
          </div>
        </>
      )}
    </div>
  );
}

export default memo(StockCard);
