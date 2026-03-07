import React, { useState } from 'react';
import axios from 'axios';

export default function ResetPassword() {
  const [password, setPassword] = useState('');
  const [status, setStatus] = useState({ type: '', msg: '' });

  const handleSubmit = async (e) => {
    e.preventDefault();
    const searchParams = new URLSearchParams(window.location.search);
    const token = searchParams.get('token');

    if (!token) {
      setStatus({ type: 'error', msg: "Invalid or missing reset token." });
      return;
    }

    try {
      await axios.post('/api/reset-password', { token, password });
      setStatus({ type: 'success', msg: "Password reset successfully!" });
      setTimeout(() => window.location.href = '/login', 2000);
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.message || "Reset failed. Token may be expired." });
    }
  };

  return (
    <div className="min-h-screen flex bg-white font-sans items-center justify-center p-6">
      <div className="w-full max-w-md bg-white p-8 rounded-3xl shadow-xl border border-slate-100">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">🔑</div>
          <h1 className="text-2xl font-black text-slate-800">Set New Password</h1>
          <p className="text-slate-500">Enter your new secure password below.</p>
        </div>

        {status.msg && (
          <div className={`p-4 rounded-xl mb-6 text-sm font-bold text-center ${status.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
            {status.msg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">New Password</label>
            <input 
              type="password" 
              className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none" 
              placeholder="••••••••" 
              onChange={e => setPassword(e.target.value)} 
              required 
              minLength={6}
            />
          </div>

          <button className="w-full bg-blue-900 text-white p-4 rounded-xl font-bold hover:bg-blue-800 transition-all shadow-lg">Reset Password</button>
        </form>
      </div>
    </div>
  );
}