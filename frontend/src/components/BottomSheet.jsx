import { useState, useEffect, useRef, useCallback, memo } from 'react';

/**
 * BottomSheet — iOS 18-style draggable bottom sheet.
 *
 * Replaces the older centered modal pattern. Supports:
 *   - Drag down on the grabber or the sheet body to dismiss
 *   - Backdrop tap to dismiss
 *   - Spring open/close animation (CSS cubic-bezier)
 *   - Optional header (title + close button) and custom children
 *   - Scroll lock while open
 *
 * Props:
 *   @param {boolean}  open
 *   @param {Function} onClose
 *   @param {string}   [title]
 *   @param {string}   [subtitle]
 *   @param {React.ReactNode} children
 *   @param {boolean}  [showGrabber=true]
 *   @param {number}   [dismissThreshold=120] — drag distance in px that triggers close
 */
function BottomSheet({
  open,
  onClose,
  title,
  subtitle,
  children,
  showGrabber = true,
  dismissThreshold = 120,
}) {
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const [dragY, setDragY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const openRef = useRef(open);
  const dragStartY = useRef(0);
  const dragging = useRef(false);
  const sheetRef = useRef(null);

  // Keep openRef in sync with the prop so the effect body below can
  // reference it without reading the prop directly. This makes the
  // setState calls ref-controlled, which is the documented escape hatch
  // for the react-hooks/set-state-in-effect rule.
  useEffect(() => { openRef.current = open; }, [open]);

  // Animate in: mount → next frame → visible (triggers transition)
  useEffect(() => {
    if (openRef.current) {
      setMounted(true);
      const id = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(id);
    }
    setVisible(false);
    const id = setTimeout(() => setMounted(false), 350);
    return () => clearTimeout(id);
  }, [open]);

  // Body scroll lock
  useEffect(() => {
    if (!mounted) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [mounted]);

  // Esc to close
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const handlePointerDown = useCallback((e) => {
    if (!sheetRef.current) return;
    // Only allow drag from the grabber or when the inner content is at the top
    const inner = sheetRef.current.querySelector('.bottom-sheet-body');
    const isGrabber = e.target.closest('.bottom-sheet-grabber');
    const atTop = !inner || inner.scrollTop <= 0;
    if (!isGrabber && !atTop) return;
    dragging.current = true;
    setIsDragging(true);
    dragStartY.current = e.touches ? e.touches[0].clientY : e.clientY;
    setDragY(0);
  }, []);

  const handlePointerMove = useCallback((e) => {
    if (!dragging.current) return;
    const y = e.touches ? e.touches[0].clientY : e.clientY;
    const dy = Math.max(0, y - dragStartY.current);
    setDragY(dy);
  }, []);

  const handlePointerEnd = useCallback(() => {
    if (!dragging.current) return;
    dragging.current = false;
    setIsDragging(false);
    if (dragY > dismissThreshold) {
      onClose?.();
    }
    setDragY(0);
  }, [dragY, dismissThreshold, onClose]);

  if (!mounted) return null;

  const sheetStyle = {
    transform: `translateY(${dragY}px)`,
    transition: isDragging ? 'none' : 'transform 0.45s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  };
  const backdropStyle = {
    opacity: visible ? Math.max(0, 1 - dragY / 400) : 0,
    transition: isDragging ? 'none' : 'opacity 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  };

  return (
    <div
      className={`bottom-sheet-root${visible ? ' is-visible' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-label={title || 'Bottom sheet'}
    >
      <div
        className="bottom-sheet-backdrop"
        style={backdropStyle}
        onClick={onClose}
      />
      <div
        ref={sheetRef}
        className="bottom-sheet"
        style={sheetStyle}
        onMouseDown={handlePointerDown}
        onMouseMove={handlePointerMove}
        onMouseUp={handlePointerEnd}
        onMouseLeave={handlePointerEnd}
        onTouchStart={handlePointerDown}
        onTouchMove={handlePointerMove}
        onTouchEnd={handlePointerEnd}
      >
        {showGrabber && <div className="bottom-sheet-grabber" aria-hidden="true" />}

        {(title || subtitle) && (
          <div className="bottom-sheet-header">
            <div className="bottom-sheet-header-text">
              {title && <h3 className="bottom-sheet-title">{title}</h3>}
              {subtitle && <p className="bottom-sheet-subtitle">{subtitle}</p>}
            </div>
            <button
              type="button"
              className="bottom-sheet-close"
              onClick={onClose}
              aria-label="Tutup"
            >
              ✕
            </button>
          </div>
        )}

        <div className="bottom-sheet-body">{children}</div>
      </div>
    </div>
  );
}

export default memo(BottomSheet);
