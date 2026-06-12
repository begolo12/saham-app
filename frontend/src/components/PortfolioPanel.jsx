import { useState, useCallback, useMemo, useEffect, memo } from 'react';
import { fmtPrice } from '../utils';
import Skeleton from './Skeleton';
import { lightHaptic, mediumHaptic, successHaptic } from '../utils/haptic';

/**
 * PortfolioPanel — compact virtual portfolio.
 * - Summary row folded by default, tap to expand
 * - "Tambah" inline form, collapsed by default, autocomplete via native datalist
 * - Position rows: 1-line, tap to expand for full breakdown
 */
function PortfolioPanel({ portfolio, onSave, onDelete, stocks = [] }) {
  const [openForm, setOpenForm] = useState(false);
  const [form, setForm] = useState({ symbol: '', qty: '1', avg_price: '' });
  const [openPos, setOpenPos] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const summary = portfolio?.summary || {};
  const positions = portfolio?.positions || [];

  const symbolOptions = useMemo(
    () => (stocks || [])
      .map((s) => s.symbol)
      .filter(Boolean)
      .filter((v, i, a) => a.indexOf(v) === i)
      .sort(),
    [stocks],
  );

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(null), 1600);
    return () => clearTimeout(t);
  }, [toast]);

  const showToast = useCallback((msg) => {
    successHaptic?.();
    setToast(msg);
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault?.();
    if (!form.symbol || !form.qty || !form.avg_price) return;
    setBusy(true);
    try {
      await onSave({
        symbol: form.symbol.toUpperCase(),
        qty: Number(form.qty),
        avg_price: Number(form.avg_price),
      });
      setForm({ symbol: '', qty: '1', avg_price: '' });
      setOpenForm(false);
      showToast('Posisi disimpan');
    } finally {
      setBusy(false);
    }
  }, [form, onSave, showToast]);

  const handleDelete = useCallback(async (sym) => {
    lightHaptic();
    await onDelete(sym);
    showToast(`${sym} dihapus`);
  }, [onDelete, showToast]);

  if (!portfolio) {
    return (
      <div className="report-compact">
        <Skeleton variant="market-summary" />
        <Skeleton variant="card" count={3} />
      </div>
    );
  }

  return (
    <div className="report-compact">
      <details className="report-summary" open>
        <summary>
          <span className="rs-title">Porto</span>
          <span className={`rs-pct ${(summary.total_pnl || 0) >= 0 ? 'pos' : 'neg'}`}>
            {(summary.total_pnl_pct || 0).toFixed(2)}%
          </span>
          <span className="rs-chev" aria-hidden>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
          </span>
        </summary>
        <div className="rs-body">
          <div><span>Nilai</span><b>{fmtPrice(summary.total_value || 0)}</b></div>
          <div><span>P/L</span><b className={(summary.total_pnl || 0) >= 0 ? 'pos' : 'neg'}>{fmtPrice(summary.total_pnl || 0)}</b></div>
          <div><span>Win</span><b>{summary.win_rate || 0}%</b></div>
        </div>
      </details>

      <div className="portfolio-toolbar">
        <span className="section-label" style={{ margin: 0 }}>Posisi <span className="section-count">{positions.length}</span></span>
        <button
          type="button"
          className="add-btn primary"
          onClick={() => { mediumHaptic(); setOpenForm((v) => !v); }}
        >
          {openForm ? 'Batal' : '+ Tambah'}
        </button>
      </div>

      {openForm && (
        <form className="portfolio-form-compact" onSubmit={handleSubmit}>
          <label>
            <span>Kode</span>
            <input
              list="porto-symbols"
              placeholder="BBCA"
              value={form.symbol}
              onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
              autoComplete="off"
            />
            <datalist id="porto-symbols">
              {symbolOptions.map((s) => <option key={s} value={s} />)}
            </datalist>
          </label>
          <label>
            <span>Lot</span>
            <input
              type="number"
              inputMode="numeric"
              min="1"
              value={form.qty}
              onChange={(e) => setForm({ ...form, qty: e.target.value })}
            />
          </label>
          <label>
            <span>Avg</span>
            <input
              type="number"
              inputMode="numeric"
              value={form.avg_price}
              onChange={(e) => setForm({ ...form, avg_price: e.target.value })}
            />
          </label>
          <button type="submit" className="add-btn primary" disabled={busy}>
            {busy ? 'Simpan…' : 'Simpan'}
          </button>
        </form>
      )}

      <div className="compact-list">
        {positions.map((pos) => {
          const isOpen = openPos === pos.symbol;
          const pnlPos = (pos.pnl || 0) >= 0;
          return (
            <div key={pos.symbol} className={`signal-card compact ${isOpen ? 'is-open' : ''}`}>
              <button
                type="button"
                className="signal-card-row"
                onClick={() => { lightHaptic(); setOpenPos(isOpen ? null : pos.symbol); }}
                aria-expanded={isOpen}
              >
                <span className="signal-card-symbol">{pos.symbol}</span>
                <span className="signal-card-pill" style={{ color: pnlPos ? 'var(--green)' : 'var(--red)' }}>
                  {(pos.pnl_pct || 0).toFixed(1)}%
                </span>
                <span className="signal-card-price">{fmtPrice(pos.current_price)}</span>
                <span className="signal-card-chev" aria-hidden>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </span>
              </button>
              {!isOpen && (
                <div className="signal-card-glance">
                  <span>{pos.qty} lot @ {fmtPrice(pos.avg_price)}</span>
                </div>
              )}
              {isOpen && (
                <div className="signal-card-detail">
                  <div className="signal-card-grid">
                    <div><span>Qty</span><b>{pos.qty} lot</b></div>
                    <div><span>Avg</span><b>{fmtPrice(pos.avg_price)}</b></div>
                    <div><span>Now</span><b>{fmtPrice(pos.current_price)}</b></div>
                    <div><span>P/L</span><b className={pnlPos ? 'pos' : 'neg'}>{fmtPrice(pos.pnl)}</b></div>
                  </div>
                  <div className="signal-card-actions">
                    <button type="button" className="add-btn secondary danger" onClick={(e) => { e.stopPropagation(); handleDelete(pos.symbol); }}>
                      Hapus
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {!positions.length && <div className="empty-line">Belum ada posisi · tambah dari Laporan atau +Tambah</div>}
      </div>

      {toast && (
        <div className="toast" role="status">
          <span className="toast-icon">✓</span>
          <span>{toast}</span>
        </div>
      )}
    </div>
  );
}

export default memo(PortfolioPanel);
