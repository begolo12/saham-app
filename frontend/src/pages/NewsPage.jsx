import { memo, useState, useCallback, useEffect } from 'react';
import NewsPanel from '../components/NewsPanel';
import { fetchNews } from '../api';
import { useStocksStore } from '../stores';

/**
 * NewsPage — Feed berita pasar + filter per saham.
 */
function NewsPage({ onSelectStock }) {
  const [newsData, setNewsData] = useState(null);
  const [newsLoading, setNewsLoading] = useState(false);
  const { allStocks, topStocks, fetchAllStocks } = useStocksStore();

  const loadNews = useCallback(async (symbol = '') => {
    setNewsLoading(true);
    try {
      setNewsData(await fetchNews(symbol, 8));
    } catch {
      setNewsData({ items: [] });
    } finally {
      setNewsLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    loadNews();
    if (!allStocks.length) fetchAllStocks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page page-enter">
      <NewsPanel
        news={newsData}
        loading={newsLoading}
        stocks={allStocks.length ? allStocks : topStocks}
        onLoadSymbol={loadNews}
        onOpenStock={onSelectStock}
      />
    </div>
  );
}

export default memo(NewsPage);
