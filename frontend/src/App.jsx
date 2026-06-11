import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import StockList from './components/StockList';
import SignalBadge from './components/SignalBadge';
import { fetchTopStocks, fetchAllStocks, fetchMarketSummary, fetchLearningSummary, evaluateLearning, fetchPortfolio, savePortfolioPosition, deletePortfolioPosition, fetchDailyReport } from './api';

const StockDetail = lazy(() => import('./components/StockDetail'));

const WATCHLIST_KEY = 'saham_watchlist';

function loadWatchlist() {
  try {
    const stored = localStorage.getItem(WATCHLIST_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function fmtTime(date) {
  if (!date) return '';
  return date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function fmtPrice(price) {
  if (price == null) return '-';
  return 'Rp ' + Number(price).toLocaleString('id-ID', { minimumFractionDigits: 0 });
}

function countSignal(stocks, type) {
  return (stocks || []).filter(s => (s.signal || s.overallSignal) === type).length;
}

const SEGMENTS = ['Laporan', 'Pasar', 'Sinyal', 'Porto', 'Belajar'];

const FALLBACK_STOCKS = [
  { symbol: 'BBCA', name: 'Bank Central Asia Tbk.', price: 10250, change_percent: 1.25, signal: 'BUY', signal_strength: 78, sector: 'Finance' },
  { symbol: 'BBRI', name: 'Bank Rakyat Indonesia Tbk.', price: 5650, change_percent: -0.88, signal: 'HOLD', signal_strength: 45, sector: 'Finance' },
  { symbol: 'TLKM', name: 'Telkom Indonesia Tbk.', price: 3950, change_percent: 2.15, signal: 'BUY', signal_strength: 82, sector: 'Technology' },
  { symbol: 'ASII', name: 'Astra International Tbk.', price: 5450, change_percent: -1.45, signal: 'SELL', signal_strength: 65, sector: 'Consumer' },
  { symbol: 'ADRO', name: 'Adaro Energy Indonesia Tbk.', price: 2850, change_percent: 3.50, signal: 'BUY', signal_strength: 91, sector: 'Energy' },
  { symbol: 'BMRI', name: 'Bank Mandiri Tbk.', price: 7200, change_percent: 0.75, signal: 'BUY', signal_strength: 72, sector: 'Finance' },
  { symbol: 'GOTO', name: 'GoTo Gojek Tokopedia Tbk.', price: 98, change_percent: -2.00, signal: 'SELL', signal_strength: 55, sector: 'Technology' },
  { symbol: 'INDF', name: 'Indofood Sukses Makmur Tbk.', price: 6325, change_percent: 0.32, signal: 'HOLD', signal_strength: 40, sector: 'Consumer' },
];

const FALLBACK_SUMMARY = {
  name: 'IHSG',
  price: 7234.56,
  change_percent: 0.45,
  high_52w: 7800,
  low_52w: 6500,
};


function LearningPanel({ summary, loading, onEvaluate }) {
  const recent = summary?.recent || [];
  const bySignal = summary?.by_signal || [];
  return (
    <div style={{ padding: '0 16px 24px' }}>
      <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
        <div className="market-summary-header">
          <h3>Mesin Belajar Sinyal</h3>
          <button className="sort-chip active" onClick={onEvaluate} disabled={loading}>
            {loading ? 'Cek...' : 'Evaluasi 30H'}
          </button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, paddingTop: 10 }}>
          <div className="learning-stat"><b>{summary?.accuracy ?? 0}%</b><span>Akurasi</span></div>
          <div className="learning-stat"><b>{summary?.evaluated ?? 0}</b><span>Dievaluasi</span></div>
          <div className="learning-stat"><b>{summary?.pending_evaluation ?? 0}</b><span>Menunggu</span></div>
        </div>
        <p style={{ color: '#8E8E93', fontSize: 12, lineHeight: 1.4, marginTop: 12 }}>
          {summary?.rule || 'Rekomendasi dicatat, lalu dicek ulang setelah 30 hari.'}
        </p>
      </div>

      <p className="section-label">Performa per Sinyal</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
        {bySignal.length ? bySignal.map((row) => (
          <div key={row.recommendation} className="signal-card">
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <b style={{ color: '#fff' }}>{row.recommendation}</b>
              <span style={{ color: '#34C759', fontWeight: 700 }}>{row.accuracy}%</span>
            </div>
            <div style={{ color: '#8E8E93', fontSize: 12, marginTop: 6 }}>
              {row.correct}/{row.count} benar • avg return {row.avg_return}%
            </div>
          </div>
        )) : (
          <div className="empty-state" style={{ padding: 24 }}>
            <p className="empty-state-title">Belum ada hasil evaluasi</p>
            <p className="empty-state-desc">Data baru valid setelah sinyal berumur 30 hari.</p>
          </div>
        )}
      </div>

      <p className="section-label">Riwayat Sinyal Terakhir</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {recent.map((row, i) => (
          <div key={`${row.symbol}-${row.created_at}-${i}`} className="signal-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
              <div>
                <b style={{ color: '#fff' }}>{row.symbol}</b>
                <div style={{ color: '#8E8E93', fontSize: 11 }}>{row.recommendation} • strength {Math.round(row.strength || 0)}</div>
              </div>
              <div style={{ textAlign: 'right', color: row.is_correct ? '#34C759' : row.is_correct === 0 ? '#FF3B30' : '#8E8E93', fontWeight: 700 }}>
                {row.return_pct == null ? 'Pending' : `${row.return_pct}%`}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PortfolioPanel({ portfolio, onSave, onDelete }) {
  const [form, setForm] = useState({ symbol: '', qty: '', avg_price: '' });
  const summary = portfolio?.summary || {};
  const positions = portfolio?.positions || [];
  const submit = (e) => {
    e.preventDefault();
    if (!form.symbol || !form.qty || !form.avg_price) return;
    onSave({ symbol: form.symbol, qty: Number(form.qty), avg_price: Number(form.avg_price) });
    setForm({ symbol: '', qty: '', avg_price: '' });
  };
  return <div style={{ padding: '0 16px 24px' }}>
    <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
      <div className="market-summary-header"><h3>Virtual Portfolio</h3><span style={{ color: (summary.total_pnl || 0) >= 0 ? '#34C759' : '#FF3B30', fontWeight: 800 }}>{(summary.total_pnl_pct || 0).toFixed(2)}%</span></div>
      <div className="portfolio-grid">
        <div className="learning-stat"><b>{fmtPrice(summary.total_value || 0)}</b><span>Nilai</span></div>
        <div className="learning-stat"><b>{fmtPrice(summary.total_pnl || 0)}</b><span>P/L</span></div>
        <div className="learning-stat"><b>{summary.win_rate || 0}%</b><span>Win rate</span></div>
      </div>
    </div>
    <form className="portfolio-form" onSubmit={submit}>
      <input placeholder="Kode (BBCA)" value={form.symbol} onChange={e => setForm({ ...form, symbol: e.target.value.toUpperCase() })} />
      <input placeholder="Lot/lembar" type="number" value={form.qty} onChange={e => setForm({ ...form, qty: e.target.value })} />
      <input placeholder="Avg price" type="number" value={form.avg_price} onChange={e => setForm({ ...form, avg_price: e.target.value })} />
      <button>Simpan</button>
    </form>
    <p className="section-label">Posisi</p>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {positions.map(pos => <div className="signal-card" key={pos.symbol}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
          <div><b style={{ color: '#fff' }}>{pos.symbol}</b><div style={{ color: '#8E8E93', fontSize: 12 }}>{pos.qty} @ {fmtPrice(pos.avg_price)} • now {fmtPrice(pos.current_price)}</div></div>
          <div style={{ textAlign: 'right' }}><b style={{ color: pos.pnl >= 0 ? '#34C759' : '#FF3B30' }}>{pos.pnl_pct}%</b><div style={{ color: '#8E8E93', fontSize: 12 }}>{fmtPrice(pos.pnl)}</div></div>
        </div>
        <button className="sort-chip" style={{ marginTop: 10 }} onClick={() => onDelete(pos.symbol)}>Hapus</button>
      </div>)}
      {!positions.length && <div className="empty-state"><p className="empty-state-title">Porto kosong</p><p className="empty-state-desc">Masukkan posisi real app saham kamu di sini.</p></div>}
    </div>
  </div>;
}

function ReportPanel({ report, onSelectStock }) {
  const buys = report?.buy_now || [];
  const sells = report?.sell_or_avoid || [];
  return <div style={{ padding: '0 16px 24px' }}>
    <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
      <div className="market-summary-header"><h3>Laporan Hari Ini</h3><span style={{ color: '#8E8E93', fontSize: 11 }}>7D plan</span></div>
      <p style={{ color: '#EBEBF5', fontSize: 13, lineHeight: 1.45 }}>{report?.headline || 'Mengambil laporan...'}</p>
      {report?.portfolio && <div className="portfolio-grid" style={{ marginTop: 12 }}>
        <div className="learning-stat"><b>{fmtPrice(report.portfolio.total_value || 0)}</b><span>Porto</span></div>
        <div className="learning-stat"><b>{(report.portfolio.total_pnl_pct || 0).toFixed(2)}%</b><span>P/L</span></div>
        <div className="learning-stat"><b>{report.portfolio.win_rate || 0}%</b><span>Win</span></div>
      </div>}
    </div>
    <p className="section-label">BUY sekarang — jual target 7 hari</p>
    {buys.map(s => <div className="signal-card" key={s.symbol} onClick={() => onSelectStock(s)} style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}><b style={{ color: '#fff' }}>{s.symbol}</b><SignalBadge signal={s.signal} strength={s.signal_strength} /></div>
      <div style={{ color: '#8E8E93', fontSize: 12, marginTop: 8 }}>{s.trade_plan?.instruction || 'Cek detail untuk rencana.'}</div>
    </div>)}
    {!buys.length && <div className="empty-state"><p className="empty-state-title">Belum ada BUY kuat</p></div>}
    <p className="section-label">SELL / Hindari</p>
    {sells.map(s => <div className="signal-card" key={s.symbol} onClick={() => onSelectStock(s)} style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}><b style={{ color: '#fff' }}>{s.symbol}</b><SignalBadge signal={s.signal} strength={s.signal_strength} /></div>
      <div style={{ color: '#8E8E93', fontSize: 12, marginTop: 8 }}>{s.trade_plan?.instruction || 'Cek detail untuk rencana.'}</div>
    </div>)}
  </div>;
}

export default function App() {
  const [tab, setTab] = useState('market');
  const [selectedStock, setSelectedStock] = useState(null);
  const [topStocks, setTopStocks] = useState([]);
  const [allStocks, setAllStocks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [watchlist, setWatchlist] = useState(loadWatchlist);
  const [marketSummary, setMarketSummary] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [pulling, setPulling] = useState(false);
  const [pullY, setPullY] = useState(0);
  const [segmentIdx, setSegmentIdx] = useState(0);
  const [segmentTab, setSegmentTab] = useState('Pasar');
  const [learningSummary, setLearningSummary] = useState(null);
  const [learningLoading, setLearningLoading] = useState(false);
  const [portfolio, setPortfolio] = useState(null);
  const [dailyReport, setDailyReport] = useState(null);

  const touchStartY = useRef(0);
  const scrollRef = useRef(0);
  const mainRef = useRef(null);

  // Watchlist persistence
  useEffect(() => {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
  }, [watchlist]);

  const toggleWatchlist = useCallback((symbol) => {
    setWatchlist(prev =>
      prev.includes(symbol) ? prev.filter(s => s !== symbol) : [...prev, symbol]
    );
  }, []);

  const watchlistStocks = allStocks.filter(s => watchlist.includes(s.symbol));
  const signalStats = {
    beli: countSignal(allStocks, 'BUY'),
    jual: countSignal(allStocks, 'SELL'),
    tahan: countSignal(allStocks, 'HOLD'),
  };

  // Fetch top 10 stocks for Market tab — refreshes every 60s
  const fetchTopStocksCb = useCallback(async () => {
    setLoading(true);
    try {
      const json = await fetchTopStocks();
      setTopStocks(json.data || json.stocks || json || []);
      setLastUpdated(new Date());
    } catch {
      setTopStocks(FALLBACK_STOCKS);
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch ALL stocks for Signal tab — called once on mount
  const fetchAllStocksCb = useCallback(async () => {
    try {
      const json = await fetchAllStocks();
      setAllStocks(json.data || json.stocks || json || []);
    } catch {
      // Use topStocks fallback for allStocks too if fetchAll fails
    }
  }, []);

  const fetchMarketSummaryCb = useCallback(async () => {
    try {
      const json = await fetchMarketSummary();
      setMarketSummary(json.data || json);
    } catch {
      setMarketSummary(FALLBACK_SUMMARY);
    }
  }, []);


  const fetchLearningSummaryCb = useCallback(async () => {
    setLearningLoading(true);
    try {
      const json = await fetchLearningSummary();
      setLearningSummary(json.data || json);
    } catch {
      setLearningSummary({ total_records: 0, pending_evaluation: 0, evaluated: 0, accuracy: 0, by_signal: [], recent: [] });
    } finally {
      setLearningLoading(false);
    }
  }, []);

  const handleEvaluateLearning = useCallback(async () => {
    setLearningLoading(true);
    try {
      await evaluateLearning(100);
      await fetchLearningSummaryCb();
    } finally {
      setLearningLoading(false);
    }
  }, [fetchLearningSummaryCb]);

  const fetchPortfolioCb = useCallback(async () => {
    try { setPortfolio(await fetchPortfolio()); } catch { setPortfolio({ positions: [], summary: {} }); }
  }, []);

  const fetchDailyReportCb = useCallback(async () => {
    try { setDailyReport(await fetchDailyReport()); } catch { setDailyReport(null); }
  }, []);

  const savePositionCb = useCallback(async (pos) => {
    const data = await savePortfolioPosition(pos);
    setPortfolio(data);
    fetchDailyReportCb();
  }, [fetchDailyReportCb]);

  const deletePositionCb = useCallback(async (symbol) => {
    const data = await deletePortfolioPosition(symbol);
    setPortfolio(data);
    fetchDailyReportCb();
  }, [fetchDailyReportCb]);

  // Initial fetch: keep first paint fast. Heavy report/learning loads only when tab opened.
  useEffect(() => {
    fetchTopStocksCb();
    fetchMarketSummaryCb();
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 800));
    const idleId = idle(() => {
      fetchAllStocksCb();
      fetchPortfolioCb();
    });
    return () => {
      if (window.cancelIdleCallback) window.cancelIdleCallback(idleId);
      else clearTimeout(idleId);
    };
  }, [fetchTopStocksCb, fetchAllStocksCb, fetchMarketSummaryCb, fetchPortfolioCb]);

  // Market tab refresh every 60s (top stocks + market summary)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchTopStocksCb();
      fetchMarketSummaryCb();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchTopStocksCb, fetchMarketSummaryCb]);

  const handleRefresh = useCallback(() => {
    fetchTopStocksCb();
    fetchMarketSummaryCb();
  }, [fetchTopStocksCb, fetchMarketSummaryCb]);

  const handleSelectStock = useCallback((stock) => {
    setSelectedStock(stock);
    setTab('detail');
  }, []);

  const handleBack = useCallback(() => {
    setSelectedStock(null);
    setTab('market');
  }, []);

  const showDetail = tab === 'detail' && selectedStock;

  const handleSegment = (label) => {
    setSegmentTab(label);
    if (label === 'Laporan') { setTab('report'); setSelectedStock(null); fetchDailyReportCb(); }
    else if (label === 'Pasar') { setTab('market'); setSelectedStock(null); }
    else if (label === 'Watchlist') { setTab('watchlist'); setSelectedStock(null); }
    else if (label === 'Sinyal') { setTab('signal'); setSelectedStock(null); }
    else if (label === 'Porto') { setTab('portfolio'); setSelectedStock(null); fetchPortfolioCb(); }
    else if (label === 'Belajar') { setTab('learning'); setSelectedStock(null); fetchLearningSummaryCb(); }
  };

  const handleTabChange = (newTab) => {
    setTab(newTab);
    setSelectedStock(null);
    if (newTab === 'report') setSegmentTab('Laporan');
    else if (newTab === 'market') setSegmentTab('Pasar');
    else if (newTab === 'watchlist') setSegmentTab('Watchlist');
    else if (newTab === 'signal') setSegmentTab('Sinyal');
    else if (newTab === 'portfolio') setSegmentTab('Porto');
    else if (newTab === 'learning') setSegmentTab('Belajar');
  };

  // Pull-to-refresh
  const handleTouchStart = useCallback((e) => {
    if (mainRef.current) {
      scrollRef.current = mainRef.current.scrollTop;
    }
    touchStartY.current = e.touches[0].clientY;
  }, []);

  const handleTouchMove = useCallback((e) => {
    if (scrollRef.current > 0) return;
    const dy = e.touches[0].clientY - touchStartY.current;
    if (dy > 0) {
      setPulling(true);
      setPullY(Math.min(dy * 0.4, 80));
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (pullY > 40 && !loading) {
      handleRefresh();
    }
    setPulling(false);
    setPullY(0);
  }, [pullY, loading, handleRefresh]);

  const lastUpdatedStr = lastUpdated ? fmtTime(lastUpdated) : '';

  // Determine which stocks to pass to StockList based on active tab
  const activeStocks = tab === 'market' ? topStocks
    : tab === 'signal' ? allStocks
    : tab === 'watchlist' ? watchlistStocks
    : [];

  // Default sort for signal tab
  const defaultSort = tab === 'signal' ? 'sinyal' : 'default';

  return (
    <div className="app"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Large Title Header */}
      <header className="app-header">
        <div className="app-title-wrap">
          <h1 className="app-title">Saham ID</h1>
          <span className="live-dot" />
        </div>
        <div className="header-right">
          {lastUpdatedStr && (
            <span className="last-updated">Diperbarui: {lastUpdatedStr}</span>
          )}
        </div>
      </header>

      {/* Segmented Control */}
      <div className="segmented-control">
        {SEGMENTS.map((label) => (
          <button
            key={label}
            className={`segmented-btn${segmentTab === label ? ' active' : ''}`}
            onClick={() => handleSegment(label)}
          >
            {label}
          </button>
        ))}
      </div>

      <main className="app-main" ref={mainRef}>
        {pulling && (
          <div className="pull-indicator" style={{ opacity: Math.min(pullY / 40, 1), height: pullY }}>
            {pullY > 40 ? 'Lepaskan untuk segarkan' : 'Tarik ke bawah'}
          </div>
        )}

        {showDetail ? (
          <Suspense fallback={<div className="stock-detail"><div className="skeleton-detail"><div className="skeleton-line w-40 h-xl" /><div className="skeleton-line w-25 h-md" /><div className="skeleton-line w-80 h-lg" /></div></div>}>
            <StockDetail stock={selectedStock} onBack={handleBack} />
          </Suspense>
        ) : tab === 'report' ? (
          <ReportPanel report={dailyReport} onSelectStock={handleSelectStock} />
        ) : tab === 'portfolio' ? (
          <PortfolioPanel portfolio={portfolio} onSave={savePositionCb} onDelete={deletePositionCb} />
        ) : tab === 'learning' ? (
          <LearningPanel summary={learningSummary} loading={learningLoading} onEvaluate={handleEvaluateLearning} />
        ) : tab === 'market' || tab === 'signal' || tab === 'watchlist' ? (
          <>
            {/* Market Summary Card — Market tab only */}
            {tab === 'market' && marketSummary && (
              <div className="market-summary">
                <div className="market-summary-header">
                  <h3>Ringkasan Pasar</h3>
                  <div className="signal-stats">
                    <div className="signal-stat">
                      <span className="signal-stat-dot" style={{ background: '#34C759' }} />
                      <span style={{ color: '#34C759' }}>{signalStats.beli}</span>
                    </div>
                    <div className="signal-stat">
                      <span className="signal-stat-dot" style={{ background: '#FF3B30' }} />
                      <span style={{ color: '#FF3B30' }}>{signalStats.jual}</span>
                    </div>
                    <div className="signal-stat">
                      <span className="signal-stat-dot" style={{ background: '#8E8E93' }} />
                      <span style={{ color: '#8E8E93' }}>{signalStats.tahan}</span>
                    </div>
                  </div>
                </div>
                <div className="market-summary-body">
                  <div className="market-index">
                    <span className="market-index-name">{marketSummary.name || 'IHSG'}</span>
                    <span className="market-index-price">
                      {Number(marketSummary.price || 0).toLocaleString('id-ID', { minimumFractionDigits: 2 })}
                    </span>
                    <span className="market-index-change"
                      style={{ color: (marketSummary.change_percent || 0) >= 0 ? '#34C759' : '#FF3B30' }}
                    >
                      {(marketSummary.change_percent || 0) >= 0 ? '+' : ''}
                      {(marketSummary.change_percent || 0).toFixed(2)}%
                    </span>
                  </div>
                  <div className="market-range">
                    <p className="market-range-label">Range 52 Minggu</p>
                    <div className="market-range-bar">
                      <div className="market-range-fill" style={{
                        width: marketSummary.high_52w && marketSummary.low_52w
                          ? `${((marketSummary.price - marketSummary.low_52w) / (marketSummary.high_52w - marketSummary.low_52w)) * 100}%`
                          : '50%'
                      }} />
                    </div>
                    <div className="market-range-values">
                      <span>{marketSummary.low_52w?.toLocaleString('id-ID')}</span>
                      <span>{marketSummary.high_52w?.toLocaleString('id-ID')}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <StockList
              stocks={activeStocks}
              loading={loading}
              onRefresh={handleRefresh}
              onSelectStock={handleSelectStock}
              watchlist={watchlist}
              onToggleWatchlist={toggleWatchlist}
              defaultSort={defaultSort}
            />
          </>
        ) : (
          /* Signal Dashboard — fallback for any other tab */
          <div style={{ padding: '0 16px 16px' }}>
            <p className="section-label" style={{ marginBottom: 12 }}>
              {allStocks.length} Saham Tercatat
            </p>
            <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
              <div className="market-summary-header">
                <h3>Statistik Sinyal</h3>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-around', padding: '8px 0' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#34C759' }}>{signalStats.beli}</div>
                  <div style={{ fontSize: 11, color: '#8E8E93', fontWeight: 500, marginTop: 2 }}>BELI</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#FF3B30' }}>{signalStats.jual}</div>
                  <div style={{ fontSize: 11, color: '#8E8E93', fontWeight: 500, marginTop: 2 }}>JUAL</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 28, fontWeight: 800, color: '#8E8E93' }}>{signalStats.tahan}</div>
                  <div style={{ fontSize: 11, color: '#8E8E93', fontWeight: 500, marginTop: 2 }}>TAHAN</div>
                </div>
              </div>
            </div>

            {/* Top signals */}
            <p className="section-label">Sinyal Terkuat</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {allStocks
                .filter(s => s.signal === 'BUY' || s.signal === 'SELL')
                .sort((a, b) => (b.signal_strength || 0) - (a.signal_strength || 0))
                .slice(0, 5)
                .map((stock, i) => {
                  const change = stock.change_percent ?? 0;
                  const isPos = change >= 0;
                  const isBuy = stock.signal === 'BUY';
                  return (
                    <div
                      key={stock.symbol}
                      className="signal-card"
                      onClick={() => handleSelectStock(stock)}
                      style={{ animationDelay: `${i * 0.06}s`, cursor: 'pointer' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{
                            width: 34, height: 34, borderRadius: 10,
                            background: `linear-gradient(135deg, ${isBuy ? '#34C759' : '#FF3B30'}, ${isBuy ? '#30D158' : '#FF453A'})`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontWeight: 700, fontSize: 14, color: '#fff'
                          }}>
                            {stock.symbol?.[0] || '?'}
                          </div>
                          <div>
                            <span style={{ fontWeight: 700, fontSize: 14, color: '#fff' }}>{stock.symbol}</span>
                            <span style={{ display: 'block', fontSize: 10, color: '#8E8E93', marginTop: 1 }}>{stock.name}</span>
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontWeight: 700, fontSize: 15, color: '#fff' }}>{fmtPrice(stock.price)}</span>
                          <span style={{ display: 'block', fontSize: 11, color: isPos ? '#34C759' : '#FF3B30', fontWeight: 600 }}>
                            {isPos ? '+' : ''}{change.toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              {allStocks.filter(s => s.signal === 'BUY' || s.signal === 'SELL').length === 0 && (
                <div className="empty-state" style={{ padding: '30px 20px' }}>
                  <p className="empty-state-title">Tidak ada sinyal aktif</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

    </div>
  );
}

