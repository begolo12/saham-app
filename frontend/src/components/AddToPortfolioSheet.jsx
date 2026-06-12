import { useState, useEffect, useCallback, memo } from 'react';
import { fmtPrice, displayName } from '../utils';
import { lightHaptic, successHaptic } from '../utils/haptic';

/**
 * AddToPortfolioSheet — inline compact sheet to add a recommendation
 * to the virtual portfolio. Pre-fills avg_price from current price
 * and exposes a single lot input + "Simpan" button.
 *
 * Props:
 *   @param {object}  stock         — recommendation row (symbol, price, signal, ...)
 *   @param {Function} onClose
 *   @param {Function} onSave       — ({symbol, qty, avg_price}) => Promise
 *   @param {boolean}  alreadyHeld  — true if this symbol is already in the portfolio
 */
function AddToPortfolioSheet({ stock, onClose, onSave, alreadyHeld }) {
  const [qty, setQty] = useState('1');
  const [avgPrice, setAvgPrice] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (stock) {
      setQty('1');
      setAvgPrice(stock.price != null ? String(stock.price) : '');
      setError('');
    }
  }, [stock]);

  const qtyNum = Number(qty) || 0;
  const priceNum = Number(avgPrice) || 0;
  const total = qtyNum * priceNum;

  const handleSave = useCallback(async () => {
    if (!stock) return;
    if (qtyNum <= 0) { setError('Lot harus > 0'); return; }
    if (priceNum <= 0) { setError('Harga harus > 0'); return; }
    setBusy(true);
    setError('');
    try {
      await onSave({
        symbol: stock.symbol,
        qty: qtyNum,
        avg_price: priceNum,
      });
      successHaptic?.();
      onClose?.();
    } catch (e) {
      setError(e?.message || 'Gagal simpan');
    } finally {
      setBusy(false);
    }
  }, [stock, qtyNum, priceNum, onSave, onClose]);

  if (!stock) return null;

  return (
    <div className="add-sheet">
      <div className="add-sheet-head">
        <div className="add-sheet-symbol">
          <b>{stock.symbol}</b>
          <span>{displayName(stock)}</span>
        </div>
        <div className="add-sheet-price">
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Harga</span>
          <b>{fmtPrice(stock.price)}</b>
        </div>
      </div>

      {alreadyHeld && (
        <div className="add-sheet-hint" style={{ background: 'var(--tint-yellow)', color: 'var(--orange)' }}>
          Sudah ada di porto — simpan akan replace posisi.
        </div>
      )}

      <div className="add-sheet-grid">
        <label className="add-sheet-field">
          <span>Lot</span>
          <div className="add-sheet-qty">
            <button type="button" onClick={() => { lightHaptic(); setQty((q) => String(Math.max(1, (Number(q) || 1) - 1))); }}>−</button>
            <input
              type="number"
              inputMode="numeric"
              min="1"
              value={qty}
              onChange={(e) => setQty(e.target.value.replace(/[^0-9]/g, ''))}
            />
            <button type="button" onClick={() => { lightHaptic(); setQty((q) => String((Number(q) || 0) + 1)); }}>+</button>
          </div>
        </label>

        <label className="add-sheet-field">
          <span>Avg price</span>
          <input
            type="number"
            inputMode="numeric"
            value={avgPrice}
            onChange={(e) => setAvgPrice(e.target.value)}
          />
        </label>
      </div>

      <div className="add-sheet-total">
        <span>Modal</span>
        <b>{fmtPrice(total)}</b>
      </div>

      {error && <div className="add-sheet-error">{error}</div>}

      <div className="add-sheet-actions">
        <button type="button" className="add-sheet-btn-secondary" onClick={onClose} disabled={busy}>
          Batal
        </button>
        <button type="button" className="add-sheet-btn-primary" onClick={handleSave} disabled={busy}>
          {busy ? 'Menyimpan…' : 'Tambah ke Porto'}
        </button>
      </div>
    </div>
  );
}

export default memo(AddToPortfolioSheet);
