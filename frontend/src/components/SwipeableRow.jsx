import { useState, useRef, useCallback, memo } from 'react';
import { lightHaptic, successHaptic } from '../utils/haptic';

const THRESHOLD = 80;       // px of drag that triggers the action
const MAX_DRAG = 140;       // px clamp on the visual translation

/**
 * SwipeableRow — wraps a child (typically a stock card) and reveals an action
 * panel when swiped horizontally. Swipe right → action panel on the left
 * (default: add to watchlist). Swipe left → action panel on the right
 * (default: remove from watchlist).
 *
 * Props:
 *   @param {React.ReactNode} children
 *   @param {Function} [onSwipeRight] — called when user releases past threshold on right swipe
 *   @param {Function} [onSwipeLeft]  — called when user releases past threshold on left swipe
 *   @param {string}   [rightLabel='Tambah Watchlist']
 *   @param {string}   [leftLabel='Hapus']
 *   @param {boolean}  [rightActive=false]  — show "active" state (e.g. already watched)
 *   @param {boolean}  [disabled=false]     — disable swipe entirely
 */
function SwipeableRow({
  children,
  onSwipeRight,
  onSwipeLeft,
  rightLabel = 'Tambah Watchlist',
  leftLabel = 'Hapus',
  rightActive = false,
  leftActive = false,
  disabled = false,
}) {
  const [dragX, setDragX] = useState(0);
  const [hasDragged, setHasDragged] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const startX = useRef(0);
  const startY = useRef(0);
  const tracking = useRef(false);
  const axis = useRef(null); // 'h' | 'v' | null
  const trackRef = useRef(null);

  const onStart = useCallback((e) => {
    if (disabled) return;
    const pt = e.touches ? e.touches[0] : e;
    startX.current = pt.clientX;
    startY.current = pt.clientY;
    tracking.current = true;
    axis.current = null;
    setIsDragging(false);
  }, [disabled]);

  const onMove = useCallback((e) => {
    if (!tracking.current) return;
    const pt = e.touches ? e.touches[0] : e;
    const dx = pt.clientX - startX.current;
    const dy = pt.clientY - startY.current;

    if (axis.current === null) {
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      // Lock to the dominant axis; if vertical wins, abandon horizontal swipe
      axis.current = Math.abs(dy) > Math.abs(dx) ? 'v' : 'h';
      if (axis.current === 'h') setIsDragging(true);
    }
    if (axis.current !== 'h') return;

    // Clamp so the row never slides more than MAX_DRAG
    const clamped = Math.max(-MAX_DRAG, Math.min(MAX_DRAG, dx));
    setDragX(clamped);
    if (Math.abs(clamped) > 8) setHasDragged(true);
  }, []);

  const snapBack = useCallback(() => {
    setDragX(0);
    const id = setTimeout(() => setHasDragged(false), 250);
    return () => clearTimeout(id);
  }, []);

  const onEnd = useCallback(() => {
    if (!tracking.current) return;
    tracking.current = false;
    if (axis.current !== 'h') {
      axis.current = null;
      return;
    }
    axis.current = null;

    if (dragX > THRESHOLD) {
      lightHaptic();
      onSwipeRight?.();
    } else if (dragX < -THRESHOLD) {
      lightHaptic();
      onSwipeLeft?.();
    } else {
      snapBack();
    }
    setDragX(0);
    setIsDragging(false);
    // Success haptic on the small bounce-back if action fired
    if (dragX > THRESHOLD || dragX < -THRESHOLD) {
      successHaptic();
    }
  }, [dragX, onSwipeRight, onSwipeLeft, snapBack]);

  const showRight = dragX > 0;
  const showLeft = dragX < 0;

  return (
    <div
      className={`swipe-row${hasDragged ? ' has-dragged' : ''}`}
      onTouchStart={onStart}
      onTouchMove={onMove}
      onTouchEnd={onEnd}
      onTouchCancel={onEnd}
      onMouseDown={onStart}
      onMouseMove={onMove}
      onMouseUp={onEnd}
      onMouseLeave={onEnd}
    >
      {(onSwipeLeft || leftActive) && (
        <div className={`swipe-action swipe-action-left remove${leftActive ? ' active' : ''}`} style={{ opacity: showLeft ? 1 : 0.0 }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></svg>
          {leftLabel}
        </div>
      )}
      {(onSwipeRight || rightActive) && (
        <div className={`swipe-action swipe-action-right watchlist${rightActive ? ' active' : ''}`} style={{ opacity: showRight ? 1 : 0.0 }}>
          <svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          {rightLabel}
        </div>
      )}
      <div
        ref={trackRef}
        className={`swipe-row-track${isDragging ? ' dragging' : ''}`}
        style={{ transform: `translateX(${dragX}px)` }}
      >
        {children}
      </div>
    </div>
  );
}

export default memo(SwipeableRow);
