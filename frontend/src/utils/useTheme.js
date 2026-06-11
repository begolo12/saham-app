import { useState, useEffect, useCallback, useMemo } from 'react';
import { lightHaptic } from './haptic';

const STORAGE_KEY = 'saham_theme';
const VALID = ['auto', 'light', 'dark'];

/**
 * useTheme — manage light/dark/auto theme.
 *
 *   - "auto" follows the OS prefers-color-scheme setting
 *   - "light" / "dark" force the theme
 *   - Choice is persisted in localStorage under "saham_theme"
 *   - Returns: { theme, resolved, setTheme, toggle }
 */
export function useTheme() {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === 'undefined') return 'dark';
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && VALID.includes(stored)) return stored;
    } catch { /* ignore */ }
    return 'dark';
  });

  const [systemPrefersLight, setSystemPrefersLight] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    return window.matchMedia('(prefers-color-scheme: light)').matches;
  });

  // Track OS-level preference changes
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mql = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = (e) => setSystemPrefersLight(e.matches);
    mql.addEventListener?.('change', onChange);
    return () => mql.removeEventListener?.('change', onChange);
  }, []);

  // Apply theme class + theme-color meta
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const isLight = theme === 'light' || (theme === 'auto' && systemPrefersLight);
    // Smooth transition between themes
    root.classList.add('theme-transitioning');
    root.classList.toggle('light-theme', isLight);
    root.classList.toggle('theme-auto', theme === 'auto');
    // Update status bar color
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', isLight ? '#F2F2F7' : '#0a0a1a');
    const t = setTimeout(() => root.classList.remove('theme-transitioning'), 400);
    return () => clearTimeout(t);
  }, [theme, systemPrefersLight]);

  // Persist user choice
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, theme); } catch { /* ignore */ }
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (!VALID.includes(next)) return;
    lightHaptic();
    setThemeState(next);
  }, []);

  const toggle = useCallback(() => {
    setThemeState((prev) => {
      const effectiveLight = prev === 'light' || (prev === 'auto' && systemPrefersLight);
      return effectiveLight ? 'dark' : 'light';
    });
    lightHaptic();
  }, [systemPrefersLight]);

  const resolved = useMemo(() => {
    if (theme === 'light') return 'light';
    if (theme === 'dark') return 'dark';
    return systemPrefersLight ? 'light' : 'dark';
  }, [theme, systemPrefersLight]);

  return { theme, resolved, setTheme, toggle };
}

export default useTheme;
