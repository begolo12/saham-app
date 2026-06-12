import { memo } from 'react';
import StockList from '../components/StockList';
import RecommendationStrip from '../components/RecommendationStrip';
import { useStocksStore } from '../stores';

/**
 * SignalPage — Strip rekomendasi + daftar semua saham tersortir berdasarkan sinyal.
 */
function SignalPage({ watchlist, onToggleWatchlist, onSelectStock, handleRefresh, loading, recommendedStocks, onShowMore }) {
  const { allStocks } = useStocksStore();
  return (
    <div className="page page-enter">
      {recommendedStocks.length > 0 && (
        <RecommendationStrip recommendedStocks={recommendedStocks} onSelectStock={onSelectStock} onShowMore={onShowMore} />
      )}
      <StockList
        stocks={allStocks}
        loading={loading && !allStocks.length}
        onRefresh={handleRefresh}
        onSelectStock={onSelectStock}
        watchlist={watchlist}
        onToggleWatchlist={onToggleWatchlist}
        defaultSort="sinyal"
      />
    </div>
  );
}

export default memo(SignalPage);
