import React, { useState } from 'react';
import axios from 'axios';

export default function AdminLogin() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('/api/platform/auth/login', {
        username: username.trim(),
        password: password
      });

      // Store admin credentials
      localStorage.setItem('token', response.data.token);
      localStorage.setItem('isAdmin', 'true');
      localStorage.setItem('adminUser', JSON.stringify(response.data.user));

      // Redirect to admin dashboard
      window.location.href = '/admin';
    } catch (err) {
      const msg = err.response?.data?.message || 'Invalid admin credentials';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Admin Console Header */}
        <div className="bg-linear-to-r from-purple-900 to-blue-900 p-8 rounded-t-3xl shadow-2xl border-b-4 border-purple-500">
          <div className="text-center">
            <div className="w-16 h-16 bg-linear-to-br from-purple-400 to-blue-400 rounded-2xl flex items-center justify-center text-white font-black text-2xl shadow-lg mx-auto mb-4">
              ⚙️
            </div>
            <h1 className="text-3xl font-black text-white mb-2">EDUPULSE</h1>
            <p className="text-purple-200 text-sm font-bold">PLATFORM ADMIN CONSOLE</p>
          </div>
        </div>

        {/* Login Form */}
        <div className="bg-white rounded-b-3xl shadow-2xl p-8">
          <h2 className="text-2xl font-bold text-slate-800 mb-1">Admin Access</h2>
          <p className="text-slate-500 text-sm mb-6">Platform administrator credentials required</p>

          {error && (
            <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6 text-sm font-bold flex items-center gap-2 border border-red-200">
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="text-xs font-bold text-slate-700 uppercase block mb-2">
                Admin Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="your_admin_username"
                className="w-full border-2 border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 focus:bg-white outline-none transition-all font-medium"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label className="text-xs font-bold text-slate-700 uppercase block mb-2">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full border-2 border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-purple-500 focus:bg-white outline-none transition-all font-medium"
                required
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-linear-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-bold p-3 rounded-xl transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed mt-6"
            >
              {loading ? '⏳ Authenticating...' : '🔐 Sign In as Admin'}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-slate-200">
            <p className="text-center text-sm text-slate-600">
              Looking for school login?{' '}
              <a href="/login" className="font-bold text-blue-600 hover:text-blue-700">
                Go to School Login
              </a>
            </p>
          </div>

          {/* Admin Console Info */}
          <div className="mt-6 p-4 bg-purple-50 rounded-lg border border-purple-200">
            <p className="text-xs font-bold text-purple-900 uppercase mb-2">ℹ️ Admin Console</p>
            <p className="text-xs text-purple-800 leading-relaxed">
              This console is restricted to platform administrators only. Unauthorized access attempts are logged and monitored.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
