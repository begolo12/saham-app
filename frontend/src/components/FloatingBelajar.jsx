import { memo } from 'react';

/**
 * FloatingBelajar — floating action button that navigates to the Belajar (learning) tab.
 *
 * Props:
 *   @param {Function} onClick — () => void
 */
function FloatingBelajar({ onClick }) {
  return (
    <button className="belajar-float" onClick={onClick} aria-label="Belajar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
      <span>Belajar</span>
    </button>
  );
}

export default memo(FloatingBelajar);
