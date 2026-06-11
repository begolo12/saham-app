import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react';
import { useState, useEffect } from 'react';
import PageErrorBoundary from './PageErrorBoundary';

// A child that throws on demand so we can exercise the boundary.
function Bomb({ shouldThrow }) {
  if (shouldThrow) throw new Error('Boom dari anak komponen');
  return <p>ok-child</p>;
}

afterEach(() => cleanup());

describe('PageErrorBoundary', () => {
  it('renders children when no error is thrown', () => {
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow={false} />
      </PageErrorBoundary>,
    );
    expect(screen.getByText('ok-child')).toBeInTheDocument();
  });

  it('catches an error and shows the fallback UI', () => {
    // React logs the error to console — silence it for cleaner test output
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow />
      </PageErrorBoundary>,
    );
    expect(screen.getByText(/Gagal Memuat Halaman/i)).toBeInTheDocument();
    expect(screen.getByText('Boom dari anak komponen')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Coba Lagi/i })).toBeInTheDocument();
    spy.mockRestore();
  });

  it('retry button resets the boundary state and re-renders children', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    // Drive the "shouldThrow" flag from OUTSIDE the boundary so we can flip it
    // without the boundary swallowing the click on a hidden flip button.
    const setThrowRef = { current: null };
    function Outer() {
      // eslint-disable-next-line react-hooks/rules-of-hooks
      const [shouldThrow, set] = useState(true);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      useEffect(() => { setThrowRef.current = set; }, [set]);
      return (
        <PageErrorBoundary>
          <Bomb shouldThrow={shouldThrow} />
        </PageErrorBoundary>
      );
    }
    render(<Outer />);
    // boundary caught the error
    expect(screen.getByText(/Gagal Memuat Halaman/i)).toBeInTheDocument();

    // stop the child from throwing, then click retry
    act(() => setThrowRef.current(false));
    fireEvent.click(screen.getByRole('button', { name: /Coba Lagi/i }));
    expect(screen.getByText('ok-child')).toBeInTheDocument();
    expect(screen.queryByText(/Gagal Memuat Halaman/i)).not.toBeInTheDocument();
    spy.mockRestore();
  });

  it('fallback message is in Bahasa Indonesia', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow />
      </PageErrorBoundary>,
    );
    expect(screen.getByText(/Gagal Memuat Halaman/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Coba Lagi/i })).toBeInTheDocument();
    spy.mockRestore();
  });
});
