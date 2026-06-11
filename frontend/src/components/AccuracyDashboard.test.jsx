import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import AccuracyDashboard from './AccuracyDashboard';
import { fetchAccuracy, fetchAccuracySummary } from '../api';

vi.mock('../api', () => ({
  fetchAccuracy: vi.fn(),
  fetchAccuracySummary: vi.fn(),
}));

const SAMPLE = {
  by_signal: [
    { recommendation: 'BUY', accuracy: 62.5, count: 40, correct: 25, avg_return: 1.8 },
    { recommendation: 'SELL', accuracy: 55.0, count: 20, correct: 11, avg_return: -0.5 },
    { recommendation: 'NEUTRAL', accuracy: 80.0, count: 10, correct: 8, avg_return: 0.1 },
  ],
  metrics: {
    sharpe_ratio: 1.42,
    avg_return: 2.1,
    max_drawdown: -8.5,
    total: 70,
  },
  monthly: [
    { label: 'Jul', accuracy: 50 },
    { label: 'Agu', accuracy: 55 },
    { label: 'Sep', accuracy: 60 },
    { label: 'Okt', accuracy: 65 },
    { label: 'Nov', accuracy: 70 },
    { label: 'Des', accuracy: 68 },
  ],
  confusion_matrix: {
    rows: ['BUY', 'SELL'],
    cols: ['BUY', 'SELL'],
    data: [[25, 15], [9, 11]],
  },
  ab_test: {
    v1: { win_rate: 55, count: 100, correct: 55 },
    v2: { win_rate: 62, count: 100, correct: 62 },
  },
  period: '30H',
  updated_at: '2026-06-01T00:00:00Z',
};

describe('AccuracyDashboard', () => {
  beforeEach(() => {
    vi.mocked(fetchAccuracy).mockReset();
    vi.mocked(fetchAccuracySummary).mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders win rate numbers per signal type', async () => {
    vi.mocked(fetchAccuracy).mockResolvedValue({ data: SAMPLE });
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('win-rate-BUY')).toBeInTheDocument();
    });

    const buy = screen.getByTestId('win-rate-BUY');
    const sell = screen.getByTestId('win-rate-SELL');
    const neutral = screen.getByTestId('win-rate-NEUTRAL');

    expect(buy).toHaveTextContent('62.5%');
    expect(buy).toHaveTextContent('25/40');

    expect(sell).toHaveTextContent('55.0%');
    expect(sell).toHaveTextContent('11/20');

    expect(neutral).toHaveTextContent('80.0%');
    expect(neutral).toHaveTextContent('8/10');
  });

  it('renders risk/return stat cards (Sharpe, avg return, max drawdown)', async () => {
    vi.mocked(fetchAccuracy).mockResolvedValue({ data: SAMPLE });
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('stat-sharpe')).toBeInTheDocument();
    });

    expect(screen.getByTestId('stat-sharpe')).toHaveTextContent('1.42');
    expect(screen.getByTestId('stat-avg-return')).toHaveTextContent('2.10');
    expect(screen.getByTestId('stat-max-dd')).toHaveTextContent('8.50');
  });

  it('renders accuracy over time chart with monthly data', async () => {
    vi.mocked(fetchAccuracy).mockResolvedValue({ data: SAMPLE });
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('accuracy-over-time')).toBeInTheDocument();
    });

    // The chart container should exist (recharts renders inside)
    const chart = screen.getByTestId('accuracy-over-time');
    expect(chart).toBeInTheDocument();

    // Period label is rendered
    expect(chart).toHaveTextContent('Akurasi 12 Bulan');

    // The ResponsiveContainer wrapper class is used by recharts.
    // (jsdom cannot compute layout dimensions, so the inner svg may not
    // render — but the outer container must be present in the DOM.)
    expect(chart.querySelector('.recharts-responsive-container')).toBeInTheDocument();
  });

  it('renders confusion matrix with 2x2 cells', async () => {
    vi.mocked(fetchAccuracy).mockResolvedValue({ data: SAMPLE });
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('confusion-matrix')).toBeInTheDocument();
    });

    const cm = screen.getByTestId('confusion-matrix');
    expect(cm).toHaveTextContent('25');
    expect(cm).toHaveTextContent('15');
    expect(cm).toHaveTextContent('9');
    expect(cm).toHaveTextContent('11');
    expect(cm).toHaveTextContent('Aktual × Prediksi');
  });

  it('renders A/B test comparison when available', async () => {
    vi.mocked(fetchAccuracy).mockResolvedValue({ data: SAMPLE });
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('ab-test')).toBeInTheDocument();
    });

    const ab = screen.getByTestId('ab-test');
    expect(ab).toHaveTextContent('V1 (BASELINE)');
    expect(ab).toHaveTextContent('V2 (KANDIDAT)');
    expect(ab).toHaveTextContent('55.0%');
    expect(ab).toHaveTextContent('62.0%');
    expect(ab).toHaveTextContent('Pemenang: V2');
  });

  it('handles empty data without crashing', async () => {
    vi.mocked(fetchAccuracy).mockResolvedValue({ data: {} });
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    // Wait for fetch to settle (loading -> loaded)
    await waitFor(() => {
      expect(screen.queryByTestId('accuracy-loading')).not.toBeInTheDocument();
    });

    // Dashboard container still renders
    expect(screen.getByTestId('accuracy-dashboard')).toBeInTheDocument();

    // Win-rate tiles still mount with 0% defaults (not crashing)
    expect(screen.getByTestId('win-rate-BUY')).toHaveTextContent('0.0%');
    expect(screen.getByTestId('win-rate-SELL')).toHaveTextContent('0.0%');
    expect(screen.getByTestId('win-rate-NEUTRAL')).toHaveTextContent('0.0%');

    // Stats show em-dash placeholders
    expect(screen.getByTestId('stat-sharpe')).toHaveTextContent('—');
    expect(screen.getByTestId('stat-avg-return')).toHaveTextContent('—');
    expect(screen.getByTestId('stat-max-dd')).toHaveTextContent('—');
  });

  it('handles fetch error gracefully', async () => {
    vi.mocked(fetchAccuracy).mockRejectedValue(new Error('network down'));
    vi.mocked(fetchAccuracySummary).mockRejectedValue(new Error('network down'));

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.queryByTestId('accuracy-loading')).not.toBeInTheDocument();
    });

    // Component still mounts without throwing
    expect(screen.getByTestId('accuracy-dashboard')).toBeInTheDocument();
    // Error message surfaced
    expect(screen.getByTestId('accuracy-dashboard')).toHaveTextContent('network down');
  });

  it('handles payload without .data wrapper', async () => {
    // Some backends return raw root object
    vi.mocked(fetchAccuracy).mockResolvedValue(SAMPLE);
    vi.mocked(fetchAccuracySummary).mockResolvedValue(null);

    render(<AccuracyDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId('win-rate-BUY')).toHaveTextContent('62.5%');
    });
  });
});
