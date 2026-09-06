import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Logo } from '../components/Logo';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';

const DEFAULT_PUBLIC_CONTENT = {
  faqs: [
    {
      question: 'How do I upload students in bulk?',
      answer: 'Go to Admissions, use the CSV upload section, and ensure required columns match the template.'
    },
    {
      question: 'Who can approve terminal reports?',
      answer: 'Homeroom submits, Headmaster reviews, and Proprietor gives final approval based on workflow.'
    },
    {
      question: 'Do diagnostic mock strands appear on terminal reports?',
      answer: 'Yes. Teachers can add diagnostic strands in Report Builder, and they will show in a separate Diagnostic Strand Insights section on the terminal report.'
    },
    {
      question: 'How do I reset my password?',
      answer: 'Use Forgot Password on this page, then verify your email reset link.'
    }
  ],
  tutorials: [
    { title: 'How to upload students (CSV)', url: 'https://www.youtube.com/watch?v=5v5wQ5M3jX8' },
    { title: 'How to configure promotion thresholds', url: 'https://www.youtube.com/watch?v=8YxY7mTjM6Q' },
    { title: 'How to build and print terminal reports', url: 'https://www.youtube.com/watch?v=Q5l2Qh4Aq_0' },
    { title: 'How diagnostic strands appear on terminal reports', url: 'https://www.youtube.com/watch?v=Q5l2Qh4Aq_0' }
  ],
  support: {
    email: 'info@edupulsesmt.com',
    phone: '+233 552 141 384',
    response_time: 'within 24 hours on business days'
  },
  auth: {
    login_title: 'Welcome Back',
    login_subtitle: 'Enter your business credentials to access the dashboard.'
  }
};

