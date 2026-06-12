import { memo, Suspense, lazy } from 'react';

// recharts is heavy (~150KB gz) — only load when the user opens /accuracy
const AccuracyDashboard = lazy(() => import('../components/AccuracyDashboard'));

/**
 * AccuracyPage — Dashboard akurasi mesin sinyal (per strategi / per saham).
 */
function AccuracyPage() {
  return (
    <div className="page page-enter">
      <Suspense fallback={<div style={{ padding: '24px 16px' }}>Memuat akurasi...</div>}>
        <AccuracyDashboard />
      </Suspense>
    </div>
  );
}

export default memo(AccuracyPage);
