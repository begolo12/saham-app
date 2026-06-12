import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { isSubPage, ensureBackHistory, HOME_PATH } from './pwaBack';

describe('pwaBack', () => {
  describe('isSubPage', () => {
    it('returns false for known root tabs', () => {
      for (const p of ['/', '/signal', '/news', '/portfolio', '/report', '/learning', '/accuracy', '/admin']) {
        expect(isSubPage(p)).toBe(false);
      }
    });

    it('returns true for sub-pages like /detail/BBCA', () => {
      expect(isSubPage('/detail/BBCA')).toBe(true);
      expect(isSubPage('/detail/BBCA.JK')).toBe(true);
      expect(isSubPage('/unknown/route')).toBe(true);
    });

    it('handles empty/null/undefined safely', () => {
      expect(isSubPage('')).toBe(false);
      expect(isSubPage(null)).toBe(false);
      expect(isSubPage(undefined)).toBe(false);
    });
  });

  describe('ensureBackHistory', () => {
    let originalWindow;
    let originalHistory;

    beforeEach(() => {
      originalWindow = globalThis.window;
      originalHistory = globalThis.history;
    });

    afterEach(() => {
      globalThis.window = originalWindow;
      globalThis.history = originalHistory;
    });

    function stubWindow(length, pathname = '/detail/BBCA') {
      const calls = [];
      const fakeHistory = {
        get length() {
          return length;
        },
        replaceState: (state, _, url) => calls.push(['replaceState', url]),
        pushState: (state, _, url) => calls.push(['pushState', url]),
      };
      globalThis.window = { history: fakeHistory, location: { pathname } };
      return { calls, fakeHistory };
    }

    it('patches history on cold-start deep link (length 1)', () => {
      const { calls } = stubWindow(1, '/detail/BBCA');
      ensureBackHistory('/detail/BBCA');
      expect(calls).toEqual([
        ['replaceState', HOME_PATH],
        ['pushState', '/detail/BBCA'],
      ]);
    });

    it('does not patch when path is a root tab', () => {
      const { calls } = stubWindow(1, '/');
      ensureBackHistory('/');
      expect(calls).toEqual([]);
    });

    it('does not patch when history is already multi-entry', () => {
      const { calls } = stubWindow(3, '/detail/BBCA');
      ensureBackHistory('/detail/BBCA');
      expect(calls).toEqual([]);
    });

    it('does not throw when window is missing', () => {
      const original = globalThis.window;
      // simulate SSR / non-browser env
      // eslint-disable-next-line no-undef
      delete globalThis.window;
      expect(() => ensureBackHistory('/detail/BBCA')).not.toThrow();
      globalThis.window = original;
    });
  });
});
