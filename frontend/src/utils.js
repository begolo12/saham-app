/**
 * Format a Date object to Indonesian locale time string.
 * @param {Date|null|undefined} date
 * @returns {string}
 */
export function fmtTime(date) {
  if (!date) return '';
  return date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/**
 * Format a number as Indonesian Rupiah price string.
 * @param {number|null|undefined} price
 * @returns {string}
 */
export function fmtPrice(price) {
  if (price == null) return '-';
  return 'Rp ' + Number(price).toLocaleString('id-ID', { minimumFractionDigits: 0 });
}

/**
 * Count stocks matching a signal type.
 * NEUTRAL matches both 'NEUTRAL' and 'HOLD'.
 * @param {Array} stocks
 * @param {'BUY'|'SELL'|'NEUTRAL'} type
 * @returns {number}
 */
export function countSignal(stocks, type) {
  return (stocks || []).filter(s => {
    const signal = s.signal || s.overall_signal || s.overallSignal;
    if (type === 'NEUTRAL') return signal === 'NEUTRAL' || signal === 'HOLD';
    return signal === type;
  }).length;
}
