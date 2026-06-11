import { create } from 'zustand';
import { fetchTopStocks, fetchAllStocks, fetchMarketSummary } from '../api';

const FALLBACK_STOCKS = [
  { symbol: 'BBCA', name: 'Bank Central Asia Tbk.', price: 10250, change_percent: 1.25, signal: 'BUY', signal_strength: 78, sector: 'Finance' },
  { symbol: 'BBRI', name: 'Bank Rakyat Indonesia Tbk.', price: 5650, change_percent: -0.88, signal: 'NEUTRAL', signal_strength: 45, sector: 'Finance' },
  { symbol: 'TLKM', name: 'Telkom Indonesia Tbk.', price: 3950, change_percent: 2.15, signal: 'BUY', signal_strength: 82, sector: 'Technology' },
  { symbol: 'ASII', name: 'Astra International Tbk.', price: 5450, change_percent: -1.45, signal: 'SELL', signal_strength: 65, sector: 'Consumer' },
  { symbol: 'ADRO', name: 'Adaro Energy Indonesia Tbk.', price: 2850, change_percent: 3.50, signal: 'BUY', signal_strength: 91, sector: 'Energy' },
  { symbol: 'BMRI', name: 'Bank Mandiri Tbk.', price: 7200, change_percent: 0.75, signal: 'BUY', signal_strength: 72, sector: 'Finance' },
  { symbol: 'GOTO', name: 'GoTo Gojek Tokopedia Tbk.', price: 98, change_percent: -2.00, signal: 'SELL', signal_strength: 55, sector: 'Technology' },
  { symbol: 'INDF', name: 'Indofood Sukses Makmur Tbk.', price: 6325, change_percent: 0.32, signal: 'NEUTRAL', signal_strength: 40, sector: 'Consumer' },
];

const FALLBACK_SUMMARY = {
  name: 'IHSG',
  price: 7234.56,
  change_percent: 0.45,
  high_52w: 7800,
  low_52w: 6500,
};

const useStocksStore = create((set, get) => ({
  topStocks: [],
  allStocks: [],
  marketSummary: null,
  loading: false,
  lastUpdated: null,

  fetchTopStocks: async () => {
    const { topStocks } = get();
    set({ loading: topStocks.length === 0 });
    try {
      const json = await fetchTopStocks();
      set({ topStocks: json.data || json.stocks || json || [], lastUpdated: new Date() });
    } catch {
      set((state) => ({
        topStocks: state.topStocks.length ? state.topStocks : FALLBACK_STOCKS,
        lastUpdated: new Date(),
      }));
    } finally {
      set({ loading: false });
    }
  },

  fetchAllStocks: async () => {
    try {
      const json = await fetchAllStocks();
      set({ allStocks: json.data || json.stocks || json || [] });
    } catch {
      // silent — fallback to empty
    }
  },

  fetchMarketSummary: async () => {
    try {
      const json = await fetchMarketSummary();
      set({ marketSummary: json.data || json });
    } catch {
      set({ marketSummary: FALLBACK_SUMMARY });
    }
  },
}));

export default useStocksStore;
