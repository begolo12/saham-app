import { memo, useEffect, Suspense, lazy } from 'react';
import Skeleton from '../components/Skeleton';
import { useStocksStore } from '../stores';

// Lazy wrapper — keeps detail chunk out of initial bundle
const StockDetail = lazy(() => import('../components/StockDetail'));

/**
 * StockDetailPage — Halaman detail satu saham + rencana trading 7 hari.
 * Memuat daftar saham kalau belum tersedia (untuk tombol watchlist, dll).
 */
function StockDetailPage() {
  const { fetchAllStocks } = useStocksStore();

  useEffect(() => {
    fetchAllStocks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page page-enter">
      <Suspense fallback={<div className="stock-detail"><Skeleton variant="detail" /></div>}>
        <StockDetail />
      </Suspense>
    </div>
  );
}

export default memo(StockDetailPage);
