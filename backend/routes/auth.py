from typing import Dict, Any

from fastapi import Depends, HTTPException

from app import app
from schemas.auth import LoginRequest, UserCreate, RefreshRequest
from services.db import (
    _now_iso, _password_hash, _get_user_by_credentials, _make_token,
    current_user, superadmin_user, _db_conn,
)
from services.auth_service import login as auth_login, refresh as auth_refresh


@app.post('/api/auth/login')
async def login(payload: LoginRequest):
    result = auth_login(payload.username, payload.password)
    if not result:
        raise HTTPException(status_code=401, detail='Username/password salah')
    return result


@app.post('/api/auth/refresh')
async def refresh(payload: RefreshRequest):
    result = auth_refresh(payload.refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail='Refresh token tidak valid atau kedaluwarsa')
    return result


@app.get('/api/auth/me')
async def me(user: Dict[str, Any] = Depends(current_user)):
    return {'user': {'id': user['id'], 'username': user['username'], 'role': user['role']}}


@app.get('/api/admin/users')
async def admin_users(_: Dict[str, Any] = Depends(superadmin_user)):
    with _db_conn() as conn:
        rows = conn.execute('SELECT id, username, role, created_at FROM app_users ORDER BY id').fetchall()
    return {'users': [dict(r) for r in rows]}


@app.post('/api/admin/users')
async def admin_create_user(payload: UserCreate, _: Dict[str, Any] = Depends(superadmin_user)):
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail='Username dan password wajib')
    role = payload.role if payload.role in ('user', 'superadmin') else 'user'
    try:
        with _db_conn() as conn:
            conn.execute('INSERT INTO app_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
                         (username, _password_hash(payload.password), role, _now_iso()))
            conn.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'User gagal dibuat: {exc}')
    return await admin_users(_)
