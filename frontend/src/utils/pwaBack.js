/**
 * PWA Android back-button helpers.
 *
 * 1. `ensureBackHistory` — on cold start with a deep link (e.g. /detail/BBCA),
 *    patch the history stack so Android back returns to the home page instead
 *    of closing the app. Only patches the stack when the current path is a
 *    sub-page; pure home launches stay untouched.
 *
 * 2. `HOME_PATHS` — list of root tabs that are safe destinations for back
 *    navigation when the user pops past the first entry.
 */

export const HOME_PATHS = new Set(['/', '/signal', '/news', '/portfolio', '/report', '/learning', '/accuracy', '/admin']);

export const HOME_PATH = '/';

export function isSubPage(pathname) {
  if (!pathname) return false;
  if (HOME_PATHS.has(pathname)) return false;
  return true;
}

/**
 * If the app cold-starts on a sub-page (deep link), insert a synthetic `/`
 * entry behind it so Android back returns home instead of closing the PWA.
 * Safe to call multiple times — no-op if history is already multi-entry.
 */
export function ensureBackHistory(pathname) {
  if (typeof window === 'undefined') return;
  if (!pathname || !isSubPage(pathname)) return;
  // history.length is 1 on cold-start direct hit; >= 2 means user navigated
  if (window.history.length >= 2) return;
  try {
    window.history.replaceState({ pwaHome: true }, '', HOME_PATH);
    window.history.pushState(null, '', pathname);
    // back will now pop to '/'
  } catch {
    // some embedded webviews restrict history mutation; fail silently
  }
}
