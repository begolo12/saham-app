// ============================================================
// constants.js — Shared frontend constants
// Centralized magic numbers so changes are one-line edits.
// ============================================================

// Minimum daily volume to consider a stock "liquid" (worth trading).
// Used for liquidity filter (StockList) and low-volume warning icon (StockCard).
export const LIQUIDITY_THRESHOLD = 10000;

// Signal strength thresholds (0-100 scale).
// Used to classify overall signal as BUY / NEUTRAL / SELL.
export const SIGNAL_BUY_THRESHOLD = 65;
export const SIGNAL_SELL_THRESHOLD = 40;
