import { fmtPrice } from '../utils';

/**
 * SignalDashboard — full signal statistics panel with BUY/SELL/NEUTRAL
 * counts and the top 5 strongest signal cards.
 *
 * Renders when the active tab doesn't match any specific panel (fallback).
 *
 * Props:
 *   @param {Array}    allStocks     — full list of stocks with signal data
 *   @param {{ beli: number, jual: number, tahan: number }} signalStats
 *   @param {Function} onSelectStock — (stock) => void, opens stock detail
 */
export default function SignalDashboard({ allStocks = [], signalStats, onSelectStock }) {
  const topSignals = allStocks
    .filter(s => s.signal === 'BUY' || s.signal === 'SELL')
    .sort((a, b) => (b.signal_strength || 0) - (a.signal_strength || 0))
    .slice(0, 5);

  return (
    <div style={{ padding: '0 16px 16px' }}>
      <p className="section-label" style={{ marginBottom: 12 }}>
        {allStocks.length} Saham Tercatat
      </p>
      <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
        <div className="market-summary-header">
          <h3>Statistik Sinyal</h3>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-around', padding: '8px 0' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: '#34C759' }}>{signalStats?.beli ?? 0}</div>
            <div style={{ fontSize: 11, color: '#8E8E93', fontWeight: 500, marginTop: 2 }}>BELI</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: '#FF3B30' }}>{signalStats?.jual ?? 0}</div>
            <div style={{ fontSize: 11, color: '#8E8E93', fontWeight: 500, marginTop: 2 }}>JUAL</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: '#8E8E93' }}>{signalStats?.tahan ?? 0}</div>
            <div style={{ fontSize: 11, color: '#8E8E93', fontWeight: 500, marginTop: 2 }}>TAHAN</div>
          </div>
        </div>
      </div>

      <p className="section-label">Sinyal Terkuat</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {topSignals.map((stock, i) => {
          const change = stock.change_percent ?? 0;
          const isPos = change >= 0;
          const isBuy = stock.signal === 'BUY';
          return (
            <div
              key={stock.symbol}
              className="signal-card"
              onClick={() => onSelectStock?.(stock)}
              style={{ animationDelay: `${i * 0.06}s`, cursor: 'pointer' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 34, height: 34, borderRadius: 10,
                    background: `linear-gradient(135deg, ${isBuy ? '#34C759' : '#FF3B30'}, ${isBuy ? '#30D158' : '#FF453A'})`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 14, color: '#fff'
                  }}>
                    {stock.symbol?.[0] || '?'}
                  </div>
                  <div>
                    <span style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>{stock.symbol}</span>
                    <span style={{ display: 'block', fontSize: 10, color: '#8E8E93', marginTop: 1 }}>{stock.name}</span>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontWeight: 700, fontSize: 15, color: '#fff' }}>{fmtPrice(stock.price)}</span>
                  <span style={{ display: 'block', fontSize: 11, color: isPos ? '#34C759' : '#FF3B30', fontWeight: 600 }}>
                    {isPos ? '+' : ''}{change.toFixed(2)}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        {topSignals.length === 0 && (
          <div className="empty-state" style={{ padding: '30px 20px' }}>
            <p className="empty-state-title">Tidak ada sinyal aktif</p>
          </div>
        )}
      </div>
    </div>
  );
}
