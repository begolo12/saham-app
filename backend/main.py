#!/usr/bin/env python
"""SahamApp API — slim entry point.

Imports the FastAPI app from app.py and runs startup initialisation
(DB schema creation, admin user seeding).
"""

from app import app
from services.db import _init_db, _ensure_admin_user

# ── Startup: create tables, seed admin user ──
_init_db()
_ensure_admin_user()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8774, reload=True)
