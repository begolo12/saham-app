import { memo, useEffect } from 'react';
import ReportPanel from '../components/ReportPanel';
import { useAuthStore, usePortfolioStore } from '../stores';

/**
 * ReportPage — Laporan harian rekomendasi BUY / SELL / Hindari.
 */
function ReportPage() {
  const { dailyReport, fetchDailyReport } = usePortfolioStore();
  const { authUser } = useAuthStore();

  useEffect(() => {
    if (authUser) fetchDailyReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authUser]);

  return (
    <div className="page page-enter">
      <ReportPanel report={dailyReport} />
    </div>
  );
}

export default memo(ReportPage);
