import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import StockCard from './StockCard';

afterEach(() => cleanup());

const baseStock = {
  symbol: 'BBCA',
  name: 'Bank Central Asia',
  price: 9500,
  change_percent: 1.5,
  signal: 'BUY',
  signal_strength: 75,
};

describe('StockCard', () => {
  it('renders symbol, name and formatted price', () => {
    render(<StockCard stock={baseStock} />);
    expect(screen.getByText('BBCA')).toBeInTheDocument();
    expect(screen.getByText('Bank Central Asia')).toBeInTheDocument();
    // toLocaleString('id-ID') for 9500 → "9.500"
    expect(screen.getByText(/9[.\u00A0]500/)).toBeInTheDocument();
  });

  it('uses green color for positive change', () => {
    render(<StockCard stock={{ ...baseStock, change_percent: 2.4 }} />);
    const change = screen.getByText(/\+2\.40%/);
    expect(change).toBeInTheDocument();
    // Color is applied via inline style; jsdom normalizes hex → rgb
    expect(change.getAttribute('style') || '').toMatch(/rgb\(52,\s*199,\s*89\)/);
  });

  it('uses red color for negative change', () => {
    render(<StockCard stock={{ ...baseStock, change_percent: -1.2 }} />);
    const change = screen.getByText(/-1\.20%/);
    expect(change).toBeInTheDocument();
    expect(change.getAttribute('style') || '').toMatch(/rgb\(255,\s*59,\s*48\)/);
  });

  it('treats zero change as positive (no minus sign)', () => {
    render(<StockCard stock={{ ...baseStock, change_percent: 0 }} />);
    expect(screen.getByText(/\+0\.00%/)).toBeInTheDocument();
  });

  it('falls back to change when change_percent is missing', () => {
    // Strip change_percent out of the object passed to the component.
    const { change_percent: _cp, ...rest } = baseStock;
    void _cp; // explicit no-op so the destructure is preserved
    render(<StockCard stock={{ ...rest, change: 3.2 }} />);
    expect(screen.getByText(/\+3\.20%/)).toBeInTheDocument();
  });

  it('star button toggles watchlist on click without triggering onClick', () => {
    const onClick = vi.fn();
    const onToggle = vi.fn();
    render(
      <StockCard
        stock={baseStock}
        onClick={onClick}
        onToggleWatchlist={onToggle}
        watchlist={['BBCA']}
      />,
    );
    const star = screen.getByRole('button', { className: /star-btn/ });
    fireEvent.click(star);
    expect(onToggle).toHaveBeenCalledWith('BBCA');
    expect(onClick).not.toHaveBeenCalled();
  });

  it('clicking the card body invokes onClick with the stock', () => {
    const onClick = vi.fn();
    render(<StockCard stock={baseStock} onClick={onClick} />);
    // click on a non-button area
    fireEvent.click(screen.getByText('BBCA'));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith(
      expect.objectContaining({ symbol: 'BBCA' }),
    );
  });

  it('renders the watchlist star as active when symbol is in watchlist', () => {
    render(
      <StockCard
        stock={baseStock}
        watchlist={['BBCA']}
        onToggleWatchlist={() => {}}
      />,
    );
    const star = screen.getByRole('button', { className: /star-btn/ });
    expect(star.className).toMatch(/active/);
    expect(star.textContent).toContain('★');
  });

  it('renders the watchlist star as inactive when symbol is not in watchlist', () => {
    render(
      <StockCard
        stock={baseStock}
        watchlist={[]}
        onToggleWatchlist={() => {}}
      />,
    );
    const star = screen.getByRole('button', { className: /star-btn/ });
    expect(star.className).not.toMatch(/active/);
    expect(star.textContent).toContain('☆');
  });

  it('shows a sector badge when sector is provided', () => {
    render(
      <StockCard
        stock={{ ...baseStock, sector: 'Finance' }}
        onClick={() => {}}
      />,
    );
    expect(screen.getByText('Finance')).toBeInTheDocument();
  });
});
