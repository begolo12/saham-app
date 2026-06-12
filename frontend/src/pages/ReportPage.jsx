import { memo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ReportPanel from '../components/ReportPanel';
import { useAuthStore, usePortfolioStore } from '../stores';
import { lightHaptic } from '../utils/haptic';

/**
 * ReportPage — Laporan harian rekomendasi BUY / SELL / Hindari.
 * Compact: cards folded by default, tap to expand.
 */
function ReportPage() {
  const { dailyReport, fetchDailyReport } = usePortfolioStore();
  const { authUser } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (authUser) fetchDailyReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authUser]);

  const handleOpenDetail = (row) => {
    lightHaptic();
    if (row?.symbol) navigate(`/detail/${row.symbol}`);
  };

  return (
    <div className="page page-enter">
      <ReportPanel report={dailyReport} onOpenDetail={handleOpenDetail} />
    </div>
  );
}

export default memo(ReportPage);
