import { memo } from 'react';
import { useNavigate } from 'react-router-dom';
import Skeleton from './Skeleton';

function LearningPanel({ summary, loading, onEvaluate }) {
  const navigate = useNavigate();
  if (loading && !summary) {
    return (
      <div style={{ padding: '0 16px 24px' }}>
        <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
          <div className="market-summary-header">
            <h3>Mesin Belajar Sinyal</h3>
          </div>
          <Skeleton variant="learning-stat" />
        </div>
        <Skeleton variant="card" count={3} />
      </div>
    );
  }

  const recent = summary?.recent || [];
  const bySignal = summary?.by_signal || [];
  return (
    <div style={{ padding: '0 16px 24px' }}>
      <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
        <div className="market-summary-header">
          <h3>Mesin Belajar Sinyal</h3>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              className="sort-chip active"
              onClick={() => navigate('/accuracy')}
              title="Buka dashboard akurasi lengkap"
            >
              Dashboard
            </button>
            <button className="sort-chip active" onClick={onEvaluate} disabled={loading}>
              {loading ? 'Cek...' : 'Evaluasi 30H'}
            </button>
          </div>
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

export default memo(LearningPanel);
