import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import StockList from './components/StockList';
import MarketSummary from './components/MarketSummary';
import RecommendationStrip from './components/RecommendationStrip';
import SignalDashboard from './components/SignalDashboard';
import ErrorBoundary from './components/ErrorBoundary';
import PageErrorBoundary from './components/PageErrorBoundary';
import BottomNav from './components/BottomNav';
import FloatingBelajar from './components/FloatingBelajar';
import BottomSheet from './components/BottomSheet';
import InstallPrompt from './components/InstallPrompt';
import Skeleton from './components/Skeleton';
import { fmtTime, countSignal } from './utils';
import { fetchLearningSummary, evaluateLearning, fetchNews } from './api';
import useAuthStore from './stores/authStore';
import useStocksStore from './stores/stocksStore';
import usePortfolioStore from './stores/portfolioStore';
import useTheme from './utils/useTheme';
import SignalBadge from './components/SignalBadge';
import { lightHaptic, mediumHaptic } from './utils/haptic';

const StockDetail = lazy(() => import('./components/StockDetail'));
const ReportPanel = lazy(() => import('./components/ReportPanel'));
const NewsPanel = lazy(() => import('./components/NewsPanel'));
const PortfolioPanel = lazy(() => import('./components/PortfolioPanel'));
const LearningPanel = lazy(() => import('./components/LearningPanel'));
const LoginPage = lazy(() => import('./components/LoginPage'));
const AdminUsersPanel = lazy(() => import('./components/AdminUsersPanel'));
const AccuracyDashboard = lazy(() => import('./components/AccuracyDashboard'));

const WATCHLIST_KEY = 'saham_watchlist';

function loadWatchlist() {
  try { return JSON.parse(localStorage.getItem(WATCHLIST_KEY)) || []; } catch { return []; }
}

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

const fallbackSkeleton = <div style={{ padding: '0 16px' }}><Skeleton variant="card" count={4} /></div>;
const detailFallback = <div className="stock-detail"><Skeleton variant="detail" /></div>;
const reportFallback = <div style={{ padding: '0 16px' }}><Skeleton variant="market-summary" /><Skeleton variant="card" count={3} /></div>;

/* ───────────────────────────── Page components ───────────────────────────── */

/** Market home — market summary + StockList with top stocks */
function MarketPage({ watchlist, onToggleWatchlist, onSelectStock, handleRefresh, loading }) {
  const { topStocks, allStocks, marketSummary } = useStocksStore();
  const displayStocks = allStocks.length ? allStocks : topStocks;
  const signalStats = {
    beli: countSignal(displayStocks, 'BUY'),
    jual: countSignal(displayStocks, 'SELL'),
    tahan: countSignal(displayStocks, 'NEUTRAL'),
  };
  return (
    <div className="page-enter">
      {marketSummary && <MarketSummary marketSummary={marketSummary} signalStats={signalStats} />}
      <StockList
        stocks={topStocks}
        loading={loading && !topStocks.length}
        onRefresh={handleRefresh}
        onSelectStock={onSelectStock}
        watchlist={watchlist}
        onToggleWatchlist={onToggleWatchlist}
        defaultSort="default"
      />
    </div>
  );
}

/** Signal page — recommendation strip + StockList with all stocks, signal sort */
function SignalPage({ watchlist, onToggleWatchlist, onSelectStock, handleRefresh, loading, recommendedStocks, onShowMore }) {
  const { allStocks } = useStocksStore();
  return (
    <div className="page-enter">
      {recommendedStocks.length > 0 && (
        <RecommendationStrip recommendedStocks={recommendedStocks} onSelectStock={onSelectStock} onShowMore={onShowMore} />
      )}
      <StockList
        stocks={allStocks}
        loading={loading && !allStocks.length}
        onRefresh={handleRefresh}
        onSelectStock={onSelectStock}
        watchlist={watchlist}
        onToggleWatchlist={onToggleWatchlist}
        defaultSort="sinyal"
      />
    </div>
  );
}

