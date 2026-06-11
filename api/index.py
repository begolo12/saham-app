import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
FRONTEND_DIST = ROOT / 'frontend' / 'dist'

sys.path.insert(0, str(BACKEND))

from mangum import Mangum  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse  # noqa: E402
from main import app  # noqa: E402


@app.get('/manifest.json', include_in_schema=False)
async def serve_manifest():
    path = FRONTEND_DIST / 'manifest.json'
    if path.exists():
        return FileResponse(path, media_type='application/manifest+json')
    raise HTTPException(404)


@app.get('/sw.js', include_in_schema=False)
async def serve_sw():
    path = FRONTEND_DIST / 'sw.js'
    if path.exists():
        return FileResponse(path, media_type='application/javascript')
    raise HTTPException(404)


@app.get('/icon-{w}x{h}.png', include_in_schema=False)
async def serve_icon(w: int, h: int):
    path = FRONTEND_DIST / f'icon-{w}x{h}.png'
    if w == h and path.exists():
        return FileResponse(path, media_type='image/png')
    raise HTTPException(404)


@app.get('/assets/{file_path:path}', include_in_schema=False)
async def serve_assets(file_path: str):
    path = FRONTEND_DIST / 'assets' / file_path
    if path.exists():
        return FileResponse(path)
    raise HTTPException(404)


@app.get('/', include_in_schema=False)
async def serve_index():
    path = FRONTEND_DIST / 'index.html'
    if path.exists():
        return HTMLResponse(path.read_text(encoding='utf-8'))
    return {'status': 'api running', 'frontend': 'not built'}


@app.get('/{full_path:path}', include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith('api/'):
        raise HTTPException(404)
    path = FRONTEND_DIST / 'index.html'
    if path.exists():
        return HTMLResponse(path.read_text(encoding='utf-8'))
    raise HTTPException(404)


handler = Mangum(app)
