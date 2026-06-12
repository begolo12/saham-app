import { useState, useCallback, memo } from 'react';
import Skeleton from './Skeleton';
import { displayName } from '../utils';

function NewsPanel({ news, loading, stocks, onLoadSymbol, onOpenStock }) {
  const [query, setQuery] = useState('');
  const suggestions = (stocks || [])
    .filter(s => query && (s.symbol || '').toUpperCase().includes(query.toUpperCase()))
    .slice(0, 8);
  const groups = news?.items || [];
  const singleItems = news?.symbol ? [news] : groups;
  const sentimentColor = (sentiment) => sentiment === 'POSITIVE' ? '#34C759' : sentiment === 'NEGATIVE' ? '#FF3B30' : '#8E8E93';
  const label = (sentiment) => sentiment === 'POSITIVE' ? 'Positif → tambah bobot BUY' : sentiment === 'NEGATIVE' ? 'Negatif → tambah bobot SELL' : 'Netral';

  const handleSearch = useCallback(() => {
    if (query) onLoadSymbol(query);
  }, [query, onLoadSymbol]);

  if (loading && !news) {
    return (
      <div style={{ padding: '0 16px 24px' }}>
        <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
          <div className="market-summary-header"><h3>Berita & Sentimen</h3></div>
          <div className="skeleton-line w-60 h-md" />
          <div style={{ marginTop: 12 }}><div className="skeleton-line w-full h-lg" /></div>
        </div>
        <Skeleton variant="card" count={3} />
      </div>
    );
  }

  return <div style={{ padding: '0 16px 24px' }}>
    <div className="market-summary" style={{ margin: '0 0 12px 0' }}>
      <div className="market-summary-header"><h3>Berita & Sentimen</h3><span style={{ color: '#8E8E93', fontSize: 11 }}>Google News RSS</span></div>
      <p style={{ color: '#EBEBF5', fontSize: 13, lineHeight: 1.45 }}>Berita positif jadi pertimbangan tambahan BUY. Berita negatif jadi pertimbangan SELL / hindari.</p>
      <div className="news-search-row">
        <input placeholder="Cari kode saham: BBCA, BBRI..." value={query} onChange={e => setQuery(e.target.value.toUpperCase())} />
        <button onClick={handleSearch}>Cari</button>
      </div>
      {suggestions.length > 0 && <div className="news-suggestions">{suggestions.map(st => { const dn = displayName(st, ''); return (<button key={st.symbol} onClick={() => { setQuery(st.symbol); onLoadSymbol(st.symbol); }}>{st.symbol}{dn && <span>{dn}</span>}</button>); })}</div>}
    </div>
    {loading && (
      <div style={{ padding: '20px 0' }}>
        <Skeleton variant="card" count={2} />
      </div>
    )}
    {!loading && singleItems.map((group, idx) => (
      <div className="market-summary news-group" key={group.symbol || `news-${idx}`} style={{ margin: '0 0 12px 0' }}>
        <div className="market-summary-header">
          <h3>{group.symbol || 'Market'}</h3>
          <span style={{ color: sentimentColor(group.sentiment), fontWeight: 800 }}>{label(group.sentiment)}</span>
        </div>
        <p style={{ color: '#8E8E93', fontSize: 12, lineHeight: 1.45 }}>{group.reason}</p>
        <div className="news-score-row">
          <span>Skor {group.sentiment_score || 0}</span><span>+{group.positive_count || 0}</span><span>-{group.negative_count || 0}</span><span>Netral {group.neutral_count || 0}</span>
        </div>
        <div className="news-list">
          {(group.items || []).map((item, idx) => <a key={`${item.url}-${idx}`} className="news-card" href={item.url} target="_blank" rel="noreferrer">
            <div><b>{item.title}</b><p>{item.summary || 'Buka berita untuk detail.'}</p></div>
            <span style={{ color: sentimentColor(item.sentiment) }}>{item.sentiment}</span>
          </a>)}
          {!(group.items || []).length && <p style={{ color: '#8E8E93', fontSize: 13 }}>Belum ada berita relevan.</p>}
        </div>
        {group.symbol && <button className="sort-chip active" onClick={() => onOpenStock({ symbol: group.symbol, name: group.symbol })}>Buka Detail {group.symbol}</button>}
      </div>
    ))}
  </div>;
}

export default memo(NewsPanel);
