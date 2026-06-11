import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiCache } from './api';

// Helper: real-time wait for the ApiCache's stale-while-revalidate path
// (which uses Promise.resolve().then(...) microtask chains, not timers).
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));

describe('ApiCache', () => {
  beforeEach(() => {
    apiCache.clear();
  });

  it('caches a successful response and returns it on second call without refetching', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ data: 'hello' });
    const a = await apiCache.getOrFetch('k1', fetchFn, 60_000);
    const b = await apiCache.getOrFetch('k1', fetchFn, 60_000);
    expect(a).toEqual({ data: 'hello' });
    expect(b).toEqual({ data: 'hello' });
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('refetches after TTL expires (no prior data branch)', async () => {
    // After TTL expires with no prior data, ApiCache should issue a fresh fetch
    // (path 4 in the implementation). Use fake system time to make the
    // boundary deterministic.
    vi.useFakeTimers();
    try {
      const base = Date.now();
      vi.setSystemTime(base);
      const fetchFn = vi.fn()
        .mockResolvedValueOnce({ v: 1 })
        .mockResolvedValueOnce({ v: 2 });
      // First call: fresh fetch, no cache
      const first = await apiCache.getOrFetch('ttl-k', fetchFn, 1_000);
      expect(first).toEqual({ v: 1 });
      expect(fetchFn).toHaveBeenCalledTimes(1);
      // Inside TTL: served from cache
      vi.setSystemTime(base + 500);
      const cached = await apiCache.getOrFetch('ttl-k', fetchFn, 1_000);
      expect(cached).toEqual({ v: 1 });
      expect(fetchFn).toHaveBeenCalledTimes(1);
      // Past TTL: returns stale + bg refresh (SWR). Verify bg fires.
      vi.setSystemTime(base + 2_000);
      const stale = await apiCache.getOrFetch('ttl-k', fetchFn, 1_000);
      expect(stale).toEqual({ v: 1 }); // still stale for this call
      // let bg promise chain settle
      await vi.advanceTimersByTimeAsync(0);
      expect(fetchFn).toHaveBeenCalledTimes(2);
      // subsequent call sees the refreshed value
      const fresh = await apiCache.getOrFetch('ttl-k', fetchFn, 1_000);
      expect(fresh).toEqual({ v: 2 });
      expect(fetchFn).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('deduplicates two parallel calls into a single fetch', async () => {
    let resolveFetch;
    const fetchFn = vi.fn().mockImplementation(
      () => new Promise((res) => { resolveFetch = res; }),
    );
    const p1 = apiCache.getOrFetch('dedup', fetchFn, 60_000);
    // let the first call's microtask schedule the fetch
    await tick(0);
    const p2 = apiCache.getOrFetch('dedup', fetchFn, 60_000);
    resolveFetch({ ok: true });
    const [a, b] = await Promise.all([p1, p2]);
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(a).toEqual({ ok: true });
    expect(b).toEqual({ ok: true });
  });

  it('serves stale data and refreshes in the background (stale-while-revalidate)', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce({ v: 'fresh-1' })
      .mockResolvedValueOnce({ v: 'fresh-2' });
    const first = await apiCache.getOrFetch('swr', fetchFn, 50);
    expect(first).toEqual({ v: 'fresh-1' });
    // wait past TTL
    await tick(80);
    // next call returns stale instantly, then triggers background refresh
    const stale = await apiCache.getOrFetch('swr', fetchFn, 50);
    expect(stale).toEqual({ v: 'fresh-1' });
    // give the background refresh time to resolve
    await tick(20);
    const after = await apiCache.getOrFetch('swr', fetchFn, 50);
    expect(after).toEqual({ v: 'fresh-2' });
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('invalidate() clears the cache for a single key', async () => {
    const fetchFn = vi.fn()
      .mockResolvedValueOnce({ v: 1 })
      .mockResolvedValueOnce({ v: 2 });
    await apiCache.getOrFetch('inv', fetchFn, 60_000);
    apiCache.invalidate('inv');
    const result = await apiCache.getOrFetch('inv', fetchFn, 60_000);
    expect(result).toEqual({ v: 2 });
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('invalidatePrefix() removes only matching keys', async () => {
    const fnA = vi.fn().mockResolvedValue('a');
    const fnB = vi.fn().mockResolvedValue('b');
    await apiCache.getOrFetch('stocks:all', fnA, 60_000);
    await apiCache.getOrFetch('portfolio:something', fnB, 60_000);
    apiCache.invalidatePrefix('stocks:');
    const fa = vi.fn().mockResolvedValue('a2');
    const fb = vi.fn().mockResolvedValue('b2');
    expect(await apiCache.getOrFetch('stocks:all', fa, 60_000)).toBe('a2');
    expect(fa).toHaveBeenCalledTimes(1);
    // portfolio entry should still be cached — fn not invoked
    expect(await apiCache.getOrFetch('portfolio:something', fb, 60_000)).toBe('b');
    expect(fb).not.toHaveBeenCalled();
  });

  it('clears the cache on fetch failure so a retry is possible', async () => {
    const fail = vi.fn().mockRejectedValue(new Error('boom'));
    await expect(apiCache.getOrFetch('retry', fail, 60_000)).rejects.toThrow('boom');
    const ok = vi.fn().mockResolvedValue({ ok: true });
    const result = await apiCache.getOrFetch('retry', ok, 60_000);
    expect(result).toEqual({ ok: true });
    expect(ok).toHaveBeenCalledTimes(1);
  });
});
