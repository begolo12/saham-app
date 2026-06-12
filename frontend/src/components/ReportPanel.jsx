import { memo, useState, useCallback, useEffect } from 'react';
import SignalBadge from './SignalBadge';
import AddToPortfolioSheet from './AddToPortfolioSheet';
import BottomSheet from './BottomSheet';
import { fmtPrice } from '../utils';
import Skeleton from './Skeleton';
import { lightHaptic, mediumHaptic } from '../utils/haptic';
import { usePortfolioStore } from '../stores';

/**
 * TradeCard — single ultra-compact card.
 * - Row 1: Symbol | signal badge | price | chevron toggle
 * - Row 2 (collapsed): 1-line target/risk glance
 * - Row 3 (expanded): full trade plan + "Tambah ke Porto" button
 */
function TradeCard({ row, isBuy, held, onAdd, onOpenDetail }) {
  const [open, setOpen] = useState(false);
  const tp = row.trade_plan || {};
  const target = tp.take_profit || tp.target;
  const invalid = tp.stop_loss || tp.invalidation;

  return (
    <div className={`signal-card compact ${open ? 'is-open' : ''} ${isBuy ? 'is-buy' : 'is-sell'}`}>
      <button
        type="button"
        className="signal-card-row"
        onClick={() => { lightHaptic(); setOpen((v) => !v); }}
        aria-expanded={open}
      >
        <span className="signal-card-symbol">{row.symbol}</span>
        <SignalBadge signal={row.signal} strength={row.signal_strength} compact />
        <span className="signal-card-price">{fmtPrice(row.price)}</span>
        <span className="signal-card-chev" aria-hidden>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </span>
      </button>

      {!open && (
        <div className="signal-card-glance">
          {isBuy ? (
            <span>Target {fmtPrice(target)} · SL {fmtPrice(invalid)}</span>
          ) : (
            <span>Target {fmtPrice(target)} · Invalid {fmtPrice(invalid)}</span>
          )}
          {held && <span className="held-pill">di porto</span>}
        </div>
      )}

      {open && (
        <div className="signal-card-detail">
          <div className="signal-card-grid">
            <div><span>Entry</span><b>{fmtPrice(tp.entry || row.price)}</b></div>
            <div><span>Target</span><b className={isBuy ? 'pos' : 'neg'}>{fmtPrice(target)}</b></div>
            <div><span>Stop</span><b className={isBuy ? 'neg' : 'pos'}>{fmtPrice(invalid)}</b></div>
            <div><span>Horizon</span><b>{tp.horizon || '7D'}</b></div>
          </div>
          {tp.instruction && <p className="signal-card-note">{tp.instruction}</p>}

          <div className="signal-card-actions">
            {isBuy && (
              <button type="button" className="add-btn primary" onClick={(e) => { e.stopPropagation(); mediumHaptic(); onAdd(row); }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Tambah ke Porto
              </button>
            )}
            <button type="button" className="add-btn secondary" onClick={(e) => { e.stopPropagation(); lightHaptic(); onOpenDetail(row); }}>
              Detail
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * ReportPanel — compact Laporan page.
 * - Folded-by-default signal cards (1 line each)
 * - Tap to expand: full trade plan + "Tambah ke Porto" action
 * - "Tambah ke Porto" opens a bottom sheet with lot input (pre-filled avg price)
 * - Portfolio summary collapsed to single row
 */
function ReportPanel({ report, onOpenDetail }) {
  const { portfolio, savePosition } = usePortfolioStore();
  const [addTarget, setAddTarget] = useState(null);
  const [savedToast, setSavedToast] = useState(null);

  const buys = report?.buy_now || [];
  const sells = report?.sell_or_avoid || [];
  const summary = report?.portfolio || {};
  const heldSymbols = new Set((portfolio?.positions || []).map((p) => p.symbol));

  // Auto-dismiss toast
  useEffect(() => {
    if (!savedToast) return undefined;
    const t = setTimeout(() => setSavedToast(null), 1800);
    return () => clearTimeout(t);
  }, [savedToast]);

  const handleAdd = useCallback((row) => {
    setAddTarget(row);
  }, []);

  const handleSave = useCallback(async (pos) => {
    await savePosition(pos);
    setSavedToast(`${pos.symbol} • ${pos.qty} lot @ ${fmtPrice(pos.avg_price)}`);
  }, [savePosition]);

  if (!report) {
    return (
      <div className="report-compact">
        <Skeleton variant="market-summary" />
        <Skeleton variant="card" count={2} />
        <Skeleton variant="card" count={2} />
      </div>
    );
  }

  return (
    <div className="report-compact">
      <details className="report-summary">
        <summary>
          <span className="rs-title">Ringkasan Porto</span>
          <span className={`rs-pct ${(summary.total_pnl_pct || 0) >= 0 ? 'pos' : 'neg'}`}>
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

      <p className="section-label">BUY · target 7 hari <span className="section-count">{buys.length}</span></p>
      <div className="compact-list">
        {buys.map((s) => (
          <TradeCard
            key={s.symbol}
            row={s}
            isBuy
            held={heldSymbols.has(s.symbol)}
            onAdd={handleAdd}
            onOpenDetail={onOpenDetail}
          />
        ))}
        {!buys.length && <div className="empty-line">Belum ada BUY kuat</div>}
      </div>

      <p className="section-label">SELL / Hindari <span className="section-count">{sells.length}</span></p>
      <div className="compact-list">
        {sells.map((s) => (
          <TradeCard
            key={s.symbol}
            row={s}
            isBuy={false}
            held={heldSymbols.has(s.symbol)}
            onAdd={handleAdd}
            onOpenDetail={onOpenDetail}
          />
        ))}
        {!sells.length && <div className="empty-line">Tidak ada SELL aktif</div>}
      </div>

      <BottomSheet
        open={Boolean(addTarget)}
        onClose={() => setAddTarget(null)}
        title={addTarget ? `Beli ${addTarget.symbol}` : ''}
        subtitle={addTarget ? `Rekomendasi 7 hari · ${fmtPrice(addTarget.price)}` : ''}
      >
        <AddToPortfolioSheet
          stock={addTarget}
          onClose={() => setAddTarget(null)}
          onSave={handleSave}
          alreadyHeld={addTarget ? heldSymbols.has(addTarget.symbol) : false}
        />
      </BottomSheet>

      {savedToast && (
        <div className="toast" role="status">
          <span className="toast-icon">✓</span>
          <span>{savedToast} tersimpan</span>
        </div>
      )}
    </div>
  );
}

export default memo(ReportPanel);
