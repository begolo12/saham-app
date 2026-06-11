import { useState, useEffect, memo } from 'react';
import { lightHaptic } from '../utils/haptic';

const STORAGE_KEY = 'saham_install_prompt';
const MIN_VISITS = 2;

/**
 * InstallPrompt — lightweight PWA install banner.
 *
 * Listens for the browser's beforeinstallprompt event, then surfaces a
 * non-intrusive banner after the user has visited at least MIN_VISITS times
 * (tracked in localStorage). The banner is dismissible and the dismissal
 * sticks in localStorage so it won't pester the user again.
 */
function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);
  const [visible, setVisible] = useState(false);
  const [installed, setInstalled] = useState(false);

  // Detect already-installed (iOS + Android/desktop)
  useEffect(() => {
    const isStandalone =
      (typeof window !== 'undefined' &&
        (window.matchMedia?.('(display-mode: standalone)').matches ||
          window.navigator?.standalone === true)) ||
      false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    if (isStandalone) setInstalled(true);
  }, []);

  // Read state + register event listener
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- legitimate one-time setup
    if (installed) return undefined;

    const stored = (() => {
      try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch { return {}; }
    })();

    // If user dismissed and didn't ask to be reminded, do nothing
    if (stored.dismissed && !stored.allowReshow) {
      return undefined;
    }

    // Track visit count
    const nextVisits = (stored.visits || 0) + 1;
    const updated = { ...stored, visits: nextVisits };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));

    const onPrompt = (e) => {
      e.preventDefault();
      setDeferred(e);
      if (nextVisits >= MIN_VISITS) {
        // Defer the banner a bit so it doesn't compete with first paint
        setTimeout(() => setVisible(true), 1500);
      }
    };

    const onInstalled = () => {
      setInstalled(true);
      setVisible(false);
      try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
    };

    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, [installed]);

  const handleInstall = async () => {
    if (!deferred) return;
    lightHaptic();
    try {
      deferred.prompt();
      const choice = await deferred.userChoice;
      if (choice?.outcome === 'accepted') {
        setInstalled(true);
        setVisible(false);
      }
    } catch {
      /* swallow — user may have closed the native prompt */
    }
    setDeferred(null);
  };

  const handleDismiss = () => {
    lightHaptic();
    setVisible(false);
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      stored.dismissed = true;
      stored.allowReshow = false;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
    } catch { /* ignore */ }
  };

  if (!visible || installed) return null;

  return (
    <div className="install-prompt" role="complementary" aria-label="Pasang aplikasi">
      <div className="install-prompt-icon" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3v12" />
          <polyline points="7 10 12 15 17 10" />
          <path d="M5 21h14" />
        </svg>
      </div>
      <div className="install-prompt-body">
        <b>Pasang Saham ID</b>
        <span>Akses lebih cepat &amp; notifikasi sinyal langsung dari homescreen</span>
      </div>
      <div className="install-prompt-actions">
        <button type="button" className="install-prompt-btn install-prompt-btn-primary" onClick={handleInstall}>
          Pasang
        </button>
        <button type="button" className="install-prompt-btn install-prompt-btn-ghost" onClick={handleDismiss} aria-label="Tutup">
          ✕
        </button>
      </div>
    </div>
  );
}

export default memo(InstallPrompt);