/** News page */
function NewsPage({ onSelectStock }) {
  const [newsData, setNewsData] = useState(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const { allStocks, topStocks, fetchAllStocks } = useStocksStore();

  const loadNews = useCallback(async (symbol = '') => {
    setNewsLoading(true);
    try { setNewsData(await fetchNews(symbol, 8)); } catch { setNewsData({ items: [] }); }
    finally { setNewsLoading(false); }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { loadNews(); if (!allStocks.length) fetchAllStocks(); }, []);

  return (
    <div className="page-enter">
      <NewsPanel news={newsData} loading={newsLoading} stocks={allStocks.length ? allStocks : topStocks} onLoadSymbol={loadNews} onOpenStock={onSelectStock} />
    </div>
  );
}

/** Portfolio page */
function PortfolioPage() {
  const { portfolio, fetchPortfolio, savePosition, deletePosition } = usePortfolioStore();
  const { allStocks, topStocks, fetchAllStocks } = useStocksStore();
  const { authUser } = useAuthStore();

  useEffect(() => { if (authUser) fetchPortfolio(); if (!allStocks.length) fetchAllStocks(); }, [authUser]);

  return (
    <div className="page-enter">
      <Suspense fallback={fallbackSkeleton}>
        <AdminUsersPanel authUser={authUser} />
        <PortfolioPanel portfolio={portfolio} onSave={savePosition} onDelete={deletePosition} stocks={allStocks.length ? allStocks : topStocks} />
      </Suspense>
    </div>
  );
}

/** Learning page */
function LearningPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    try { const json = await fetchLearningSummary(); setSummary(json.data || json); }
    catch { setSummary({ total_records: 0, pending_evaluation: 0, evaluated: 0, accuracy: 0, by_signal: [], recent: [] }); }
    finally { setLoading(false); }
  }, []);

  const handleEvaluate = useCallback(async () => {
    setLoading(true);
    try { await evaluateLearning(100); await fetchSummary(); }
    finally { setLoading(false); }
  }, [fetchSummary]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchSummary(); }, [fetchSummary]);

  return (
    <div className="page-enter">
      <LearningPanel summary={summary} loading={loading} onEvaluate={handleEvaluate} />
    </div>
  );
}

/** Report page */
function ReportPage() {
  const { dailyReport, fetchDailyReport } = usePortfolioStore();
  const { authUser } = useAuthStore();

  useEffect(() => { if (authUser) fetchDailyReport(); }, [authUser]);

  return (
    <div className="page-enter">
      <Suspense fallback={reportFallback}>
        <ReportPanel report={dailyReport} />
      </Suspense>
    </div>
  );
}

