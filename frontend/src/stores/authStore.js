import { create } from 'zustand';
import { fetchMe, login as apiLogin } from '../api';

const TOKEN_KEY = 'saham_auth_token';
const REFRESH_KEY = 'saham_refresh_token';
const USERNAME_KEY = 'saham_username';

// Synchronous init — read cached auth so first paint never blocks on /auth/me
function readCachedAuth() {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const username = localStorage.getItem(USERNAME_KEY);
    if (token && username) {
      return { authUser: { username }, authChecked: true };
    }
  } catch {
    // localStorage may be unavailable (private mode); fall through
  }
  return { authUser: null, authChecked: true };
}

const useAuthStore = create((set) => ({
  ...readCachedAuth(),

  login: async (username, password) => {
    const data = await apiLogin(username, password);
    localStorage.setItem(TOKEN_KEY, data.token);
    if (data.user?.username) localStorage.setItem(USERNAME_KEY, data.user.username);
    set({ authUser: data.user });
    return data.user;
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USERNAME_KEY);
    set({ authUser: null });
  },

  checkSession: async () => {
    try {
      const data = await fetchMe();
      if (data.user?.username) localStorage.setItem(USERNAME_KEY, data.user.username);
      set({ authUser: data.user, authChecked: true });
    } catch {
      // Token rejected — clear cached auth
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
      localStorage.removeItem(USERNAME_KEY);
      set({ authUser: null, authChecked: true });
    }
  },
}));

export default useAuthStore;
