import { useState, useCallback, useEffect, memo } from 'react';
import { fetchUsers, createUser } from '../api';

function AdminUsersPanel({ authUser }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ username: '', password: '', role: 'user' });
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    if (authUser?.role !== 'superadmin') return;
    const data = await fetchUsers();
    setUsers(data.users || []);
  }, [authUser]);

  const submit = useCallback(async (e) => {
    e.preventDefault();
    setMsg('');
    try {
      const data = await createUser(form);
      setUsers(data.users || []);
      setForm({ username: '', password: '', role: 'user' });
      setMsg('User dibuat.');
    } catch { setMsg('Gagal buat user.'); }
  }, [form]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load().catch(() => {}); }, [load]);

  if (authUser?.role !== 'superadmin') return null;

  return <div className="market-summary" style={{ margin: '0 16px 12px' }}>
    <div className="market-summary-header"><h3>Admin User</h3><span style={{ color: '#8E8E93', fontSize: 11 }}>Super admin</span></div>
    <form className="portfolio-form" onSubmit={submit}>
      <input placeholder="Username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} />
      <input placeholder="Password" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
      <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}><option value="user">user</option><option value="superadmin">superadmin</option></select>
      <button>Tambah</button>
    </form>
    {msg && <p style={{ color: '#8E8E93', fontSize: 12 }}>{msg}</p>}
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>
      {users.map(u => <div className="signal-card" key={u.id}><b style={{ color: '#fff' }}>{u.username}</b><span style={{ color: '#8E8E93', fontSize: 12, marginLeft: 8 }}>{u.role}</span></div>)}
    </div>
  </div>;
}

export default memo(AdminUsersPanel);
