import { memo } from 'react';
import AccuracyDashboard from '../components/AccuracyDashboard';

/**
 * AccuracyPage — Dashboard akurasi mesin sinyal (per strategi / per saham).
 */
function AccuracyPage() {
  return (
    <div className="page page-enter">
      <AccuracyDashboard />
    </div>
  );
}

export default memo(AccuracyPage);
