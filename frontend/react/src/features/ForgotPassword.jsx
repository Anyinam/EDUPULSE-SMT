import React, { useState } from 'react';
import axios from 'axios';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';

export default function ForgotPassword() {
  const [form, setForm] = useState({ schoolCode: '', email: '' });
  const [status, setStatus] = useState({ type: '', msg: '' });
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: 'info', msg: 'Processing...' });
    try {
      const res = await axios.post('/api/forgot-password', {
        schoolCode: form.schoolCode.trim().toUpperCase(),
        email: form.email.trim()
      });
      setStatus({ type: 'success', msg: res.data.message });
    } catch (err) {
      setStatus({ type: 'error', msg: "Request failed. Please try again." });
    }
  };

  return (
    <div className="min-h-screen flex bg-white font-sans">
      {/* Left Side - Branding */}
      <div className="hidden lg:flex w-1/2 bg-slate-900 items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 bg-linear-to-br from-slate-900 to-blue-900 opacity-90 z-10"></div>
        <div className="relative z-20 text-white p-12 max-w-xl text-center">
            <div className="w-20 h-20 bg-white/10 backdrop-blur-md rounded-full flex items-center justify-center mb-6 border border-white/20 shadow-xl mx-auto">
                <span className="text-4xl">🔐</span>
            </div>
            <h2 className="text-4xl font-black mb-4">Account Recovery</h2>
            <p className="text-blue-200 text-lg">
                "Secure access restoration for EduPulse tenants."
            </p>
        </div>
      </div>

      {/* Right Side - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-24">
        <form onSubmit={handleSubmit} className="w-full max-w-md">
          <h1 className="text-3xl font-bold text-slate-800 mb-2">Forgot Password?</h1>
          <p className="text-slate-500 mb-8">Enter your organization ID and email to receive a reset link.</p>
          
          {status.msg && (
            <div className={`p-4 rounded-xl mb-6 text-sm font-bold ${status.type === 'success' ? 'bg-green-50 text-green-700' : status.type === 'error' ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'}`}>
              {status.msg}
            </div>
          )}

          <div className="space-y-5">
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Organization ID</label>
              <input className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none uppercase font-mono" placeholder="e.g. CCA-OFK" onChange={e => setForm({...form, schoolCode: e.target.value})} required />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Registered Email</label>
              <input type="email" className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none" placeholder="staff@school.edu" onChange={e => setForm({...form, email: e.target.value})} required />
            </div>
          </div>

          <button className="w-full bg-slate-800 text-white p-4 rounded-xl font-bold mt-8 hover:bg-slate-700 transition-all shadow-lg">Send Reset Link</button>
          <p className="text-center mt-8 text-sm text-slate-400"><a href="/login" className="text-blue-600 font-bold hover:underline">Back to Login</a></p>

          <div className="mt-4 p-4 bg-white border border-slate-200 rounded-xl">
            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Legal Policies</p>
            <p className="text-sm text-slate-600">By creating a school account, you accept our Terms of Service, Privacy Policy, and Data Retention Policy.</p>
            <div className="mt-2 text-sm flex flex-wrap gap-3">
              <button type="button" onClick={() => setShowTerms(true)} className="text-blue-600 font-semibold hover:underline">Terms of Service</button>
              <button type="button" onClick={() => setShowPrivacy(true)} className="text-blue-600 font-semibold hover:underline">Privacy Policy</button>
              <button type="button" onClick={() => setShowRetention(true)} className="text-blue-600 font-semibold hover:underline">Data Retention Policy</button>
            </div>
          </div>

          <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
          <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
          <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
        </form>
      </div>
    </div>
  );
}