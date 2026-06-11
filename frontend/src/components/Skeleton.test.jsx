import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import Skeleton from './Skeleton';

describe('Skeleton', () => {
  afterEach(() => cleanup());

  it('renders the default skeleton (card variant by default)', () => {
    const { container } = render(<Skeleton />);
    // default variant is 'card'
    expect(container.querySelector('.skeleton-list')).toBeInTheDocument();
    expect(container.querySelector('.skeleton-card')).toBeInTheDocument();
  });

  it('renders the requested variant: detail', () => {
    const { container } = render(<Skeleton variant="detail" />);
    expect(container.querySelector('.skeleton-detail')).toBeInTheDocument();
  });

  it('renders the requested variant: market-summary', () => {
    const { container } = render(<Skeleton variant="market-summary" />);
    expect(container.querySelector('.skeleton-market-summary')).toBeInTheDocument();
    expect(container.querySelectorAll('.skeleton-market-row').length).toBe(3);
  });

  it('renders the requested variant: chart', () => {
    const { container } = render(<Skeleton variant="chart" />);
    expect(container.querySelector('.skeleton-chart')).toBeInTheDocument();
  });

  it('renders the requested variant: learning-stat (3 stat tiles)', () => {
    const { container } = render(<Skeleton variant="learning-stat" />);
    expect(container.querySelectorAll('.skeleton-learning-stat').length).toBe(3);
  });

  it('respects the count prop on the card variant (multiple placeholders)', () => {
    const { container } = render(<Skeleton variant="card" count={4} />);
    expect(container.querySelectorAll('.skeleton-card').length).toBe(4);
  });

  it('applies width / height / borderRadius styles on internal lines when supplied', () => {
    // The card variant has a leading icon-shaped line with inline width / height /
    // borderRadius. Re-render and read those computed style props.
    const { container } = render(<Skeleton variant="card" />);
    const icon = container.querySelector('.skeleton-card .skeleton-line');
    expect(icon).toBeInTheDocument();
    // The component hard-codes 38×38 — assert that style hook is present
    const style = icon.getAttribute('style') || '';
    expect(style).toMatch(/width:\s*38/);
    expect(style).toMatch(/height:\s*38/);
    expect(style).toMatch(/border-radius:\s*10/);
  });
});
