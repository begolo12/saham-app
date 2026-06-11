import { useState, useMemo, useRef, useEffect, memo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import StockCard from './StockCard';
import SwipeableRow from './SwipeableRow';
import { searchStocks } from '../api';
import { LIQUIDITY_THRESHOLD } from '../constants';

const ROW_HEIGHT = 96; // tinggi satu kartu saham dengan top row + bottom row (px)
const VIRTUAL_LIST_OFFSET = 360; // header + sort chips + section label + bottom nav (termasuk padding ekstra)

function StockList({ stocks, loading, onSelectStock, watchlist, onToggleWatchlist, defaultSort = 'default' }) {
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [sortBy, setSortBy] = useState(defaultSort);
  const [gridView, setGridView] = useState(false);
  const [liquidOnly, setLiquidOnly] = useState(true);
  const [signalFilter, setSignalFilter] = useState('ALL');
  const [minPotential, setMinPotential] = useState(0);
  const debounceRef = useRef(null);

  // Ref untuk kontainer scroll virtual
  const scrollRef = useRef(null);

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
      result = result.filter((s) => Number(s.volume || s.avg_volume || 0) >= LIQUIDITY_THRESHOLD);
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

  // Virtualizer — hanya aktif di mode daftar (list). Mode grid tidak divirtualisasi
  // karena mengandalkan CSS Grid multi-kolom yang tidak kompatibel dengan position:absolute.
  const virtualizer = useVirtualizer({
    count: gridView ? 0 : filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
    // Dinamis: kalau ada kartu dengan nama panjang (dua baris) atau
    // data ekstra, virtualizer akan menambah tinggi per item.
    measureElement: (el) => el.getBoundingClientRect().height,
  });

  const sortChips = useMemo(() => ([
    { key: 'default', label: 'Semua' },
    { key: 'harga', label: 'Harga' },
    { key: 'perubahan', label: 'Perubahan' },
    { key: 'volume', label: 'Volume' },
    { key: 'potensi', label: 'Potensi' },
    { key: 'sinyal', label: 'Sinyal' },
  ]), []);

  const signalChips = useMemo(() => ['ALL', 'BUY', 'NEUTRAL', 'SELL'], []);

  return (
    <div className="stock-list">
      <div className="stock-list-header">
        <div className="search-bar">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Cari saham..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setSignalFilter('ALL');
            }}
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
        {signalChips.map((sig) => (
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
        <button className={`sort-chip${minPotential === 50 ? ' active' : ''}`} onClick={() => setMinPotential(minPotential === 50 ? 0 : 50)}>
          Potensi ≥50
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
          {gridView ? (
            // Grid view — render biasa, tidak divirtualisasi
            <div className="stock-card-grid grid-view">
              {filtered.map((stock, i) => (
                <StockCard
                  key={stock.symbol}
                  stock={stock}
                  index={i}
                  onClick={onSelectStock}
                  watchlist={watchlist}
                  onToggleWatchlist={onToggleWatchlist}
                  gridView={true}
                />
              ))}
            </div>
          ) : (
            // List view — virtual scrolling
            <div
              ref={scrollRef}
              className="stock-list-virtual"
              style={{
                height: `calc(100vh - ${VIRTUAL_LIST_OFFSET}px)`,
                overflowY: 'auto',
                paddingBottom: 24, // ruang ekstra agar card terakhir tidak tertutup bottom nav
              }}
            >
              <div
                style={{
                  height: `${virtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative',
                }}
              >
                {virtualizer.getVirtualItems().map((virtualItem) => {
                  const stock = filtered[virtualItem.index];
                  if (!stock) return null;
                  const isWatched = watchlist?.includes(stock.symbol);
                  return (
                    <div
                      key={virtualItem.key}
                      data-index={virtualItem.index}
                      ref={virtualizer.measureElement}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        transform: `translateY(${virtualItem.start}px)`,
                      }}
                    >
                      <SwipeableRow
                        rightActive={isWatched}
                        rightLabel={isWatched ? 'Di Watchlist' : 'Watchlist'}
                        leftLabel="Hapus"
                        onSwipeRight={() => {
                          if (!isWatched) onToggleWatchlist?.(stock.symbol);
                        }}
                        onSwipeLeft={() => {
                          if (isWatched) onToggleWatchlist?.(stock.symbol);
                        }}
                      >
                        <StockCard
                          stock={stock}
                          index={virtualItem.index}
                          onClick={onSelectStock}
                          watchlist={watchlist}
                          onToggleWatchlist={onToggleWatchlist}
                          gridView={false}
                        />
                      </SwipeableRow>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default memo(StockList);
