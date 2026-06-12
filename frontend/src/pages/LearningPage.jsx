import { memo, useState, useCallback, useEffect } from 'react';
import LearningPanel from '../components/LearningPanel';
import { fetchLearningSummary, evaluateLearning } from '../api';

const EMPTY_SUMMARY = {
  total_records: 0,
  pending_evaluation: 0,
  evaluated: 0,
  accuracy: 0,
  by_signal: [],
  recent: [],
};

/**
 * LearningPage — Self-learning engine: ringkasan + evaluasi manual.
 */
function LearningPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchSummary = useCallback(async () => {
    setLoading(true);
    try {
      const json = await fetchLearningSummary();
      setSummary(json.data || json);
    } catch {
      setSummary(EMPTY_SUMMARY);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleEvaluate = useCallback(async () => {
    setLoading(true);
    try {
      await evaluateLearning(100);
      await fetchSummary();
    } finally {
      setLoading(false);
    }
  }, [fetchSummary]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  return (
    <div className="page page-enter">
      <LearningPanel summary={summary} loading={loading} onEvaluate={handleEvaluate} />
    </div>
  );
}

export default memo(LearningPage);
