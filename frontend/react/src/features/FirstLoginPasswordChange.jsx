import React, { useEffect, useState } from 'react';
import axios from 'axios';

const resolveDashboardTarget = () => {
  const role = localStorage.getItem('role');
  const roles = JSON.parse(localStorage.getItem('roles') || '[]');
  const assignedClass = localStorage.getItem('assigned_class') || '';

  if (roles.includes('proprietor') || role === 'proprietor') return '/proprietor';
  if (roles.includes('headmaster') || role === 'headmaster') return '/headmaster';
  if (roles.includes('finance') || role === 'finance') return '/finance';
  if (roles.includes('inventory_manager') || role === 'inventory_manager') return '/inventory';
  if (roles.includes('kitchen') || role === 'kitchen') return '/kitchen';
  if ((roles.includes('homeroom') || roles.includes('teacher') || role === 'homeroom' || role === 'teacher') && assignedClass) {
    return '/homeroom';
  }

  return '/teacher';
};

export default function FirstLoginPasswordChange() {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [status, setStatus] = useState({ type: '', msg: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      window.location.href = '/login';
      return;
    }

    if (localStorage.getItem('requires_password_reset') !== 'true') {
      window.location.href = localStorage.getItem('post_login_target') || resolveDashboardTarget();
    }
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus({ type: '', msg: '' });

    if (password.length < 8) {
      setStatus({ type: 'error', msg: 'Password must be at least 8 characters long.' });
      return;
    }

    if (!/[A-Z]/.test(password)) {
      setStatus({ type: 'error', msg: 'Password must contain at least one uppercase letter.' });
      return;
    }

    if (!/[0-9]/.test(password)) {
      setStatus({ type: 'error', msg: 'Password must contain at least one digit.' });
      return;
    }

    if (password !== confirmPassword) {
      setStatus({ type: 'error', msg: 'Passwords do not match.' });
      return;
    }

    try {
      setSaving(true);
      await axios.post(
        '/api/profile/update',
        { password },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-School-ID': localStorage.getItem('school_id')
          }
        }
      );

      localStorage.removeItem('requires_password_reset');
      const target = localStorage.getItem('post_login_target') || resolveDashboardTarget();
      setStatus({ type: 'success', msg: 'Password updated successfully. Redirecting to your dashboard...' });
      setTimeout(() => {
        localStorage.removeItem('post_login_target');
        window.location.href = target;
      }, 1200);
    } catch (error) {
      setStatus({
        type: 'error',
        msg: error.response?.data?.message || 'Failed to update password. Please try again.'
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 text-3xl">
            🔐
          </div>
          <h1 className="text-2xl font-black text-slate-800">Change Temporary Password</h1>
          <p className="mt-2 text-sm text-slate-600">
            This account was created with a temporary password. Set a new password before continuing.
          </p>
        </div>

        {status.msg && (
          <div className={`mb-5 rounded-xl p-4 text-sm font-bold ${status.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
            {status.msg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="mb-1 ml-1 block text-xs font-bold uppercase text-slate-500">New Password</label>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter a new password"
              required
            />
            <p className="mt-1 text-xs text-slate-500">Use at least 8 characters, including one uppercase letter and one digit.</p>
          </div>

          <div>
            <label className="mb-1 ml-1 block text-xs font-bold uppercase text-slate-500">Confirm Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Re-enter the new password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full rounded-xl bg-blue-900 p-4 font-bold text-white shadow-lg transition-all hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? 'Updating Password...' : 'Save New Password'}
          </button>
        </form>
      </div>
    </div>
  );
}