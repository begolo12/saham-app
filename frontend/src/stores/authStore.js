import { create } from 'zustand';
import { fetchMe, login as apiLogin } from '../api';

const useAuthStore = create((set) => ({
  authUser: null,
  authChecked: false,

  login: async (username, password) => {
    const data = await apiLogin(username, password);
    localStorage.setItem('saham_auth_token', data.token);
    set({ authUser: data.user });
    return data.user;
  },

  logout: () => {
    localStorage.removeItem('saham_auth_token');
    set({ authUser: null });
  },

  checkSession: async () => {
    try {
      const data = await fetchMe();
      set({ authUser: data.user, authChecked: true });
    } catch {
      localStorage.removeItem('saham_auth_token');
      set({ authChecked: true });
    }
  },
}));

export default useAuthStore;
