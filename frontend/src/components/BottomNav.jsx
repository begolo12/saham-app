import { memo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { lightHaptic } from '../utils/haptic';

const SEGMENTS = ['Laporan', 'Pasar', 'Sinyal', 'Berita', 'Porto'];

/** Path → segment label lookup */
const PATH_SEGMENT = {
  '/report': 'Laporan',
  '/': 'Pasar',
  '/signal': 'Sinyal',
  '/news': 'Berita',
  '/portfolio': 'Porto',
};

/** Segment label → path */
const SEGMENT_PATH = {
  'Laporan': '/report',
  'Pasar': '/',
  'Sinyal': '/signal',
  'Berita': '/news',
  'Porto': '/portfolio',
};

/**
 * BottomNav — iOS-style segmented bottom navigation bar.
 * Now uses React Router for navigation.
 */
function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const activeLabel = PATH_SEGMENT[location.pathname] || '';

  return (
    <nav className="bottom-segmented-nav" aria-label="Navigasi utama">
      {SEGMENTS.map((label) => (
        <button
          key={label}
          className={`bottom-segmented-btn${activeLabel === label ? ' active' : ''}`}
          onClick={() => { lightHaptic(); navigate(SEGMENT_PATH[label]); }}
        >
          <span className="bottom-segmented-icon">
            {label === 'Laporan' ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            ) : label === 'Pasar' ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            ) : label === 'Sinyal' ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            ) : label === 'Berita' ? (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-4 0V8"/><line x1="10" y1="6" x2="18" y1="6"/><line x1="10" y1="10" x2="18" y1="10"/><line x1="10" y1="14" x2="14" y1="14"/></svg>
            ) : (
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
            )}
          </span>
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export default memo(BottomNav);
