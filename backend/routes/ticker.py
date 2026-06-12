"""Live ticker routes — Server-Sent Events + REST snapshot.

The ticker engine (see ``services/ticker.py``) polls yfinance on a fast
interval and broadcasts price deltas to every connected client. Clients
connect to ``/api/stream/ticks`` over SSE and receive either:

* a ``snapshot`` event on connect (initial state, no animation)
* a ``tick`` event whenever at least one price changed
* a ``heartbeat`` comment every 15s (proxies stay alive)
* an ``end`` event when the server is shutting down

For clients that don't support EventSource (Electron preload, server-side
fetchers), ``/api/live/ticks`` returns the same snapshot as a normal JSON
response.
"""

import logging
from typing import Optional

from fastapi import Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from services.ticker import TickerEngine, stream_ticks

# Import the FastAPI app to register routes directly on it (matches the
# self-registration pattern used by sibling modules in routes/).
from app import app  # noqa: E402

logger = logging.getLogger('saham-api')


@app.get('/api/stream/ticks')
async def stream_ticks_endpoint(request: Request):
    """SSE endpoint — push live price ticks to the browser.

    Includes headers that prevent buffering by intermediate proxies
    (nginx, Vercel edge) so the client sees updates in real time.
    """
    engine = TickerEngine.instance()
    headers = {
        # Disable proxy buffering so events flush immediately
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive',
    }
    return StreamingResponse(
        stream_ticks(engine),
        media_type='text/event-stream',
        headers=headers,
    )


@app.get('/api/live/ticks')
async def live_ticks_snapshot(
    symbols: Optional[str] = Query(None, description='Comma-separated symbols'),
):
    """JSON snapshot of the ticker's current in-memory state.

    Cheap (no yfinance calls) — safe to hit from any non-SSE client. Use
    this for SSR/initial render; switch to the SSE stream for live updates.
    """
    engine = TickerEngine.instance()
    sym_list = None
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
    return JSONResponse(engine.snapshot(sym_list))
