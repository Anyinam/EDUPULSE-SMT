import React, { useEffect, useState } from 'react';
import axios from 'axios';
import PublicSiteLayout from '../components/PublicSiteLayout';
import { ArrowRight, Loader } from 'lucide-react';
import '../styles/public-auth.css';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';
import { getAuthToken, validateTokenExpiry } from '../utils/authUtils';

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
    login_title: 'Welcome back',
    login_subtitle: 'Sign in to your school account.'
  }
};

export default function Login() {
  const [creds, setCreds] = useState({ schoolCode: '', username: '', password: '' });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
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
      } catch {
        setPublicContent(DEFAULT_PUBLIC_CONTENT);
      }
    };
    fetchPublicContent();
  }, []);

  useEffect(() => {
    if (getAuthToken() && validateTokenExpiry()) {
      sessionStorage.removeItem('session_expired_message');
      window.location.replace(localStorage.getItem('post_login_target') || '/proprietor');
      return;
    }

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
    if (isSubmitting) return;
    setIsSubmitting(true);
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
      const msg = err.response?.data?.message || 'Check your school ID, staff username or email, and password.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerify2fa = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
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
    } finally {
      setIsSubmitting(false);
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
    sessionStorage.removeItem('session_expired_message');
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
    <PublicSiteLayout>
      <section className="public-auth public-auth--login" aria-labelledby="login-title">
        <div className="public-auth-heading">
          <h1 id="login-title">Welcome back</h1>
          <p>{twoFaStep ? 'Enter the verification code sent to your email.' : DEFAULT_PUBLIC_CONTENT.auth.login_subtitle}</p>
        </div>
        <form onSubmit={twoFaStep ? handleVerify2fa : handleLogin} aria-busy={isSubmitting}>
          {isDevTwoFaFallback && <p className="public-auth-notice">Development Mode: Email Delivery Fallback</p>}
          {error && <p className="public-auth-error" role="alert">{error}</p>}
          {twoFaStep && twoFaHint && <p className="public-auth-notice" role="status">{twoFaHint}</p>}
          {twoFaStep && resendMessage && <p className="public-auth-notice" role="status">{resendMessage}</p>}
          <div className="public-auth-fields">
            <div className="public-auth-field">
              <label htmlFor="login-school">School ID</label>
              <input id="login-school" placeholder="e.g. CCA-OFK" value={creds.schoolCode} onChange={e => setCreds({...creds, schoolCode: e.target.value.toUpperCase()})} required disabled={twoFaStep || isSubmitting} autoComplete="organization" />
            </div>
            <div className="public-auth-field">
              <label htmlFor="login-username">Staff username or email</label>
              <input id="login-username" placeholder="Username or email" value={creds.username} onChange={e => setCreds({...creds, username: e.target.value})} required disabled={twoFaStep || isSubmitting} autoComplete="username" />
            </div>
            {!twoFaStep ? (
              <div className="public-auth-field">
                <label htmlFor="login-password">Password</label>
                <input id="login-password" type="password" placeholder="Your password" value={creds.password} onChange={e => setCreds({...creds, password: e.target.value})} required disabled={isSubmitting} autoComplete="current-password" />
                <a href="/forgot-password" className="public-auth-recovery">Forgot password?</a>
              </div>
            ) : (
              <div className="public-auth-field">
                <label htmlFor="login-code">Verification code</label>
                <input id="login-code" placeholder="000000" value={twoFaCode} onChange={e => setTwoFaCode(e.target.value)} required disabled={isSubmitting} autoComplete="one-time-code" />
                <div className="public-auth-code-actions">
                  <button type="button" onClick={handleResend2faCode} disabled={resendCooldown > 0 || isResendingCode || isSubmitting} className="public-auth-link">
                    {isResendingCode ? 'Resending...' : resendCooldown > 0 ? `Resend Code in ${resendCooldown}s` : 'Resend Code'}
                  </button>
                  <span>Code expires in 10 minutes</span>
                </div>
              </div>
            )}
          </div>
          <button type="submit" className="public-auth-primary" disabled={isSubmitting || isResendingCode}>
            {isSubmitting ? <Loader size={18} className="public-auth-spinner" /> : <ArrowRight size={18} />}
            {isSubmitting ? 'Please wait...' : twoFaStep ? 'Verify & Continue' : 'Log in'}
          </button>
        </form>
        <p className="public-auth-switch">New to EduPulse SMT? <a href="/register">Create your school account</a></p>
        <aside className="public-auth-help" aria-label="Account help and policies">
          <details>
            <summary>Contact & support</summary>
            <p><a href={`mailto:${publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}`}>{publicContent.support?.email || DEFAULT_PUBLIC_CONTENT.support.email}</a><br /><a href={`tel:${(publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone).replace(/\s+/g, '')}`}>{publicContent.support?.phone || DEFAULT_PUBLIC_CONTENT.support.phone}</a></p>
            <p>Typical response time: {publicContent.support?.response_time || DEFAULT_PUBLIC_CONTENT.support.response_time}.</p>
          </details>
          <details>
            <summary>Legal policies</summary>
            <div className="public-auth-legal">
              <button type="button" onClick={() => setShowTerms(true)} className="public-auth-link">Terms of Service</button>
              <button type="button" onClick={() => setShowPrivacy(true)} className="public-auth-link">Privacy Policy</button>
              <button type="button" onClick={() => setShowRetention(true)} className="public-auth-link">Data Retention Policy</button>
            </div>
          </details>
          <details>
            <summary>Frequently asked questions</summary>
            {(publicContent.faqs || []).map((faq, index) => <details key={`${faq.question}-${index}`}><summary>{faq.question}</summary><p>{faq.answer}</p></details>)}
          </details>
        </aside>
      </section>
      <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
      <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
      <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
    </PublicSiteLayout>
  );
}