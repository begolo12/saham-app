import { memo, useEffect } from 'react';
import PortfolioPanel from '../components/PortfolioPanel';
import AdminUsersPanel from '../components/AdminUsersPanel';
import { useStocksStore, useAuthStore, usePortfolioStore } from '../stores';

/**
 * PortfolioPage — Portofolio virtual user + admin panel untuk superuser.
 */
function PortfolioPage() {
  const { portfolio, fetchPortfolio, savePosition, deletePosition } = usePortfolioStore();
  const { allStocks, topStocks, fetchAllStocks } = useStocksStore();
  const { authUser } = useAuthStore();

  useEffect(() => {
    if (authUser) fetchPortfolio();
    if (!allStocks.length) fetchAllStocks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authUser]);

  return (
    <div className="page page-enter">
      <AdminUsersPanel authUser={authUser} />
      <PortfolioPanel
        portfolio={portfolio}
        onSave={savePosition}
        onDelete={deletePosition}
        stocks={allStocks.length ? allStocks : topStocks}
      />
    </div>
  );
}

export default memo(PortfolioPage);
