import { memo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { lightHaptic } from '../utils/haptic';

/**
 * BottomNav — iOS-style segmented bottom navigation bar.
 *
 * Minimalist redesign (v2.0): 5 tabs → 3 primary tabs to keep tab labels
 * readable on small phones and reduce visual noise. The "Laporan" and
 * "Belajar" surfaces remain reachable via the header overflow menu
 * (see /laporan and /belajar routes) and via the RecommendationModal.
 */
const SEGMENTS = ['Pasar', 'Sinyal', 'Porto'];

/** Path → segment label lookup */
const PATH_SEGMENT = {
  '/': 'Pasar',
  '/signal': 'Sinyal',
  '/portfolio': 'Porto',
  '/report': 'Pasar',  // legacy → fall through to Pasar
  '/learning': 'Pasar',
};

/** Segment label → path */
const SEGMENT_PATH = {
  'Pasar': '/',
  'Sinyal': '/signal',
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
            {label === 'Pasar' ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            ) : label === 'Sinyal' ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
            )}
          </span>
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export default memo(BottomNav);
