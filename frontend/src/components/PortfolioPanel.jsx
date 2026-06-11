import { useState, useCallback, memo } from 'react';
import { fmtPrice } from '../utils';
import Skeleton from './Skeleton';

function PortfolioPanel({ portfolio, onSave, onDelete, stocks = [] }) {
  const [form, setForm] = useState({ symbol: '', qty: '', avg_price: '' });
  const [showSuggestions, setShowSuggestions] = useState(false);
  const summary = portfolio?.summary || {};
  const positions = portfolio?.positions || [];
  const symbolQuery = (form.symbol || '').toUpperCase();
  const suggestions = (stocks || [])
    .filter(s => symbolQuery && (s.symbol || '').toUpperCase().includes(symbolQuery))
    .sort((a, b) => (a.symbol || '').localeCompare(b.symbol || ''))
    .slice(0, 60);

  // eslint-disable-next-line react-hooks/preserve-manual-memoization -- stable, no deps needed
  const selectSuggestion = useCallback((stock) => {
    setForm(prev => ({ ...prev, symbol: (stock.symbol || '').toUpperCase() }));
    setShowSuggestions(false);
  }, []);

  // eslint-disable-next-line react-hooks/preserve-manual-memoization -- compiler infers different deps; form is a snapshot at submit time
  const submit = useCallback((e) => {
    e.preventDefault();
    if (!form.symbol || !form.qty || !form.avg_price) return;
    onSave({ symbol: form.symbol, qty: Number(form.qty), avg_price: Number(form.avg_price) });
    setForm({ symbol: '', qty: '', avg_price: '' });
    setShowSuggestions(false);
  }, [form, onSave]);

  if (!portfolio) {
    return (
      <div style={{ padding: '0 16px 24px' }}>
        <Skeleton variant="market-summary" />
        <Skeleton variant="card" count={3} />
      </div>
    );
  }

  return <div style={{ padding: '0 16px 24px' }}>
    <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
      <div className="market-summary-header"><h3>Virtual Portfolio</h3><span style={{ color: (summary.total_pnl || 0) >= 0 ? '#34C759' : '#FF3B30', fontWeight: 800 }}>{(summary.total_pnl_pct || 0).toFixed(2)}%</span></div>
      <div className="portfolio-grid">
        <div className="learning-stat"><b>{fmtPrice(summary.total_value || 0)}</b><span>Nilai</span></div>
        <div className="learning-stat"><b>{fmtPrice(summary.total_pnl || 0)}</b><span>P/L</span></div>
        <div className="learning-stat"><b>{summary.win_rate || 0}%</b><span>Win rate</span></div>
      </div>
    </div>
    <form className="portfolio-form" onSubmit={submit}>
      <div className="portfolio-symbol-field">
        <input
          placeholder="Kode (BBCA)"
          value={form.symbol}
          onFocus={() => setShowSuggestions(Boolean(form.symbol))}
          onChange={e => { setForm({ ...form, symbol: e.target.value.toUpperCase() }); setShowSuggestions(Boolean(e.target.value)); }}
          autoComplete="off"
        />
        {showSuggestions && suggestions.length > 0 && (
          <div className="portfolio-autocomplete">
            {suggestions.map(stock => (
              <button
                key={stock.symbol}
                type="button"
                className="portfolio-suggestion"
                onMouseDown={e => { e.preventDefault(); selectSuggestion(stock); }}
                onTouchStart={e => { e.preventDefault(); selectSuggestion(stock); }}
              >
                <b>{stock.symbol}</b><span>{stock.name || stock.sector || 'Saham IDX'}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <input placeholder="Lot/lembar" type="number" value={form.qty} onChange={e => setForm({ ...form, qty: e.target.value })} />
      <input placeholder="Avg price" type="number" value={form.avg_price} onChange={e => setForm({ ...form, avg_price: e.target.value })} />
      <button>Simpan</button>
    </form>
    <p className="section-label">Posisi</p>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {positions.map(pos => <div className="signal-card" key={pos.symbol}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
          <div><b style={{ color: '#fff' }}>{pos.symbol}</b><div style={{ color: '#8E8E93', fontSize: 12 }}>{pos.qty} @ {fmtPrice(pos.avg_price)} • now {fmtPrice(pos.current_price)}</div></div>
          <div style={{ textAlign: 'right' }}><b style={{ color: pos.pnl >= 0 ? '#34C759' : '#FF3B30' }}>{pos.pnl_pct}%</b><div style={{ color: '#8E8E93', fontSize: 12 }}>{fmtPrice(pos.pnl)}</div></div>
        </div>
        <button className="sort-chip" style={{ marginTop: 10 }} onClick={() => onDelete(pos.symbol)}>Hapus</button>
      </div>)}
      {!positions.length && <div className="empty-state"><p className="empty-state-title">Porto kosong</p><p className="empty-state-desc">Masukkan posisi real app saham kamu di sini.</p></div>}
    </div>
  </div>;
}

export default memo(PortfolioPanel);
