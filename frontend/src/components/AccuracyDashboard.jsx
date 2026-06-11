import { useEffect, useState, useMemo, memo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LabelList,
} from 'recharts';
import { fetchAccuracy, fetchAccuracySummary } from '../api';
import Skeleton from './Skeleton';

/* ─────────────────────────── Helpers ─────────────────────────── */

const SIGNAL_LABEL = { BUY: 'BELI', SELL: 'JUAL', NEUTRAL: 'TAHAN' };
const SIGNAL_COLOR = { BUY: '#34C759', SELL: '#FF3B30', NEUTRAL: '#8E8E93' };

function fmtPct(v, digits = 1) {
  if (v == null || Number.isNaN(v)) return '—';
  return `${Number(v).toFixed(digits)}%`;
}

function fmtNum(v, digits = 2) {
  if (v == null || Number.isNaN(v)) return '—';
  return Number(v).toFixed(digits);
}

/* ─────────────────────────── Sub-components ─────────────────────────── */

/** Big win-rate tile per signal type. */
function WinRateTile({ signal, winRate, count, correct }) {
  const color = SIGNAL_COLOR[signal] || '#8E8E93';
  const label = SIGNAL_LABEL[signal] || signal;
  return (
    <div
      className="learning-stat"
      data-testid={`win-rate-${signal}`}
      style={{ padding: '14px 8px' }}
    >
      <b style={{ color, fontSize: 28 }}>{fmtPct(winRate, 1)}</b>
      <span style={{ marginTop: 8 }}>Win Rate {label}</span>
      <span style={{ marginTop: 4, color: '#636366', fontSize: 10 }}>
        {correct}/{count} benar
      </span>
    </div>
  );
}

/** Stat card with label, value, accent. */
function StatCard({ label, value, unit, color = '#fff', testId }) {
  return (
    <div className="learning-stat" data-testid={testId} style={{ padding: '14px 8px' }}>
      <b style={{ color, fontSize: 22 }}>{value}{unit ? <span style={{ fontSize: 12, color: '#8E8E93', marginLeft: 2 }}>{unit}</span> : null}</b>
      <span style={{ marginTop: 8 }}>{label}</span>
    </div>
  );
}

