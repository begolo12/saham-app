import { create } from 'zustand';
import { fetchPortfolio, savePortfolioPosition, deletePortfolioPosition, fetchDailyReport } from '../api';

const usePortfolioStore = create((set, get) => ({
  portfolio: null,
  dailyReport: null,

  fetchPortfolio: async () => {
    try {
      const data = await fetchPortfolio();
      set({ portfolio: data });
    } catch {
      set({ portfolio: { positions: [], summary: {} } });
    }
  },

  savePosition: async (pos) => {
    const data = await savePortfolioPosition(pos);
    set({ portfolio: data });
    get().fetchDailyReport();
  },

  deletePosition: async (symbol) => {
    const data = await deletePortfolioPosition(symbol);
    set({ portfolio: data });
    get().fetchDailyReport();
  },

  fetchDailyReport: async () => {
    try {
      set({ dailyReport: await fetchDailyReport() });
    } catch {
      set({ dailyReport: null });
    }
  },
}));

export default usePortfolioStore;
