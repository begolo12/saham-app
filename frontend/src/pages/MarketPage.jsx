import { memo } from 'react';
import MarketSummary from '../components/MarketSummary';
import StockList from '../components/StockList';
import { useStocksStore } from '../stores';
import { countSignal } from '../utils';

/**
 * MarketPage — Ringkasan IHSG + daftar saham pilihan (top picks).
 */
function MarketPage({ watchlist, onToggleWatchlist, onSelectStock, handleRefresh, loading }) {
  const { topStocks, allStocks, marketSummary } = useStocksStore();
  const displayStocks = allStocks.length ? allStocks : topStocks;
  const signalStats = {
    beli: countSignal(displayStocks, 'BUY'),
    jual: countSignal(displayStocks, 'SELL'),
    tahan: countSignal(displayStocks, 'NEUTRAL'),
  };

  return (
    <div className="page page-enter">
      {marketSummary && <MarketSummary marketSummary={marketSummary} signalStats={signalStats} />}
      <StockList
        stocks={topStocks}
        loading={loading && !topStocks.length}
        onRefresh={handleRefresh}
        onSelectStock={onSelectStock}
        watchlist={watchlist}
        onToggleWatchlist={onToggleWatchlist}
        defaultSort="default"
      />
    </div>
  );
}

export default memo(MarketPage);
