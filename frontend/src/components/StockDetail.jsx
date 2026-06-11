import { useState, useEffect } from 'react';
import SignalBadge from './SignalBadge';
import Chart from './Chart';
import { fetchStockDetail, fetchStockRecommendationHistory } from '../api';

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

export default function StockDetail({ stock, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('Teknikal');
  const [history, setHistory] = useState([]);
  const [signalHistory, setSignalHistory] = useState([]);

  useEffect(() => {
    if (!stock?.symbol) return;
    setLoading(true);
    fetchStockDetail(stock.symbol)
      .then((res) => setDetail(res.data || res))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
    fetchStockRecommendationHistory(stock.symbol)
      .then((res) => setSignalHistory(res.history || []))
      .catch(() => setSignalHistory([]));
  }, [stock?.symbol]);

  const d = detail || stock || {};
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

  if (loading) {
    return (
      <div className="stock-detail">
        <button className="detail-back" onClick={onBack}><span className="detail-back-arrow">←</span> Kembali</button>
        <div className="skeleton-detail"><div className="skeleton-line w-40 h-xl" /><div className="skeleton-line w-full h-xl" /></div>
      </div>
    );
  }

  return (
    <div className="stock-detail">
      <button className="detail-back" onClick={onBack}><span className="detail-back-arrow">←</span> Kembali</button>

      <div className="detail-hero">
        <h2 className="detail-hero-symbol">{d.symbol}</h2>
        <p className="detail-hero-name">{d.name}</p>
        {d.sector && <span className="detail-hero-sector">{d.sector}</span>}
        <div className="detail-hero-price">{fmtPrice(price)}</div>
        <div className="detail-hero-change" style={{ color: isPositive ? '#34C759' : '#FF3B30' }}>{isPositive ? '+' : ''}{changePct.toFixed(2)}%</div>
        <div className="detail-hero-signal"><SignalBadge signal={overallSignal} strength={overallStrength} large /></div>
      </div>

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

      <div className="detail-section" style={{ animationDelay: '0.1s' }}>
        <h3 className="section-title">Grafik Harga</h3>
        <Chart symbol={d.symbol} />
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
                  <span><b style={{ color: '#fff' }}>{row.recommendation}</b> • strength {Math.round(row.strength || 0)} • {fmtPrice(row.price)}<br /><small style={{ color: '#8E8E93' }}>{row.return_pct == null ? 'Menunggu evaluasi 30 hari' : `Return ${row.return_pct}% • ${row.outcome || '-'}`}</small></span>
                </li>
              ))}
            </ul>
          ) : <p style={{ textAlign: 'center', color: '#8E8E93', fontSize: 13 }}>Belum ada riwayat rekomendasi.</p>}
        </div>
      )}
    </div>
  );
}
