import { useState, useEffect, useRef, memo } from 'react';

const SIGNAL_ICONS = { BUY: '▲', SELL: '▼', HOLD: '◆' };
const SIGNAL_LABELS = { BUY: 'BELI', SELL: 'JUAL', HOLD: 'TAHAN' };
const COLORS = {
  BUY: { bg: 'rgba(52,199,89,0.12)', text: '#34C759', border: 'rgba(52,199,89,0.3)' },
  SELL: { bg: 'rgba(255,59,48,0.12)', text: '#FF3B30', border: 'rgba(255,59,48,0.3)' },
  HOLD: { bg: 'rgba(142,142,147,0.12)', text: '#8E8E93', border: 'rgba(142,142,147,0.3)' },
};

function SignalRing({ strength, color, size = 28 }) {
  const r = (size - 4) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(Math.max(strength || 0, 0), 100);
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="signal-ring">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none"
        stroke={color} strokeWidth="3"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
    </svg>
  );
}

function SignalBadge({ signal, strength, large }) {
  const c = COLORS[signal] || COLORS.HOLD;
  const [pulse, setPulse] = useState(false);
  const prevRef = useRef(signal);

  useEffect(() => {
    if (prevRef.current !== signal) {
      setPulse(true);
      const t = setTimeout(() => setPulse(false), 600);
      prevRef.current = signal;
      return () => clearTimeout(t);
    }
  }, [signal]);

  return (
    <div className={`signal-badge${pulse ? ' pulse' : ''}${large ? ' signal-badge-large' : ''}`}
      style={large ? { flexDirection: 'column', alignItems: 'center', gap: 12 } : {}}>
      <span
        className="signal-badge-label"
        style={{
          background: c.bg,
          color: c.text,
          border: `1px solid ${c.border}`,
          ...(large ? { fontSize: 18, padding: '8px 28px', borderRadius: 12 } : {}),
        }}
      >
        <span className="signal-badge-icon">{SIGNAL_ICONS[signal] || '◆'}</span>
        {SIGNAL_LABELS[signal] || 'TAHAN'}
      </span>
      <div className="signal-ring-wrap" style={large ? { flexDirection: 'column', alignItems: 'center', gap: 6 } : {}}>
        <SignalRing strength={strength} color={c.text} size={large ? 48 : 28} />
        {large && (
          <span style={{ fontSize: 12, color: c.text, fontWeight: 600 }}>
            {strength ?? 0}/100
          </span>
        )}
      </div>
    </div>
  );
}

export default memo(SignalBadge);
