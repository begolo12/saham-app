import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';

import ErrorBoundary from './components/ErrorBoundary';
import PageErrorBoundary from './components/PageErrorBoundary';
import BottomNav from './components/BottomNav';
import BottomSheet from './components/BottomSheet';
import InstallPrompt from './components/InstallPrompt';
import Skeleton from './components/Skeleton';
import SignalBadge from './components/SignalBadge';
import { fmtTime, countSignal, displayName } from './utils';
import { lightHaptic, mediumHaptic } from './utils/haptic';
import useTheme from './utils/useTheme';
import { ensureBackHistory } from './utils/pwaBack';

import useAuthStore from './stores/authStore';
import useStocksStore from './stores/stocksStore';

import MarketPage from './pages/MarketPage';
import SignalPage from './pages/SignalPage';
import NewsPage from './pages/NewsPage';
import PortfolioPage from './pages/PortfolioPage';
import LearningPage from './pages/LearningPage';
import ReportPage from './pages/ReportPage';
import AccuracyPage from './pages/AccuracyPage';
import StockDetailPage from './pages/StockDetailPage';
import LoginRoute from './pages/LoginRoute';

/* ─────────────────────────── Skeletons ─────────────────────────── */

function LoadingScreen() {
  return (
    <div className="loading-screen">
      <div className="loading-screen-inner">
        <div className="spinner-large" />
        <div className="loading-dots"><span /><span /><span /></div>
        <p className="loading-screen-text">Memeriksa sesi...</p>
      </div>
    </div>
  );
}

const listFallback = (
  <div className="page" style={{ padding: '0 16px' }}>
    <Skeleton variant="card" count={4} />
  </div>
);

const reportFallback = (
  <div className="page" style={{ padding: '0 16px' }}>
    <Skeleton variant="market-summary" />
    <Skeleton variant="card" count={3} />
  </div>
);

/* ─────────────────────────── Header ─────────────────────────── */

const PAGE_TITLES = {
  '/': 'Saham ID',
  '/signal': 'Sinyal',
  '/news': 'Berita',
  '/portfolio': 'Portofolio',
  '/learning': 'Pembelajaran',
  '/accuracy': 'Akurasi',
  '/report': 'Laporan',
};

function resolveTitle(pathname) {
  if (pathname.startsWith('/detail/')) return 'Detail Saham';
  return PAGE_TITLES[pathname] || 'Saham ID';
}

function AppHeader({ authUser, lastUpdatedStr, resolved, toggleTheme, onBack, onLogout, showBack, title }) {
  return (
    <header className="app-header">
      <div className="app-title-wrap">
        {showBack ? (
          <button
            className="header-back-btn"
            onClick={onBack}
            aria-label="Kembali"
            type="button"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        ) : null}
        <h1 className="app-title">{title}</h1>
        {!showBack && <span className="live-dot" />}
      </div>
      <div className="header-right">
        {authUser && <span className="last-updated">{authUser.username}</span>}
        {lastUpdatedStr && !showBack && <span className="last-updated">· {lastUpdatedStr}</span>}
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={resolved === 'light' ? 'Aktifkan mode gelap' : 'Aktifkan mode terang'}
          title={resolved === 'light' ? 'Mode gelap' : 'Mode terang'}
        >
          <svg className="theme-icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <svg className="theme-icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.07" y2="4.93"/></svg>
        </button>
        {authUser && (
          <button className="logout-btn" onClick={onLogout} type="button">Keluar</button>
        )}
      </div>
    </header>
  );
}

/* ─────────────────────────── Pull-to-refresh ─────────────────────────── */

function usePullToRefresh(onRefresh, scrollRef) {
  const [pulling, setPulling] = useState(false);
  const [pullY, setPullY] = useState(0);
  const touchStartY = useRef(0);
  const scrollAtStart = useRef(0);

  const onTouchStart = useCallback((e) => {
    if (scrollRef.current) scrollAtStart.current = scrollRef.current.scrollTop;
    touchStartY.current = e.touches[0].clientY;
  }, [scrollRef]);

  const onTouchMove = useCallback((e) => {
    if (scrollAtStart.current > 0) return;
    const dy = e.touches[0].clientY - touchStartY.current;
    if (dy > 0) {
      setPulling(true);
      setPullY(Math.min(dy * 0.4, 80));
    }
  }, []);

  const onTouchEnd = useCallback(() => {
    if (pullY > 40) onRefresh();
    setPulling(false);
    setPullY(0);
  }, [pullY, onRefresh]);

  return { pulling, pullY, onTouchStart, onTouchMove, onTouchEnd };
}