/** 2x2 confusion matrix (predicted vs actual). */
function ConfusionMatrix({ matrix }) {
  // Expects: { rows: [actual], cols: [predicted], data: [[...]] }
  const rows = matrix?.rows || ['BUY', 'SELL'];
  const cols = matrix?.cols || matrix?.columns || ['BUY', 'SELL'];
  const data = matrix?.data || matrix?.values || [[0, 0], [0, 0]];

  const max = useMemo(() => {
    let m = 0;
    for (const r of data) for (const v of r) if (v > m) m = v;
    return m || 1;
  }, [data]);

  return (
    <div className="market-summary" style={{ margin: '0 0 12px 0' }} data-testid="confusion-matrix">
      <div className="market-summary-header">
        <h3>Confusion Matrix</h3>
        <span style={{ fontSize: 10, color: '#636366' }}>Aktual × Prediksi</span>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%', borderCollapse: 'separate', borderSpacing: 6,
          fontSize: 11, textAlign: 'center',
        }}>
          <thead>
            <tr>
              <th style={{ color: '#636366', fontWeight: 600, padding: 4 }}> </th>
              {cols.map((c) => (
                <th key={c} style={{ color: SIGNAL_COLOR[c] || '#fff', fontWeight: 700, padding: 4 }}>
                  {SIGNAL_LABEL[c] || c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={r}>
                <th style={{ color: SIGNAL_COLOR[r] || '#fff', fontWeight: 700, padding: 4, textAlign: 'right' }}>
                  {SIGNAL_LABEL[r] || r}
                </th>
                {cols.map((c, ci) => {
                  const v = data[ri]?.[ci] ?? 0;
                  const intensity = max > 0 ? v / max : 0;
                  const isDiag = r === c;
                  return (
                    <td
                      key={`${r}-${c}`}
                      style={{
                        background: isDiag
                          ? `rgba(52, 199, 89, ${0.15 + intensity * 0.55})`
                          : `rgba(255, 59, 48, ${0.08 + intensity * 0.35})`,
                        border: `1px solid ${isDiag ? 'rgba(52,199,89,0.4)' : 'rgba(255,59,48,0.3)'}`,
                        borderRadius: 10,
                        padding: '12px 6px',
                        color: '#fff',
                        fontWeight: 700,
                        fontSize: 14,
                      }}
                    >
                      {v}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ display: 'flex', gap: 12, fontSize: 10, color: '#8E8E93', marginTop: 10 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, background: 'rgba(52,199,89,0.5)', borderRadius: 2 }} /> Benar
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 10, height: 10, background: 'rgba(255,59,48,0.3)', borderRadius: 2 }} /> Salah
        </span>
      </div>
    </div>
  );
}

/** Accuracy over time — bar chart for last 12 months. */
function AccuracyOverTime({ data }) {
  const safe = Array.isArray(data) ? data : [];
  if (safe.length === 0) {
    return (
      <div className="market-summary" style={{ margin: '0 0 12px 0' }} data-testid="accuracy-over-time">
        <div className="market-summary-header">
          <h3>Akurasi 12 Bulan</h3>
        </div>
        <div className="empty-state" style={{ padding: 24 }}>
          <p className="empty-state-desc">Belum cukup data historis.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="market-summary" style={{ margin: '0 0 12px 0' }} data-testid="accuracy-over-time">
      <div className="market-summary-header">
        <h3>Akurasi 12 Bulan</h3>
        <span style={{ fontSize: 10, color: '#636366' }}>% benar</span>
      </div>
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer>
          <BarChart data={safe} margin={{ top: 12, right: 6, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: '#636366', fontSize: 10 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.04)' }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: '#636366', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              contentStyle={{
                background: 'rgba(20,20,30,0.95)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 10,
                fontSize: 12,
                color: '#fff',
              }}
              labelStyle={{ color: '#8E8E93', fontSize: 11 }}
              formatter={(v) => [`${Number(v).toFixed(1)}%`, 'Akurasi']}
            />
            <Bar dataKey="accuracy" radius={[6, 6, 0, 0]}>
              {safe.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.accuracy >= 60 ? '#34C759' : entry.accuracy >= 50 ? '#FF9500' : '#FF3B30'}
                />
              ))}
              <LabelList
                dataKey="accuracy"
                position="top"
                formatter={(v) => `${Number(v).toFixed(0)}%`}
                style={{ fill: '#8E8E93', fontSize: 9, fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** A/B test comparison (v1 vs v2 win rate). */
function ABTestCard({ ab }) {
  if (!ab || (!ab.v1 && !ab.v2)) return null;
  const v1 = ab.v1 || {};
  const v2 = ab.v2 || {};
  const v1Rate = v1.win_rate ?? 0;
  const v2Rate = v2.win_rate ?? 0;
  const winner = v2Rate > v1Rate ? 'v2' : v1Rate > v2Rate ? 'v1' : 'tie';
  const lift = v1Rate > 0 ? ((v2Rate - v1Rate) / v1Rate) * 100 : 0;

  return (
    <div className="market-summary" style={{ margin: '0 0 12px 0' }} data-testid="ab-test">
      <div className="market-summary-header">
        <h3>A/B Test Hasil</h3>
        <span style={{ fontSize: 10, color: winner === 'v2' ? '#34C759' : winner === 'v1' ? '#FF9500' : '#8E8E93' }}>
          {winner === 'tie' ? 'Seri' : `Pemenang: ${winner.toUpperCase()}`}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div
          style={{
            padding: 12, borderRadius: 12,
            background: winner === 'v1' ? 'rgba(52,199,89,0.10)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${winner === 'v1' ? 'rgba(52,199,89,0.4)' : 'rgba(255,255,255,0.08)'}`,
          }}
        >
          <div style={{ fontSize: 10, color: '#8E8E93', fontWeight: 600, letterSpacing: 0.5 }}>V1 (BASELINE)</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: '#fff', marginTop: 6 }}>{fmtPct(v1Rate, 1)}</div>
          <div style={{ fontSize: 10, color: '#636366', marginTop: 4 }}>
            {v1.correct ?? 0}/{v1.count ?? 0} benar
          </div>
        </div>
        <div
          style={{
            padding: 12, borderRadius: 12,
            background: winner === 'v2' ? 'rgba(52,199,89,0.10)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${winner === 'v2' ? 'rgba(52,199,89,0.4)' : 'rgba(255,255,255,0.08)'}`,
          }}
        >
          <div style={{ fontSize: 10, color: '#8E8E93', fontWeight: 600, letterSpacing: 0.5 }}>V2 (KANDIDAT)</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: winner === 'v2' ? '#34C759' : '#fff', marginTop: 6 }}>
            {fmtPct(v2Rate, 1)}
          </div>
          <div style={{ fontSize: 10, color: '#636366', marginTop: 4 }}>
            {v2.correct ?? 0}/{v2.count ?? 0} benar
          </div>
        </div>
      </div>
      {Number.isFinite(lift) && Math.abs(lift) > 0.01 && (
        <div
          style={{
            marginTop: 10, fontSize: 11, textAlign: 'center',
            color: lift > 0 ? '#34C759' : '#FF3B30', fontWeight: 600,
          }}
        >
          {lift > 0 ? '▲' : '▼'} {Math.abs(lift).toFixed(1)}% vs baseline
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────── Main ─────────────────────────── */

function normalizeData(payload) {
  // API may wrap in { data: ... } or return raw
  const root = (payload && typeof payload === 'object') ? (payload.data ?? payload) : {};
  return {
    bySignal: root.by_signal || root.bySignal || [],
    metrics: root.metrics || root.stats || {},
    monthly: root.monthly || root.accuracy_over_time || root.timeseries || [],
    matrix: root.confusion_matrix || root.matrix || null,
    ab: root.ab_test || root.abTest || root.ab || null,
    period: root.period || root.window || '30H',
    updatedAt: root.updated_at || root.generated_at || null,
  };
}

function AccuracyDashboard() {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch both — summary is cheap, full payload drives the dashboard
        const [full, summary] = await Promise.all([
          fetchAccuracy().catch((e) => { throw e; }),
          fetchAccuracySummary().catch(() => null),
        ]);
        if (cancelled) return;
        const raw = full?.data ?? full ?? {};
        // Merge summary metrics if main payload lacks them
        const sum = summary?.data ?? summary;
        if (sum && typeof sum === 'object') {
          raw.metrics = { ...(sum.metrics || sum), ...(raw.metrics || {}) };
        }
        setPayload(raw);
      } catch (e) {
        if (cancelled) return;
        setError(e?.message || 'Gagal memuat data akurasi');
        setPayload({});
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const data = useMemo(() => normalizeData(payload), [payload]);

  const bySignal = data.bySignal || [];
  const buy = bySignal.find((r) => r.recommendation === 'BUY' || r.signal === 'BUY') || {};
  const sell = bySignal.find((r) => r.recommendation === 'SELL' || r.signal === 'SELL') || {};
  const neutral = bySignal.find((r) => r.recommendation === 'NEUTRAL' || r.signal === 'NEUTRAL') || {};

  const sharpe = data.metrics.sharpe_ratio ?? data.metrics.sharpe ?? null;
  const avgReturn = data.metrics.avg_return ?? data.metrics.avgReturn ?? null;
  const maxDD = data.metrics.max_drawdown ?? data.metrics.maxDrawdown ?? null;
  const total = data.metrics.total ?? data.metrics.total_records ?? null;

  const hasAnyData = bySignal.length > 0
    || (data.monthly && data.monthly.length > 0)
    || data.matrix
    || sharpe != null
    || avgReturn != null;

  if (loading && !payload) {
    return (
      <div style={{ padding: '0 16px 24px' }} data-testid="accuracy-loading">
        <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
          <div className="market-summary-header"><h3>Akurasi Sinyal</h3></div>
          <Skeleton variant="learning-stat" />
        </div>
        <Skeleton variant="card" count={3} />
      </div>
    );
  }

  return (
    <div style={{ padding: '0 16px 24px' }} className="page-enter" data-testid="accuracy-dashboard">
      {/* Header */}
      <div className="market-summary" style={{ margin: '12px 0 12px 0' }}>
        <div className="market-summary-header">
          <h3>Akurasi Sinyal</h3>
          <span style={{ fontSize: 10, color: '#636366' }}>
            {data.updatedAt ? `Update ${new Date(data.updatedAt).toLocaleDateString('id-ID')}` : `Periode ${data.period}`}
          </span>
        </div>
        <p style={{ color: '#8E8E93', fontSize: 12, lineHeight: 1.4, marginTop: 4 }}>
          Performa rekomendasi BUY/SELL dievaluasi terhadap pergerakan harga aktual.
        </p>
        {error && !hasAnyData && (
          <p style={{ color: '#FF3B30', fontSize: 12, marginTop: 8 }}>⚠ {error}</p>
        )}
      </div>

      {/* Win rate tiles per signal */}
      <p className="section-label">Win Rate per Sinyal</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        <WinRateTile signal="BUY" winRate={buy.accuracy ?? buy.win_rate ?? 0} count={buy.count ?? 0} correct={buy.correct ?? 0} />
        <WinRateTile signal="SELL" winRate={sell.accuracy ?? sell.win_rate ?? 0} count={sell.count ?? 0} correct={sell.correct ?? 0} />
        <WinRateTile signal="NEUTRAL" winRate={neutral.accuracy ?? neutral.win_rate ?? 0} count={neutral.count ?? 0} correct={neutral.correct ?? 0} />
      </div>

      {/* Risk / return stat cards */}
      <p className="section-label">Metrik Risiko &amp; Return</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
        <StatCard
          label="Sharpe Ratio"
          value={sharpe != null ? fmtNum(sharpe, 2) : '—'}
          color={sharpe == null ? '#fff' : sharpe >= 1 ? '#34C759' : sharpe >= 0 ? '#FF9500' : '#FF3B30'}
          testId="stat-sharpe"
        />
        <StatCard
          label="Avg Return"
          value={avgReturn != null ? fmtNum(avgReturn, 2) : '—'}
          unit="%"
          color={avgReturn == null ? '#fff' : avgReturn >= 0 ? '#34C759' : '#FF3B30'}
          testId="stat-avg-return"
        />
        <StatCard
          label="Max Drawdown"
          value={maxDD != null ? fmtNum(Math.abs(maxDD), 2) : '—'}
          unit="%"
          color={maxDD == null ? '#fff' : '#FF3B30'}
          testId="stat-max-dd"
        />
      </div>

      {/* Accuracy over time */}
      <p className="section-label">Akurasi Historis</p>
      <AccuracyOverTime data={data.monthly} />

      {/* Confusion matrix */}
      <p className="section-label">Confusion Matrix</p>
      {data.matrix ? (
        <ConfusionMatrix matrix={data.matrix} />
      ) : (
        <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
          <div className="empty-state" style={{ padding: 24 }}>
            <p className="empty-state-desc">Belum ada data confusion matrix.</p>
          </div>
        </div>
      )}

      {/* A/B test */}
      {data.ab && <ABTestCard ab={data.ab} />}

      {/* Summary footer */}
      {total != null && (
        <div style={{ textAlign: 'center', color: '#636366', fontSize: 11, marginTop: 8 }}>
          {total.toLocaleString('id-ID')} sinyal dievaluasi
        </div>
      )}
    </div>
  );
}

export default memo(AccuracyDashboard);
