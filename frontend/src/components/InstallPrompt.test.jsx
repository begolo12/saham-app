import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import InstallPrompt from './InstallPrompt';

const STORAGE_KEY = 'saham_install_prompt';

describe('InstallPrompt', () => {
  beforeEach(() => {
    localStorage.clear();
    cleanup();
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  function flush(ms = 0) {
    return act(() => new Promise((r) => setTimeout(r, ms)));
  }

  function firePrompt() {
    return act(() => {
      const evt = new Event('beforeinstallprompt');
      evt.preventDefault = vi.fn();
      window.dispatchEvent(evt);
    });
  }

  it('does not render on first visit (visit count < 2)', async () => {
    render(<InstallPrompt />);
    // dispatch beforeinstallprompt to attempt showing
    await firePrompt();
    await flush(0);
    expect(document.querySelector('.install-prompt')).not.toBeInTheDocument();
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(stored.visits).toBe(1);
  });

  it('renders banner after 2 visits when beforeinstallprompt fires', async () => {
    // pre-seed visits = 1, so after mount it becomes 2
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visits: 1 }));
    render(<InstallPrompt />);
    await firePrompt();
    // banner is shown after a 1500ms delay in the source
    await flush(1600);
    expect(document.querySelector('.install-prompt')).toBeInTheDocument();
    expect(screen.getByText(/Pasang Saham ID/i)).toBeInTheDocument();
  });

  it('dismiss button hides the banner and persists the dismissal', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visits: 5 }));
    render(<InstallPrompt />);
    await firePrompt();
    await flush(1600);
    const dismiss = screen.getByRole('button', { name: /tutup/i });
    fireEvent.click(dismiss);
    expect(document.querySelector('.install-prompt')).not.toBeInTheDocument();
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(stored.dismissed).toBe(true);
  });

  it('does not render again after dismissal on subsequent mounts', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visits: 10, dismissed: true }));
    render(<InstallPrompt />);
    await firePrompt();
    await flush(1600);
    expect(document.querySelector('.install-prompt')).not.toBeInTheDocument();
  });

  it('captures the beforeinstallprompt event and exposes the install button', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visits: 3 }));
    render(<InstallPrompt />);
    const promptFn = vi.fn().mockResolvedValue(undefined);
    const userChoice = Promise.resolve({ outcome: 'accepted' });
    await act(() => {
      const evt = new Event('beforeinstallprompt');
      evt.prompt = promptFn;
      evt.userChoice = userChoice;
      evt.preventDefault = vi.fn();
      window.dispatchEvent(evt);
    });
    await flush(1600);
    expect(document.querySelector('.install-prompt')).toBeInTheDocument();
    const installBtn = screen.getByRole('button', { name: /pasang/i });
    fireEvent.click(installBtn);
    await flush(10);
    expect(promptFn).toHaveBeenCalledTimes(1);
  });

  it('appinstalled event removes the storage key and hides the banner', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visits: 5, dismissed: false }));
    render(<InstallPrompt />);
    await firePrompt();
    await flush(1600);
    expect(document.querySelector('.install-prompt')).toBeInTheDocument();
    await act(() => {
      window.dispatchEvent(new Event('appinstalled'));
    });
    await flush(10);
    expect(document.querySelector('.install-prompt')).not.toBeInTheDocument();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
