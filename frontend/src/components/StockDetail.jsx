import { useState, useEffect, lazy, Suspense } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import SignalBadge from './SignalBadge';
import Skeleton from './Skeleton';
import { fetchStockDetail, fetchStockRecommendationHistory } from '../api';

// recharts is heavy (~150KB gz) — only load when the detail page renders
const Chart = lazy(() => import('./Chart'));

function fmt(val) {
  if (val === null || val === undefined) return '-';
  return Number(val).toLocaleString('id-ID', { minimumFractionDigits: 2 });
}

function fmtPrice(val) {
  if (val === null || val === undefined) return '-';
  return 'Rp ' + Number(val).toLocaleString('id-ID', { minimumFractionDigits: 0 });
}

function Gauge({ value, label }) {
  const pct = Math.min(Math.max(value || 0, 0), 100);
  const color = pct < 30 ? '#FF3B30' : pct > 70 ? '#34C759' : '#FF9500';
  return (
    <div className="gauge">
      <div className="gauge-bar-track"><div className="gauge-bar-fill" style={{ width: pct + '%', backgroundColor: color }} /></div>
      <div className="gauge-labels"><span className="gauge-value" style={{ color }}>{pct.toFixed(0)}</span><span className="gauge-label">{label}</span></div>
    </div>
  );
}

function FundRow({ label, value }) {
  return <div className="fund-row"><span className="fund-label">{label}</span><span className="fund-value">{value}</span></div>;
}

const TABS = ['Teknikal', 'Fundamental', 'Sinyal', 'Riwayat'];

