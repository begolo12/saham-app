import { memo } from 'react';
import SignalBadge from './SignalBadge';
import { fmtPrice } from '../utils';
import Skeleton from './Skeleton';

function ReportPanel({ report }) {
  if (!report) {
    return (
      <div style={{ padding: '0 16px 24px' }}>
        <Skeleton variant="market-summary" />
        <p className="section-label">BUY sekarang — jual target 7 hari</p>
        <Skeleton variant="card" count={3} />
        <p className="section-label">SELL / Hindari</p>
        <Skeleton variant="card" count={2} />
      </div>
    );
  }

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
    {buys.map(s => <div className="signal-card" key={s.symbol} style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}><b style={{ color: '#fff' }}>{s.symbol}</b><SignalBadge signal={s.signal} strength={s.signal_strength} /></div>
      <div style={{ color: '#8E8E93', fontSize: 12, marginTop: 8 }}>{s.trade_plan?.instruction || 'Cek detail untuk rencana.'}</div>
    </div>)}
    {!buys.length && <div className="empty-state"><p className="empty-state-title">Belum ada BUY kuat</p></div>}
    <p className="section-label">SELL / Hindari</p>
    {sells.map(s => <div className="signal-card" key={s.symbol} style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}><b style={{ color: '#fff' }}>{s.symbol}</b><SignalBadge signal={s.signal} strength={s.signal_strength} /></div>
      <div style={{ color: '#8E8E93', fontSize: 12, marginTop: 8 }}>{s.trade_plan?.instruction || 'Cek detail untuk rencana.'}</div>
    </div>)}
  </div>;
}

export default memo(ReportPanel);
