import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTheme } from './useTheme';

// Helpers — emulate matchMedia in jsdom
function setMatchMedia(matchesLight) {
  const listeners = new Set();
  const mql = {
    matches: matchesLight,
    media: '(prefers-color-scheme: light)',
    addEventListener: (evt, cb) => listeners.add(cb),
    removeEventListener: (evt, cb) => listeners.delete(cb),
    addListener: (cb) => listeners.add(cb),
    removeListener: (cb) => listeners.delete(cb),
    dispatchEvent: (evt) => { for (const l of listeners) l(evt); return true; },
  };
  Object.defineProperty(window, 'matchMedia', {
    value: vi.fn().mockReturnValue(mql),
    configurable: true,
    writable: true,
  });
  return { mql, listeners };
}

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
    // Remove theme-color meta if present
    document.querySelectorAll('meta[name="theme-color"]').forEach((el) => el.remove());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('returns "dark" by default (no localStorage, no system pref)', () => {
    setMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('dark');
    expect(result.current.resolved).toBe('dark');
    // dark should NOT add the light-theme class
    expect(document.documentElement.classList.contains('light-theme')).toBe(false);
  });

  it('reads the theme from localStorage on mount', () => {
    setMatchMedia(false);
    localStorage.setItem('saham_theme', 'light');
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('light');
    expect(result.current.resolved).toBe('light');
    expect(document.documentElement.classList.contains('light-theme')).toBe(true);
  });

  it('falls back to default when localStorage value is invalid', () => {
    setMatchMedia(false);
    localStorage.setItem('saham_theme', 'neon');
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe('dark');
  });

  it('listens to prefers-color-scheme changes (auto mode)', () => {
    const { listeners } = setMatchMedia(false);
    localStorage.setItem('saham_theme', 'auto');
    const { result } = renderHook(() => useTheme());
    expect(result.current.resolved).toBe('dark');
    // Simulate system going to light mode
    act(() => {
      // notify all listeners
      for (const l of listeners) l({ matches: true });
    });
    expect(result.current.resolved).toBe('light');
    expect(document.documentElement.classList.contains('light-theme')).toBe(true);
  });

  it('setTheme() persists the new value to localStorage', () => {
    setMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme('light'));
    expect(result.current.theme).toBe('light');
    expect(localStorage.getItem('saham_theme')).toBe('light');
  });

  it('setTheme() ignores invalid values', () => {
    setMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme('neon'));
    expect(result.current.theme).toBe('dark');
    expect(localStorage.getItem('saham_theme')).toBe('dark');
  });

  it('toggle() flips between light and dark', () => {
    setMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    expect(result.current.resolved).toBe('dark');
    act(() => result.current.toggle());
    expect(result.current.resolved).toBe('light');
    act(() => result.current.toggle());
    expect(result.current.resolved).toBe('dark');
  });

  it('adds .light-theme class to <html> when resolved is light', () => {
    setMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    expect(document.documentElement.classList.contains('light-theme')).toBe(false);
    act(() => result.current.setTheme('light'));
    expect(document.documentElement.classList.contains('light-theme')).toBe(true);
  });

  it('updates the theme-color meta tag when theme changes', () => {
    setMatchMedia(false);
    const meta = document.createElement('meta');
    meta.setAttribute('name', 'theme-color');
    meta.setAttribute('content', '#000000');
    document.head.appendChild(meta);

    const { result } = renderHook(() => useTheme());
    // default dark — meta becomes dark color
    expect(meta.getAttribute('content')).toBe('#0a0a1a');
    act(() => result.current.setTheme('light'));
    expect(meta.getAttribute('content')).toBe('#F2F2F7');
  });

  it('uses system preference when theme is "auto"', () => {
    setMatchMedia(true);
    localStorage.setItem('saham_theme', 'auto');
    const { result } = renderHook(() => useTheme());
    expect(result.current.resolved).toBe('light');
    expect(document.documentElement.classList.contains('light-theme')).toBe(true);
  });
});
