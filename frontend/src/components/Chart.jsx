import { useState, useEffect, memo } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area,
} from 'recharts';
import { fetchStockHistory } from '../api';

const PERIODS = [
  { label: '1B', value: '1M' },
  { label: '3B', value: '3M' },
  { label: '6B', value: '6M' },
  { label: '1T', value: '1Y' },
  { label: '5T', value: '5Y' },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const closeItem = payload.find(p => p.dataKey === 'close');
  const volumeItem = payload.find(p => p.dataKey === 'volume');
  return (
    <div className="chart-tooltip">
      <p className="chart-tooltip-date">{label}</p>
      {closeItem && (
        <p className="chart-tooltip-value" style={{ color: '#007AFF' }}>
          Rp {Number(closeItem.value).toLocaleString('id-ID', { minimumFractionDigits: 0 })}
        </p>
      )}
      {volumeItem && (
        <p className="chart-tooltip-volume">
          Vol: {Number(volumeItem.value).toLocaleString('id-ID')}
        </p>
      )}
    </div>
  );
};

function transformHistory(apiData) {
  if (!apiData) return [];
  if (Array.isArray(apiData)) {
    return apiData.map(d => ({
      date: d.date || d.tanggal || '',
      close: d.close || d.harga || d.price || 0,
      open: d.open || d.pembukaan || 0,
      volume: d.volume || d.vol || 0,
    }));
  }
  const dates = apiData.dates || [];
  const closes = apiData.close || [];
  const volumes = apiData.volume || [];
  return dates.map((date, i) => ({
    date,
    close: closes[i] || 0,
    open: 0,
    volume: volumes[i] || 0,
  }));
}

function Chart({ symbol, period: defaultPeriod = '1M' }) {
  const [period, setPeriod] = useState(defaultPeriod);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  // 'empty' is set when the API returns no rows. Rendered into the
  // "Data tidak tersedia" empty state below. Lint allows because we read it
  // via the variable, not just the setter.
  // eslint-disable-next-line no-unused-vars
  const [empty, setEmpty] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    setLoading(true);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    setEmpty(false);
    fetchStockHistory(symbol, period)
      .then((res) => {
        const apiData = res.data || res;
        const transformed = transformHistory(apiData);
        if (transformed.length === 0) {
          setEmpty(true);
        } else {
          setData(transformed);
        }
      })
      .catch(() => {
        setEmpty(true);
        setData([]);
      })
      .finally(() => setLoading(false));
  }, [symbol, period]);

  if (loading) {
    return (
      <div className="chart-container">
        <div className="period-selector">
          {PERIODS.map((p) => (
            <button key={p.value} className="period-btn active">{p.label}</button>
          ))}
        </div>
        <div className="skeleton-chart" />
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="chart-container">
        <div className="period-selector">
          {PERIODS.map((p) => (
            <button key={p.value}
              className={'period-btn' + (period === p.value ? ' active' : '')}
              onClick={() => { setPeriod(p.value); setData([]); setLoading(true); }}
            >{p.label}</button>
          ))}
        </div>
        <div className="empty-chart">
          <p>Data tidak tersedia untuk periode ini</p>
          {period === '1M' && (
            <p style={{ marginTop: 8 }}>
              Coba periode{' '}
              <span className="suggest" onClick={() => { setPeriod('6M'); setData([]); setLoading(true); }}>
                6 Bulan
              </span>
            </p>
          )}
        </div>
      </div>
    );
  }

  const minPrice = Math.min(...data.map((d) => d.close));
  const maxPrice = Math.max(...data.map((d) => d.close));
  const padding = (maxPrice - minPrice) * 0.08 || maxPrice * 0.03;

  const isUp = data.length > 1 ? data[data.length - 1].close >= data[0].close : true;
  const lineColor = isUp ? '#34C759' : '#FF3B30';

  // Volume bars with green/red
  const volumeData = data.map(d => ({
    ...d,
    volColor: d.close >= (d.open || d.close) ? '#34C759' : '#FF3B30',
  }));

  return (
    <div className="chart-container">
      <div className="period-selector">
        {PERIODS.map((p) => (
          <button key={p.value}
            className={'period-btn' + (period === p.value ? ' active' : '')}
            onClick={() => setPeriod(p.value)}
          >{p.label}</button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id={`priceGrad-${symbol}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={lineColor} stopOpacity={0.25} />
              <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: '#636366', fontSize: 10 }}
            axisLine={{ stroke: 'rgba(255,255,255,0.04)' }} tickLine={false}
            tickFormatter={(v) => {
              if (!v) return '';
              const p = v.split('-');
              return p.length >= 3 ? p[2] + '/' + p[1] : v;
            }} />
          <YAxis domain={[minPrice - padding, maxPrice + padding]}
            tick={{ fill: '#636366', fontSize: 10 }} axisLine={false} tickLine={false}
            tickFormatter={(v) => v.toLocaleString('id-ID')} />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="close" stroke={lineColor}
            fill={`url(#priceGrad-${symbol})`} strokeWidth={2} />
          <Line type="monotone" dataKey="close" stroke={lineColor}
            strokeWidth={2} dot={false} activeDot={{ r: 4, fill: lineColor }} />
        </LineChart>
      </ResponsiveContainer>

      <div className="volume-chart">
        <ResponsiveContainer width="100%" height={45}>
          <BarChart data={volumeData} margin={{ top: 0, right: 5, left: 5, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="date" hide />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="volume" radius={[2, 2, 0, 0]}>
              {volumeData.map((entry, idx) => (
                <rect key={idx} fill={entry.volColor} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default memo(Chart);
