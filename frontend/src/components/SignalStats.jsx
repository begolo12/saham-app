import { memo } from 'react';

/**
 * SignalStats — horizontal BUY / SELL / NEUTRAL dot counters.
 *
 * Props:
 *   @param {{ beli: number, jual: number, tahan: number }} stats
 */
function SignalStats({ stats = { beli: 0, jual: 0, tahan: 0 } }) {
  return (
    <div className="signal-stats">
      <div className="signal-stat">
        <span className="signal-stat-dot" style={{ background: '#34C759' }} />
        <span style={{ color: '#34C759' }}>{stats.beli}</span>
      </div>
      <div className="signal-stat">
        <span className="signal-stat-dot" style={{ background: '#FF3B30' }} />
        <span style={{ color: '#FF3B30' }}>{stats.jual}</span>
      </div>
      <div className="signal-stat">
        <span className="signal-stat-dot" style={{ background: '#8E8E93' }} />
        <span style={{ color: '#8E8E93' }}>{stats.tahan}</span>
      </div>
    </div>
  );
}

export default memo(SignalStats);
