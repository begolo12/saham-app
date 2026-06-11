import { useState, useCallback, memo } from 'react';
import useAuthStore from '../stores/authStore';

function LoginPage() {
  const [form, setForm] = useState({ username: 'admin', password: 'admin123' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const loginStore = useAuthStore((s) => s.login);

  const submit = useCallback(async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginStore(form.username, form.password);
    } catch {
      setError('Login gagal. Cek username/password.');
    } finally {
      setLoading(false);
    }
  }, [form, loginStore]);

  return <div className="login-page">
    <form className="login-card" onSubmit={submit}>
      <div className="app-title-wrap" style={{ justifyContent: 'center', marginBottom: 8 }}><h1 className="app-title">Saham ID</h1><span className="live-dot" /></div>
      <p className="login-subtitle">Masuk untuk sinkron portfolio per user.</p>
      <input placeholder="Username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} disabled={loading} />
      <input placeholder="Password" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} disabled={loading} />
      {error && <p className="login-error">{error}</p>}
      <button disabled={loading}>{loading ? 'Memproses...' : 'Masuk'}</button>
      <p className="login-help">Masuk pakai akun admin yang diset di server.</p>
    </form>
  </div>;
}

export default memo(LoginPage);