/* ─────────────────────────── Watchlist hook ─────────────────────────── */

const WATCHLIST_KEY = 'saham_watchlist';

function loadWatchlist() {
  try { return JSON.parse(localStorage.getItem(WATCHLIST_KEY)) || []; } catch { return []; }
}

function useWatchlist() {
  const [watchlist, setWatchlist] = useState(loadWatchlist);

  useEffect(() => {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  }, [watchlist]);

  const toggle = useCallback((symbol) => {
    lightHaptic();
    setWatchlist((prev) => (prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol]));
  }, []);

  return { watchlist, toggle };
}

/* ─────────────────────────── App shell ─────────────────────────── */

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { authUser, checkSession, logout } = useAuthStore();
  const { allStocks, loading, lastUpdated, fetchTopStocks, fetchMarketSummary } = useStocksStore();
  const { resolved, toggle: toggleTheme } = useTheme();

  // UI state
  const [offline, setOffline] = useState(!navigator.onLine);
  const [recommendationModalOpen, setRecommendationModalOpen] = useState(false);
  const { watchlist, toggle: toggleWatchlist } = useWatchlist();
  const mainRef = useRef(null);

  // PWA: patch history on cold-start deep link
  useEffect(() => {
    ensureBackHistory(location.pathname);
  }, [location.pathname]);

  // Online detection
  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  // Auth + initial data
  useEffect(() => { checkSession(); }, [checkSession]);
  useEffect(() => { fetchTopStocks(); fetchMarketSummary(); }, [fetchTopStocks, fetchMarketSummary]);

  // Refresh intervals
  useEffect(() => {
    const market = setInterval(fetchMarketSummary, 30000);
    const stocks = setInterval(fetchTopStocks, 60000);
    return () => { clearInterval(market); clearInterval(stocks); };
  }, [fetchTopStocks, fetchMarketSummary]);

  // Derived
  const lastUpdatedStr = lastUpdated ? fmtTime(lastUpdated) : '';
  const isDetailPage = location.pathname.startsWith('/detail/');
  const isAccuracyPage = location.pathname.startsWith('/accuracy');
  const isAdminPage = location.pathname.startsWith('/admin');
  const showBack = isDetailPage || isAccuracyPage;
  const showBottomNav = !isDetailPage && !isAccuracyPage && !isAdminPage;
  const title = resolveTitle(location.pathname);

  const recommendedStocks = allStocks
    .filter((s) => s.signal === 'BUY' || s.signal === 'SELL')
    .sort((a, b) => (b.signal_strength || 0) - (a.signal_strength || 0));

  /* Actions */
  const handleRefresh = useCallback(() => {
    lightHaptic();
    fetchTopStocks();
    fetchMarketSummary();
  }, [fetchTopStocks, fetchMarketSummary]);

  const handleSelectStock = useCallback((stock) => {
    lightHaptic();
    navigate(`/detail/${stock.symbol}`);
  }, [navigate]);

  const handleBack = useCallback(() => {
    lightHaptic();
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/');
    }
  }, [navigate]);

  const handleLogout = useCallback(() => {
    lightHaptic();
    logout();
    navigate('/login', { replace: true });
  }, [logout, navigate]);

  const openRecommendations = useCallback(() => {
    mediumHaptic();
    setRecommendationModalOpen(true);
  }, []);

  const pull = usePullToRefresh(handleRefresh, mainRef);

  /* Auth gate — synchronous from localStorage, no network wait */
  if (!authUser) {
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingScreen />}>
          <Routes>
            <Route path="*" element={<LoginRoute />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    );
  }

  /* Authenticated app */
  return (
    <ErrorBoundary>
      <div
        className="app"
        onTouchStart={pull.onTouchStart}
        onTouchMove={pull.onTouchMove}
        onTouchEnd={pull.onTouchEnd}
      >
        <AppHeader
          authUser={authUser}
          lastUpdatedStr={lastUpdatedStr}
          resolved={resolved}
          toggleTheme={toggleTheme}
          onBack={handleBack}
          onLogout={handleLogout}
          showBack={showBack}
          title={title}
        />

        <main className="app-main" ref={mainRef}>
          {offline && (
            <div className="offline-indicator">
              <span className="offline-icon">✈️</span>
              Tidak ada koneksi internet — data mungkin tidak terbarui
            </div>
          )}
          {pull.pulling && (
            <div
              className="pull-indicator"
              style={{ opacity: Math.min(pull.pullY / 40, 1), height: pull.pullY }}
            >
              {pull.pullY > 40 ? 'Lepaskan untuk segarkan' : 'Tarik ke bawah'}
            </div>
          )}

          <Suspense fallback={listFallback}>
            <Routes>
              <Route path="/" element={
                <PageErrorBoundary>
                  <MarketPage
                    watchlist={watchlist}
                    onToggleWatchlist={toggleWatchlist}
                    onSelectStock={handleSelectStock}
                    handleRefresh={handleRefresh}
                    loading={loading}
                  />
                </PageErrorBoundary>
              } />

              <Route path="/signal" element={
                <PageErrorBoundary>
                  <SignalPage
                    watchlist={watchlist}
                    onToggleWatchlist={toggleWatchlist}
                    onSelectStock={handleSelectStock}
                    handleRefresh={handleRefresh}
                    loading={loading}
                    recommendedStocks={recommendedStocks}
                    onShowMore={openRecommendations}
                  />
                </PageErrorBoundary>
              } />

              <Route path="/news" element={
                <PageErrorBoundary>
                  <NewsPage onSelectStock={handleSelectStock} />
                </PageErrorBoundary>
              } />

              <Route path="/portfolio" element={
                <PageErrorBoundary>
                  <PortfolioPage />
                </PageErrorBoundary>
              } />

              <Route path="/learning" element={
                <PageErrorBoundary>
                  <LearningPage />
                </PageErrorBoundary>
              } />

              <Route path="/accuracy" element={
                <PageErrorBoundary>
                  <AccuracyPage />
                </PageErrorBoundary>
              } />

              <Route path="/report" element={
                <PageErrorBoundary>
                  <Suspense fallback={reportFallback}>
                    <ReportPage />
                  </Suspense>
                </PageErrorBoundary>
              } />

              <Route path="/detail/:symbol" element={
                <PageErrorBoundary>
                  <StockDetailPage />
                </PageErrorBoundary>
              } />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>

        <BottomSheet
          open={recommendationModalOpen}
          onClose={() => setRecommendationModalOpen(false)}
          title="Semua Sinyal"
          subtitle={`${recommendedStocks.length} rekomendasi aktif`}
        >
          {recommendedStocks.length === 0 ? (
            <div className="empty-state">
              <span className="empty-state-icon">📈</span>
              <p className="empty-state-title">Belum ada sinyal aktif</p>
              <p className="empty-state-desc">Sinyal BUY/SELL akan muncul di sini</p>
            </div>
          ) : (
            <div className="bottom-sheet-list">
              {recommendedStocks.map((stock) => (
                <button
                  key={stock.symbol}
                  className="bottom-sheet-item"
                  onClick={() => {
                    lightHaptic();
                    setRecommendationModalOpen(false);
                    handleSelectStock(stock);
                  }}
                >
                  <div className="bottom-sheet-item-meta">
                    <b>{stock.symbol}</b>
                    <span>{displayName(stock, '-')}</span>
                  </div>
                  <SignalBadge signal={stock.signal} strength={stock.signal_strength} />
                </button>
              ))}
            </div>
          )}
        </BottomSheet>

        <InstallPrompt />

        {showBottomNav && <BottomNav />}
      </div>
    </ErrorBoundary>
  );
}