export default function Login() {
  const [creds, setCreds] = useState({ schoolCode: '', username: '', password: '' });
  const [error, setError] = useState('');
  const [twoFaToken, setTwoFaToken] = useState('');
  const [twoFaCode, setTwoFaCode] = useState('');
  const [twoFaStep, setTwoFaStep] = useState(false);
  const [twoFaHint, setTwoFaHint] = useState('');
  const [resendMessage, setResendMessage] = useState('');
  const [isResendingCode, setIsResendingCode] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [publicContent, setPublicContent] = useState(DEFAULT_PUBLIC_CONTENT);
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);

  const isDevTwoFaFallback = twoFaStep && Boolean(twoFaHint);

  useEffect(() => {
    const fetchPublicContent = async () => {
      try {
        const res = await axios.get('/api/public/platform-content');
        setPublicContent((prev) => ({ ...prev, ...res.data }));
      } catch (err) {
        setPublicContent(DEFAULT_PUBLIC_CONTENT);
      }
    };
    fetchPublicContent();
  }, []);

  useEffect(() => {
    const expiredMessage = sessionStorage.getItem('session_expired_message');
    if (!expiredMessage) {
      return;
    }
    setError(expiredMessage);
    sessionStorage.removeItem('session_expired_message');
  }, []);

  useEffect(() => {
    if (resendCooldown <= 0) return undefined;
    const timer = window.setInterval(() => {
      setResendCooldown((current) => (current > 0 ? current - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendCooldown]);

  const enterTwoFaStep = (payload) => {
    setTwoFaToken(payload.token || '');
    setTwoFaCode(payload.dev_code || '');
    setTwoFaHint(
      payload?.fallback_notice
        ? `${payload.fallback_notice}${payload.dev_code ? ` Verification code: ${payload.dev_code}` : ''}`
        : ''
    );
    setResendMessage('');
    setResendCooldown(30);
    setTwoFaStep(true);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setTwoFaHint('');
    setResendMessage('');
    try {
      // Trim whitespace to prevent copy-paste errors
      const payload = {
        schoolCode: creds.schoolCode.trim(),
        username: creds.username.trim(),
        password: creds.password
      };

      const res = await axios.post('/api/login', payload);

      if (res.status === 202 && res.data?.message === '2fa_required') {
        enterTwoFaStep(res.data);
        return;
      }
      
      persistAuthAndRedirect(res.data);
    } catch (err) {
      // Display specific error from backend if available
      const msg = err.response?.data?.message || 'Invalid School Code or Business Credentials';
      setError(msg);
    }
  };

  const handleVerify2fa = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const res = await axios.post('/api/2fa/verify', {
        token: twoFaToken,
        code: twoFaCode.trim()
      });

      persistAuthAndRedirect(res.data);
    } catch (err) {
      const msg = err.response?.data?.message || 'Invalid verification code';
      setError(msg);
    }
  };

  const handleResend2faCode = async () => {
    if (!twoFaToken || resendCooldown > 0 || isResendingCode) return;

    setError('');
    setResendMessage('');
    try {
      setIsResendingCode(true);
      const res = await axios.post('/api/2fa/resend', { token: twoFaToken });
      setTwoFaCode(res.data.dev_code || '');
      setTwoFaToken(res.data.token || twoFaToken);
      setTwoFaHint(
        res.data?.fallback_notice
          ? `${res.data.fallback_notice}${res.data.dev_code ? ` Verification code: ${res.data.dev_code}` : ''}`
          : ''
      );
      setResendMessage(res.data.message || 'Verification code resent.');
      setResendCooldown(30);
    } catch (err) {
      setError(err.response?.data?.message || 'Unable to resend verification code.');
    } finally {
      setIsResendingCode(false);
    }
  };

  const resolveTarget = (roles, assignedClass) => {
    if (roles.includes('proprietor')) {
      return '/proprietor';
    }
    if (roles.includes('headmaster')) {
      return '/headmaster';
    }
    if (roles.includes('finance')) {
      return '/finance';
    }
    if (roles.includes('inventory_manager')) {
      return '/inventory';
    }
    if (roles.includes('kitchen')) {
      return '/kitchen';
    }
    if ((roles.includes('homeroom') || roles.includes('teacher')) && assignedClass) {
      return '/homeroom';
    }
    return '/teacher';
  };

  const persistAuthAndRedirect = (authData) => {
    localStorage.setItem('token', authData.token);
    localStorage.setItem('school_id', authData.school_id);
    const roles = Array.isArray(authData.roles) ? authData.roles : [authData.role].filter(Boolean);
    localStorage.setItem('role', authData.role);
    localStorage.setItem('roles', JSON.stringify(roles));
    localStorage.setItem('assigned_class', authData.assigned_class || '');
    localStorage.setItem('subscription_plan', authData.subscription_plan);
    localStorage.setItem('enabled_modules', JSON.stringify(authData.enabled_modules || {}));
    localStorage.setItem('branding', JSON.stringify(authData.branding));
    localStorage.setItem('branding_school_id', authData.school_id);

    const target = resolveTarget(roles, authData.assigned_class);
    localStorage.setItem('post_login_target', target);

    if (authData.requires_password_reset) {
      localStorage.setItem('requires_password_reset', 'true');
      window.location.href = '/first-login-password';
      return;
    }

    localStorage.removeItem('requires_password_reset');
    window.location.href = target;
  };

  return (
    <div className="min-h-screen flex bg-white font-sans">
      {/* Left Side - Branding */}
      <div className="hidden lg:flex w-1/2 bg-blue-900 items-center justify-center relative overflow-hidden">
        <div className="absolute inset-0 bg-linear-to-br from-blue-900 to-slate-900 opacity-90 z-10"></div>
        <img src="https://images.unsplash.com/photo-1523050854058-8df90110c9f1?ixlib=rb-4.0.3&auto=format&fit=crop&w=1350&q=80" className="absolute inset-0 w-full h-full object-cover" alt="School" />
        <div className="relative z-20 text-white p-12 max-w-xl">
            <div className="w-16 h-16 bg-white/10 backdrop-blur-md rounded-2xl flex items-center justify-center mb-6 border border-white/20 shadow-xl" style={{background: 'rgba(102, 126, 234, 0.2)'}}
            >
                <Logo size="lg" variant="default" />
            </div>
            <h2 className="text-5xl font-black mb-6 leading-tight">Governance with Pulse.</h2>
            <p className="text-blue-200 text-lg leading-relaxed">
                Smart school management technology designed for modern education.
            </p>
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 lg:p-24">
        <form onSubmit={twoFaStep ? handleVerify2fa : handleLogin} className="w-full max-w-md">
          <div className="flex items-center gap-2 mb-8">
            <div className="w-10 h-10 bg-blue-900 rounded-lg flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-blue-200">E</div>
            <span className="text-2xl font-black text-blue-900 tracking-tighter">EDUPULSE SMT</span>
          </div>

          <h1 className="text-3xl font-bold text-slate-800 mb-2">{publicContent.auth?.login_title || DEFAULT_PUBLIC_CONTENT.auth.login_title}</h1>
          <p className="text-slate-500 mb-8">
            {twoFaStep ? 'Enter the verification code sent to your email.' : (publicContent.auth?.login_subtitle || DEFAULT_PUBLIC_CONTENT.auth.login_subtitle)}
          </p>

          {isDevTwoFaFallback && (
            <div className="inline-flex items-center gap-2 mb-4 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-amber-800">
              <span>Development Mode</span>
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500"></span>
              <span>Email Delivery Fallback</span>
            </div>
          )}
          
          {error && <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6 text-sm font-bold flex items-center gap-2">⚠️ {error}</div>}
          {twoFaStep && twoFaHint && (
            <div className="bg-blue-50 text-blue-700 p-4 rounded-xl mb-6 text-sm font-semibold">
              {twoFaHint}
            </div>
          )}
          {twoFaStep && resendMessage && (
            <div className="bg-green-50 text-green-700 p-4 rounded-xl mb-6 text-sm font-semibold">
              {resendMessage}
            </div>
          )}

          <div className="space-y-5">
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Organization ID</label>
              <input 
                className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all font-mono" 
                placeholder="e.g. CCA-OFK" 
                onChange={e => setCreds({...creds, schoolCode: e.target.value.toUpperCase()})} 
                required
                disabled={twoFaStep}
              />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Staff Username Or Email</label>
              <input 
                className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                placeholder="Username or email" 
                onChange={e => setCreds({...creds, username: e.target.value})} 
                required
                disabled={twoFaStep}
              />
            </div>
            {!twoFaStep ? (
              <div>
                <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Password</label>
                <input 
                  className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                  type="password" 
                  placeholder="••••••••" 
                  onChange={e => setCreds({...creds, password: e.target.value})} 
                  required
                />
                <div className="text-right mt-2">
                  <a href="/forgot-password" className="text-xs font-bold text-blue-600 hover:underline">Forgot Password?</a>
                </div>
              </div>
            ) : (
              <div>
                <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Verification Code</label>
                <input
                  className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all font-mono tracking-widest"
                  placeholder="000000"
                  value={twoFaCode}
                    onChange={e => setTwoFaCode(e.target.value)}
                    required
                  />
                  <div className="mt-2 flex items-center justify-between gap-3 text-xs">
                    <button
                      type="button"
                      onClick={handleResend2faCode}
                      disabled={resendCooldown > 0 || isResendingCode}
                      className="font-bold text-blue-600 hover:underline disabled:text-slate-400 disabled:no-underline"
                    >
                      {isResendingCode
                        ? 'Resending...'
                        : resendCooldown > 0
                        ? `Resend Code in ${resendCooldown}s`
                        : 'Resend Code'}
                    </button>
                    <span className="text-slate-400">Code expires in 10 minutes</span>
                  </div>
                </div>
              )}
            </div>

          <button className="w-full bg-blue-900 text-white p-4 rounded-xl font-bold mt-8 hover:bg-blue-800 transition-all shadow-xl shadow-blue-200">
            {twoFaStep ? 'Verify & Continue' : 'Sign In to Dashboard'}
          </button>

          <p className="text-center mt-8 text-sm text-slate-400">
            New Tenant? <a href="/register" className="text-blue-600 font-bold hover:underline">Create Credentials</a>
          </p>

          <div className="mt-4 p-4 bg-white border border-slate-200 rounded-xl">
            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Legal Policies</p>
            <p className="text-sm text-slate-600">By creating a school account, you accept our Terms of Service, Privacy Policy, and Data Retention Policy.</p>
            <div className="mt-2 text-sm flex flex-wrap gap-3">
              <button type="button" onClick={() => setShowTerms(true)} className="text-blue-600 font-semibold hover:underline">Terms of Service</button>
              <button type="button" onClick={() => setShowPrivacy(true)} className="text-blue-600 font-semibold hover:underline">Privacy Policy</button>
              <button type="button" onClick={() => setShowRetention(true)} className="text-blue-600 font-semibold hover:underline">Data Retention Policy</button>
            </div>
          </div>

          <div className="mt-6 p-4 bg-slate-50 border border-slate-200 rounded-xl">
            <p className="text-xs font-bold text-slate-500 uppercase mb-2">Contact & Support</p>
            <p className="text-sm text-slate-600">Need help with setup or access?</p>
            <div className="mt-2 text-sm">
              <p className="text-slate-700">Email: <a href={`mailto:${publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}`} className="text-blue-600 font-semibold hover:underline">{publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}</a></p>
              <p className="text-slate-700">Phone/WhatsApp: <a href={`tel:${(publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone).replace(/\s+/g, '')}`} className="text-blue-600 font-semibold hover:underline">{publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone}</a></p>
            </div>
            <p className="text-xs text-slate-500 mt-2">Typical response time: {publicContent.support?.response_time || DEFAULT_PUBLIC_CONTENT.support.response_time}.</p>
          </div>

          <div className="mt-4 p-4 bg-white border border-slate-200 rounded-xl">
            <p className="text-xs font-bold text-slate-500 uppercase mb-3">FAQ</p>
            <div className="space-y-3 text-sm">
              {(publicContent.faqs || []).map((faq, index) => (
                <details key={`${faq.question}-${index}`} className="group">
                  <summary className="cursor-pointer font-semibold text-slate-700">{faq.question}</summary>
                  <p className="mt-1 text-slate-600">{faq.answer}</p>
                </details>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
              Tutorials:{' '}
              <a href="/help#tutorials" className="text-blue-600 font-semibold hover:underline">
                View updates (coming after production launch)
              </a>
            </p>
          </div>

          <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
          <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
          <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
        </form>
      </div>
    </div>
  );
}