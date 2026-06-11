import { useState, useMemo, useRef, useEffect } from 'react';
import StockCard from './StockCard';
import { searchStocks } from '../api';

export default function StockList({ stocks, loading, onRefresh, onSelectStock, watchlist, onToggleWatchlist, defaultSort = 'default' }) {
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [sortBy, setSortBy] = useState(defaultSort);
  const [gridView, setGridView] = useState(false);
  const [liquidOnly, setLiquidOnly] = useState(false);
  const [signalFilter, setSignalFilter] = useState('ALL');
  const [minPotential, setMinPotential] = useState(0);
  const debounceRef = useRef(null);

  // Reset sort when defaultSort prop changes (tab switch)
  useEffect(() => {
    setSortBy(defaultSort);
  }, [defaultSort]);

  // Debounced API search
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    const q = search.trim();
    if (!q) {
      setSearchResults(null);
      setSearching(false);
      return;
    }

    setSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const json = await searchStocks(q);
        const results = json.data || json.stocks || json || [];
        setSearchResults(Array.isArray(results) ? results : []);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [search]);

  const filtered = useMemo(() => {
    const source = searchResults !== null ? searchResults : (stocks || []);
    let result = [...source];

    // If using local stocks (no API search), apply local filter
    if (searchResults === null && search) {
      const q = search.toLowerCase();
      result = result.filter(
        (s) =>
          (s.symbol || '').toLowerCase().includes(q) ||
          (s.name || '').toLowerCase().includes(q) ||
          (s.sector || '').toLowerCase().includes(q)
      );
    }

    if (signalFilter !== 'ALL') {
      result = result.filter((s) => (s.signal || s.overall_signal || s.overallSignal) === signalFilter);
    }
    if (liquidOnly) {
      result = result.filter((s) => Number(s.volume || s.avg_volume || 0) >= 500000);
    }
    if (minPotential > 0) {
      result = result.filter((s) => Number(s.potential_score || 0) >= minPotential);
    }

    switch (sortBy) {
      case 'harga':
        result.sort((a, b) => (b.price || 0) - (a.price || 0));
        break;
      case 'perubahan':
        result.sort((a, b) => Math.abs(b.change_percent || 0) - Math.abs(a.change_percent || 0));
        break;
      case 'sinyal':
        result.sort((a, b) => (b.signal_strength || b.overall_strength || 0) - (a.signal_strength || a.overall_strength || 0));
        break;
      case 'volume':
        result.sort((a, b) => (b.volume || b.avg_volume || 0) - (a.volume || a.avg_volume || 0));
        break;
      case 'potensi':
        result.sort((a, b) => (b.potential_score || 0) - (a.potential_score || 0));
        break;
      default:
        break;
    }
    return result;
  }, [stocks, search, searchResults, sortBy, signalFilter, liquidOnly, minPotential]);

  const sortChips = [
    { key: 'default', label: 'Semua' },
    { key: 'harga', label: 'Harga' },
    { key: 'perubahan', label: 'Perubahan' },
    { key: 'volume', label: 'Volume' },
    { key: 'potensi', label: 'Potensi' },
    { key: 'sinyal', label: 'Sinyal' },
  ];

  return (
    <div className="stock-list">
      <div className="stock-list-header">
        <div className="search-bar">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Cari saham..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="search-input"
          />
        </div>
        <div className="view-toggle">
          <button
            className={`view-toggle-btn${!gridView ? ' active' : ''}`}
            onClick={() => setGridView(false)}
            title="Tampilan daftar"
          >
            ☰
          </button>
          <button
            className={`view-toggle-btn${gridView ? ' active' : ''}`}
            onClick={() => setGridView(true)}
            title="Tampilan grid"
          >
            ▦
          </button>
        </div>
      </div>

      <div className="sort-chips">
        {sortChips.map((chip) => (
          <button
            key={chip.key}
            className={`sort-chip${sortBy === chip.key ? ' active' : ''}`}
            onClick={() => setSortBy(chip.key)}
          >
            {chip.label}
          </button>
        ))}
      </div>

      <div className="sort-chips" style={{ marginTop: 8 }}>
        {['ALL', 'BUY', 'NEUTRAL', 'SELL'].map((sig) => (
          <button
            key={sig}
            className={`sort-chip${signalFilter === sig ? ' active' : ''}`}
            onClick={() => setSignalFilter(sig)}
          >
            {sig === 'ALL' ? 'Semua Sinyal' : sig}
          </button>
        ))}
        <button
          className={`sort-chip${liquidOnly ? ' active' : ''}`}
          onClick={() => setLiquidOnly((v) => !v)}
        >
          Likuid saja
        </button>
      </div>

      <div className="sort-chips" style={{ marginTop: 8 }}>
        <button className={`sort-chip${minPotential === 60 ? ' active' : ''}`} onClick={() => setMinPotential(minPotential === 60 ? 0 : 60)}>
          Potensi ≥60
        </button>
      </div>

      {loading ? (
        <div className="skeleton-list">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton-card">
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <div className="skeleton-line" style={{ width: 38, height: 38, borderRadius: 10 }} />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <div className="skeleton-line w-30 h-md" />
                  <div className="skeleton-line w-50 h-sm" />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : searching ? (
        <div className="empty-state">
          <span className="empty-state-icon">🔍</span>
          <p className="empty-state-title">Mencari...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state-icon">🔍</span>
          <p className="empty-state-title">
            {search
              ? `Tidak ada hasil untuk "${search}"`
              : 'Tidak ada saham ditemukan'}
          </p>
          <p className="empty-state-desc">
            {search ? 'Coba gunakan kata kunci lain' : 'Belum ada saham di daftar ini'}
          </p>
        </div>
      ) : (
        <>
          <p className="section-label">{filtered.length} Saham Tercatat</p>
          <div className={`stock-card-grid ${gridView ? 'grid-view' : 'list-view'}`}>
            {filtered.map((stock, i) => (
              <StockCard
                key={stock.symbol}
                stock={stock}
                index={i}
                onClick={onSelectStock}
                watchlist={watchlist}
                onToggleWatchlist={onToggleWatchlist}
                gridView={gridView}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