export default function StockDetail() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('Teknikal');
  const [signalHistory, setSignalHistory] = useState([]);

  useEffect(() => {
    if (!symbol) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    setDetail(null);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    setSignalHistory([]);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    setLoading(true);
    fetchStockDetail(symbol)
      .then((res) => setDetail(res.data || res))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [symbol]);

  useEffect(() => {
    if (activeTab !== 'Riwayat' || !symbol || signalHistory.length) return;
    fetchStockRecommendationHistory(symbol)
      .then((res) => setSignalHistory(res.history || []))
      .catch(() => setSignalHistory([]));
  }, [activeTab, symbol, signalHistory.length]);

  const initialStock = { symbol };
  const d = detail || initialStock;
  const price = d.price ?? 0;
  const changePct = d.change_percent ?? 0;
  const isPositive = changePct >= 0;
  const overallSignal = d.overall_signal || d.signal || 'NEUTRAL';
  const overallStrength = d.overall_strength ?? d.signal_strength ?? 50;
  const overallReasons = d.overall_reasons || d.reasons || [];
  const tech = d.technical || {};
  const fund = d.fundamental || {};
  const techReasons = tech.reasons || [];
  const fundReasons = fund.reasons || [];

  return (
    <div className="stock-detail">
      <div className="detail-hero">
        <h2 className="detail-hero-symbol">{d.symbol}</h2>
        <p className="detail-hero-name">{d.name}</p>
        {d.sector && <span className="detail-hero-sector">{d.sector}</span>}
        <div className="detail-hero-price">{fmtPrice(price)}</div>
        <div className="detail-hero-change" style={{ color: isPositive ? '#34C759' : '#FF3B30' }}>{isPositive ? '+' : ''}{changePct.toFixed(2)}%</div>
        <div className="detail-hero-signal"><SignalBadge signal={overallSignal} strength={overallStrength} large /></div>
        {loading && <p className="detail-loading-note">Memuat analisis lengkap...</p>}
      </div>

      {!d.trade_plan && loading && (
        <div className="detail-section trade-plan-card"><h3 className="section-title">Analisis berjalan</h3><p className="trade-plan-text">Harga dan sinyal awal sudah tampil. Detail teknikal/fundamental sedang dimuat di belakang.</p></div>
      )}

      {d.trade_plan && (
        <div className="detail-section trade-plan-card" style={{ animationDelay: '0.08s' }}>
          <h3 className="section-title">Rencana Trading 7 Hari</h3>
          <div className="trade-plan-grid">
            <div><span>Aksi</span><b>{d.trade_plan.action}</b></div>
            <div><span>Entry</span><b>{fmtPrice(d.trade_plan.entry_price)}</b></div>
            <div><span>Target</span><b style={{ color: '#34C759' }}>{fmtPrice(d.trade_plan.target_price)}</b></div>
            <div><span>Stop</span><b style={{ color: '#FF3B30' }}>{fmtPrice(d.trade_plan.stop_loss)}</b></div>
          </div>
          <p className="trade-plan-text">{d.trade_plan.instruction}</p>
          {d.daily_check && <p className="trade-plan-check">{d.daily_check.status}: {d.daily_check.message}</p>}
        </div>
      )}

      {d.news_sentiment && (
        <div className="detail-section news-detail-card" style={{ animationDelay: '0.09s' }}>
          <h3 className="section-title">Sentimen Berita</h3>
          <p className="decision-summary">{d.news_sentiment.reason}</p>
          <div className="news-score-row"><span>Skor {d.news_sentiment.sentiment_score}</span><span>Positif {d.news_sentiment.positive_count}</span><span>Negatif {d.news_sentiment.negative_count}</span><span>Netral {d.news_sentiment.neutral_count}</span></div>
        </div>
      )}

      <div className="detail-section" style={{ animationDelay: '0.1s' }}>
        <h3 className="section-title">Grafik Harga</h3>
        {detail ? <Suspense fallback={<div className="chart-placeholder">Memuat grafik...</div>}><Chart symbol={d.symbol} /></Suspense> : <div className="chart-placeholder">Grafik dimuat setelah analisis utama siap.</div>}
      </div>

      <div className="detail-tabs">
        {TABS.map((tab) => <button key={tab} className={`detail-tab${activeTab === tab ? ' active' : ''}`} onClick={() => setActiveTab(tab)}>{tab}</button>)}
      </div>

      {activeTab === 'Teknikal' && (
        <div className="detail-section">
          <h3 className="section-title">Analisis Teknikal <SignalBadge signal={tech.signal || 'NEUTRAL'} strength={tech.strength || 50} /></h3>
          <div className="tech-metrics">
            <div className="tech-item"><span className="tech-label">RSI (14)</span><Gauge value={tech.rsi ?? 50} label="RSI" /></div>
            <div className="tech-item"><span className="tech-label">MACD</span><span className="tech-value">{tech.macd_line != null ? tech.macd_line.toFixed(2) : '-'}</span></div>
            <div className="tech-item"><span className="tech-label">SMA 20</span><span className="tech-value">{tech.sma_20 != null ? fmt(tech.sma_20) : '-'}</span></div>
            <div className="tech-item"><span className="tech-label">SMA 50</span><span className="tech-value">{tech.sma_50 != null ? fmt(tech.sma_50) : '-'}</span></div>
          </div>
          <ul className="reason-list">{techReasons.map((r, i) => <li key={i} className="reason-item"><span className="reason-icon">⚡</span><span>{r}</span></li>)}</ul>
        </div>
      )}

      {activeTab === 'Fundamental' && (
        <div className="detail-section">
          <h3 className="section-title">Analisis Fundamental <SignalBadge signal={fund.signal || 'NEUTRAL'} strength={fund.strength || 50} /></h3>
          <div className="fund-metrics">
            <FundRow label="PER" value={fund.pe_ratio != null ? fund.pe_ratio.toFixed(2) + 'x' : '-'} />
            <FundRow label="PBV" value={fund.pbv != null ? fund.pbv.toFixed(2) + 'x' : '-'} />
            <FundRow label="Dividend Yield" value={fund.dividend_yield != null ? fund.dividend_yield.toFixed(2) + '%' : '-'} />
            <FundRow label="EPS" value={fund.eps != null ? fmt(fund.eps) : '-'} />
          </div>
          <ul className="reason-list">{fundReasons.map((r, i) => <li key={i} className="reason-item"><span className="reason-icon">📊</span><span>{r}</span></li>)}</ul>
        </div>
      )}

      {activeTab === 'Sinyal' && (
        <div className="detail-section overall-signal-section">
          <h3 className="section-title">Sinyal Keseluruhan</h3>
          <div className="overall-signal"><SignalBadge signal={overallSignal} strength={overallStrength} large /><p className="overall-strength-text">Kekuatan Sinyal: {overallStrength}/100</p></div>
          {d.decision_summary && <p className="decision-summary">{d.decision_summary}</p>}
          {d.key_drivers?.length > 0 && <><h4 className="mini-title">Kenapa hari ini?</h4><ul className="reason-list compact">{d.key_drivers.map((r, i) => <li key={`driver-${i}`} className="reason-item"><span className="reason-icon">✅</span><span>{r}</span></li>)}</ul></>}
          {d.risk_notes?.length > 0 && <><h4 className="mini-title">Risiko</h4><ul className="reason-list compact">{d.risk_notes.map((r, i) => <li key={`risk-${i}`} className="reason-item"><span className="reason-icon">⚠️</span><span>{r}</span></li>)}</ul></>}
          <ul className="reason-list">{overallReasons.map((r, i) => <li key={i} className="reason-item"><span className="reason-icon">💡</span><span>{r}</span></li>)}</ul>
        </div>
      )}

      {activeTab === 'Riwayat' && (
        <div className="detail-section">
          <h3 className="section-title">Riwayat Rekomendasi</h3>
          {signalHistory.length ? (
            <ul className="reason-list">
              {signalHistory.map((row, i) => (
                <li key={`${row.created_at}-${i}`} className="reason-item" style={{ alignItems: 'flex-start' }}>
                  <span className="reason-icon">{row.is_correct === 1 ? '✅' : row.is_correct === 0 ? '❌' : '⏳'}</span>
                  <span><b style={{ color: '#fff' }}>{row.recommendation}</b> • strength {Math.round(row.strength || 0)} • {fmtPrice(row.price)}<br /><small style={{ color: '#8E8E93' }}>{row.return_pct == null ? 'Menunggu evaluasi 7 hari' : `Return ${row.return_pct}% • ${row.outcome || '-'}`}</small></span>
                </li>
              ))}
            </ul>
          ) : <p style={{ textAlign: 'center', color: '#8E8E93', fontSize: 13 }}>Belum ada riwayat rekomendasi.</p>}
        </div>
      )}
    </div>
  );
}
