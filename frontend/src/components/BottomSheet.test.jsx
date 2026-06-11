import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import BottomSheet from './BottomSheet';

describe('BottomSheet', () => {
  beforeEach(() => {
    document.body.style.overflow = '';
  });

  afterEach(() => {
    cleanup();
    document.body.style.overflow = '';
  });

  it('renders when open=true (after animation frame)', async () => {
    const onClose = vi.fn();
    await act(async () => {
      render(
        <BottomSheet open onClose={onClose} title="My Title">
          <p>content</p>
        </BottomSheet>,
      );
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('My Title')).toBeInTheDocument();
    expect(screen.getByText('content')).toBeInTheDocument();
  });

  it('does not render when open=false', () => {
    const onClose = vi.fn();
    render(<BottomSheet open={false} onClose={onClose}>x</BottomSheet>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders subtitle and children when provided', async () => {
    await act(async () => {
      render(
        <BottomSheet open onClose={() => {}} title="T" subtitle="Sub">
          <span data-testid="child">child body</span>
        </BottomSheet>,
      );
    });
    expect(screen.getByText('Sub')).toBeInTheDocument();
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('close button triggers onClose', async () => {
    const onClose = vi.fn();
    await act(async () => {
      render(<BottomSheet open onClose={onClose} title="x" />);
    });
    fireEvent.click(screen.getByRole('button', { name: /tutup/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('backdrop click closes the sheet', async () => {
    const onClose = vi.fn();
    await act(async () => {
      render(<BottomSheet open onClose={onClose}>x</BottomSheet>);
    });
    fireEvent.click(screen.getByRole('dialog').querySelector('.bottom-sheet-backdrop'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Escape key closes the sheet', async () => {
    const onClose = vi.fn();
    await act(async () => {
      render(<BottomSheet open onClose={onClose} />);
    });
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('locks body scroll when open and restores on close', async () => {
    document.body.style.overflow = 'auto';
    const { rerender } = render(<BottomSheet open onClose={() => {}} />);
    await act(async () => { /* let effect run */ });
    expect(document.body.style.overflow).toBe('hidden');
    rerender(<BottomSheet open={false} onClose={() => {}} />);
    // The scroll lock is bound to `mounted` which goes false after 350ms
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });
    expect(document.body.style.overflow).toBe('auto');
  });

  it('hides the close button when no title/subtitle', async () => {
    await act(async () => {
      render(<BottomSheet open onClose={() => {}}><p>body</p></BottomSheet>);
    });
    expect(screen.queryByRole('button', { name: /tutup/i })).not.toBeInTheDocument();
  });
});