/* ───────────────────────────── App shell ───────────────────────────── */

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { authUser, authChecked, checkSession, logout } = useAuthStore();
  const { allStocks, loading, lastUpdated, fetchTopStocks, fetchMarketSummary } = useStocksStore();
  const { resolved, toggle: toggleTheme } = useTheme();

  // Local UI state
  const [watchlist, setWatchlist] = useState(loadWatchlist);
  const [recommendationModalOpen, setRecommendationModalOpen] = useState(false);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [pulling, setPulling] = useState(false);
  const [pullY, setPullY] = useState(0);
  const touchStartY = useRef(0);
  const scrollRef = useRef(0);
  const mainRef = useRef(null);

  // Offline detection
  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => { window.removeEventListener('online', goOnline); window.removeEventListener('offline', goOffline); };
  }, []);

  // Watchlist persistence
  useEffect(() => { localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist)); }, [watchlist]);

  // Auth check
  useEffect(() => { checkSession(); }, []);

  // Initial data fetch
  useEffect(() => { fetchTopStocks(); fetchMarketSummary(); }, []);

  // Refresh intervals
  useEffect(() => {
    const marketInterval = setInterval(fetchMarketSummary, 30000);
    const stockInterval = setInterval(fetchTopStocks, 60000);
    return () => { clearInterval(marketInterval); clearInterval(stockInterval); };
  }, [fetchTopStocks, fetchMarketSummary]);

  // Derived data
  const lastUpdatedStr = lastUpdated ? fmtTime(lastUpdated) : '';
  const isDetailPage = location.pathname.startsWith('/detail/');
  const isAccuracyPage = location.pathname.startsWith('/accuracy');
  const recommendedStocks = allStocks
    .filter(s => s.signal === 'BUY' || s.signal === 'SELL')
    .sort((a, b) => (b.signal_strength || 0) - (a.signal_strength || 0));

  const handleRefresh = useCallback(() => {
    lightHaptic();
    fetchTopStocks();
    fetchMarketSummary();
  }, [fetchTopStocks, fetchMarketSummary]);

  const handleSelectStock = useCallback((stock) => {
    lightHaptic();
    navigate(`/detail/${stock.symbol}`);
  }, [navigate]);

  const toggleWatchlist = useCallback((symbol) => {
    lightHaptic();
    setWatchlist(prev => prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol]);
  }, []);

  const openRecommendations = useCallback(() => {
    mediumHaptic();
    setRecommendationModalOpen(true);
  }, []);

  // Pull-to-refresh
  const handleTouchStart = useCallback((e) => {
    if (mainRef.current) scrollRef.current = mainRef.current.scrollTop;
    touchStartY.current = e.touches[0].clientY;
  }, []);

  const handleTouchMove = useCallback((e) => {
    if (scrollRef.current > 0) return;
    const dy = e.touches[0].clientY - touchStartY.current;
    if (dy > 0) { setPulling(true); setPullY(Math.min(dy * 0.4, 80)); }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (pullY > 40 && !loading) handleRefresh();
    setPulling(false);
    setPullY(0);
  }, [pullY, loading, handleRefresh]);

  // ── Auth guard ──
  if (!authChecked) return <LoadingScreen />;

  if (!authUser) {
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingScreen />}>
          <Routes>
            <Route path="*" element={<PageErrorBoundary><LoginPage /></PageErrorBoundary>} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    );
  }

  // ── Authenticated app ──
  return (
    <ErrorBoundary>
    <div className="app"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Header */}
      <header className="app-header">
        <div className="app-title-wrap">
          {isAccuracyPage ? (
            <button
              onClick={() => navigate(-1)}
              className="logout-btn"
              style={{ padding: '6px 10px', fontSize: 12, marginRight: 4 }}
              aria-label="Kembali"
            >
              ← Kembali
            </button>
          ) : null}
          <h1 className="app-title">{isAccuracyPage ? 'Akurasi' : 'Saham ID'}</h1>
          {!isAccuracyPage && <span className="live-dot" />}
        </div>
        <div className="header-right">
          <span className="last-updated">{authUser.username}</span>
          {lastUpdatedStr && <span className="last-updated">Diperbarui: {lastUpdatedStr}</span>}
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
          <button className="logout-btn" onClick={() => { lightHaptic(); logout(); navigate('/login'); }}>Keluar</button>
        </div>
      </header>

      <main className="app-main" ref={mainRef}>
        {offline && (
          <div className="offline-indicator">
            <span className="offline-icon">✈️</span>
            Tidak ada koneksi internet — data mungkin tidak terbarui
          </div>
        )}
        {pulling && (
          <div className="pull-indicator" style={{ opacity: Math.min(pullY / 40, 1), height: pullY }}>
            {pullY > 40 ? 'Lepaskan untuk segarkan' : 'Tarik ke bawah'}
          </div>
        )}

        <Suspense fallback={fallbackSkeleton}>
          <Routes>
            <Route path="/" element={
              <PageErrorBoundary>
                <MarketPage watchlist={watchlist} onToggleWatchlist={toggleWatchlist} onSelectStock={handleSelectStock} handleRefresh={handleRefresh} loading={loading} />
              </PageErrorBoundary>
            } />
            <Route path="/signal" element={
              <PageErrorBoundary>
                <SignalPage watchlist={watchlist} onToggleWatchlist={toggleWatchlist} onSelectStock={handleSelectStock} handleRefresh={handleRefresh} loading={loading} recommendedStocks={recommendedStocks} onShowMore={openRecommendations} />
              </PageErrorBoundary>
            } />
            <Route path="/detail/:symbol" element={
              <PageErrorBoundary>
                <Suspense fallback={detailFallback}>
                  <div className="page-enter"><StockDetail /></div>
                </Suspense>
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
                <div className="page-enter">
                  <AccuracyDashboard />
                </div>
              </PageErrorBoundary>
            } />
            <Route path="/report" element={
              <PageErrorBoundary>
                <ReportPage />
              </PageErrorBoundary>
            } />
            <Route path="/admin" element={
              <PageErrorBoundary>
                <AdminUsersPanel authUser={authUser} />
              </PageErrorBoundary>
            } />
            <Route path="*" element={
              <PageErrorBoundary>
                <div className="page-enter">
                  <SignalDashboard allStocks={allStocks} signalStats={{ beli: countSignal(allStocks, 'BUY'), jual: countSignal(allStocks, 'SELL'), tahan: countSignal(allStocks, 'NEUTRAL') }} onSelectStock={handleSelectStock} />
                </div>
              </PageErrorBoundary>
            } />
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
                  <span>{stock.name || stock.sector || '-'}</span>
                </div>
                <SignalBadge signal={stock.signal} strength={stock.signal_strength} />
              </button>
            ))}
          </div>
        )}
      </BottomSheet>

      <InstallPrompt />

      {!isDetailPage && !isAccuracyPage && <BottomNav />}

      <FloatingBelajar onClick={() => navigate('/learning')} />
    </div>
    </ErrorBoundary>
  );
}
