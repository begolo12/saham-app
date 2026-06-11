import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import time
import json
import sys

# Read stock list
from stock_data import INDONESIAN_STOCKS
print(f'Total in universe: {len(INDONESIAN_STOCKS)}', flush=True)

def check_volume(symbol):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period='5d', timeout=8)
        if hist is None or hist.empty or len(hist) < 2:
            return (symbol, None, 'no data')
        avg_vol = int(hist['Volume'].tail(5).mean())
        return (symbol, avg_vol, 'ok')
    except Exception as e:
        return (symbol, None, str(e)[:80])

start = time.time()
results = []
total = len(INDONESIAN_STOCKS)
done = 0

with ThreadPoolExecutor(max_workers=6) as exe:
    futures = [exe.submit(check_volume, s) for s in INDONESIAN_STOCKS]
    for fut in futures:
        r = fut.result(timeout=30)
        results.append(r)
        done += 1
        if done % 10 == 0 or done == total:
            elapsed = time.time() - start
            print(f'[{done}/{total}] {elapsed:.1f}s elapsed', flush=True)

ok = [r for r in results if r[2] == 'ok']
no_data = [r for r in results if r[2] != 'ok']
above_100k = [r for r in ok if r[1] is not None and r[1] >= 100_000]
above_500k = [r for r in ok if r[1] is not None and r[1] >= 500_000]
above_1m = [r for r in ok if r[1] is not None and r[1] >= 1_000_000]

print()
print('=== RESULTS ===')
print(f'Total in universe: {len(INDONESIAN_STOCKS)}')
print(f'OK data: {len(ok)}')
print(f'Failed/no-data: {len(no_data)}')
print(f'>= 100K vol: {len(above_100k)}')
print(f'>= 500K vol: {len(above_500k)}')
print(f'>= 1M vol: {len(above_1m)}')
print()

# Sort by volume desc
above_100k_sorted = sorted(above_100k, key=lambda x: -x[1])

print('Stocks >= 100K volume (sorted by volume desc):')
for s, v, _ in above_100k_sorted:
    print(f'  {s.replace(".JK", ""):<8} = {v:>15,}')

# Save JSON
out = {
    'total_universe': len(INDONESIAN_STOCKS),
    'ok_count': len(ok),
    'failed_count': len(no_data),
    'failed_symbols': [r[0] for r in no_data],
    'above_100k_count': len(above_100k),
    'above_500k_count': len(above_500k),
    'above_1m_count': len(above_1m),
    'above_100k_stocks': [
        {'symbol': s.replace('.JK', ''), 'avg_volume': v}
        for s, v, _ in above_100k_sorted
    ],
    'all_results': [
        {'symbol': s.replace('.JK', ''), 'avg_volume': v, 'status': st}
        for s, v, st in results
    ]
}
with open('idx_volume_scan.json', 'w') as f:
    json.dump(out, f, indent=2)
print()
print('Saved: idx_volume_scan.json')
print(f'Elapsed: {time.time() - start:.1f}s')
