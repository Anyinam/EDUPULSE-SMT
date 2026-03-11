import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Logo } from '../components/Logo';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';

const SUPPORT_CONTACT = {
  email: 'support@edupulse.com',
  phone: '+233 552 141 384'
};

const DEFAULT_HELP_CONTENT = {
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
      question: 'How do I reset my password?',
      answer: 'Use Forgot Password on this page, then verify your email reset link.'
    }
  ],
  tutorials: [
    { title: 'How to upload students (CSV)', url: 'https://www.youtube.com/watch?v=5v5wQ5M3jX8' },
    { title: 'How to configure promotion thresholds', url: 'https://www.youtube.com/watch?v=8YxY7mTjM6Q' },
    { title: 'How to build and print terminal reports', url: 'https://www.youtube.com/watch?v=Q5l2Qh4Aq_0' }
  ]
};

export default function Login() {
  const [creds, setCreds] = useState({ schoolCode: '', username: '', password: '' });
  const [error, setError] = useState('');
  const [twoFaToken, setTwoFaToken] = useState('');
  const [twoFaCode, setTwoFaCode] = useState('');
  const [twoFaStep, setTwoFaStep] = useState(false);
  const [helpContent, setHelpContent] = useState(DEFAULT_HELP_CONTENT);
  const [ownerKey, setOwnerKey] = useState('');
  const [ownerMessage, setOwnerMessage] = useState('');
  const [isSavingOwnerContent, setIsSavingOwnerContent] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);

  const ownerModeEnabled = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('owner') === '1';
  }, []);

  useEffect(() => {
    const fetchHelpContent = async () => {
      try {
        const res = await axios.get('/api/public/help-content');
        const faqs = Array.isArray(res.data?.faqs) ? res.data.faqs : DEFAULT_HELP_CONTENT.faqs;
        const tutorials = Array.isArray(res.data?.tutorials) ? res.data.tutorials : DEFAULT_HELP_CONTENT.tutorials;
        setHelpContent({ faqs, tutorials });
      } catch (err) {
        setHelpContent(DEFAULT_HELP_CONTENT);
      }
    };
    fetchHelpContent();
  }, []);

  const updateFaq = (index, field, value) => {
    setHelpContent((prev) => ({
      ...prev,
      faqs: prev.faqs.map((row, i) => (i === index ? { ...row, [field]: value } : row))
    }));
  };

  const addFaq = () => {
    setHelpContent((prev) => ({
      ...prev,
      faqs: [...prev.faqs, { question: '', answer: '' }]
    }));
  };

  const removeFaq = (index) => {
    setHelpContent((prev) => ({
      ...prev,
      faqs: prev.faqs.filter((_, i) => i !== index)
    }));
  };

  const handleOwnerSave = async () => {
    setOwnerMessage('');
    if (!ownerKey.trim()) {
      setOwnerMessage('Platform owner key is required.');
      return;
    }

    try {
      setIsSavingOwnerContent(true);
      const payload = {
        faqs: helpContent.faqs,
        tutorials: helpContent.tutorials
      };

      await axios.put('/api/platform/help-content', payload, {
        headers: {
          'X-Platform-Owner-Key': ownerKey.trim()
        }
      });

      setOwnerMessage('Global help content updated successfully.');
    } catch (err) {
      setOwnerMessage(err.response?.data?.message || 'Failed to update global help content.');
    } finally {
      setIsSavingOwnerContent(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    try {
      // Trim whitespace to prevent copy-paste errors
      const payload = {
        schoolCode: creds.schoolCode.trim(),
        username: creds.username.trim(),
        password: creds.password
      };

      const res = await axios.post('/api/login', payload);

      if (res.status === 202 && res.data?.message === '2fa_required') {
        setTwoFaToken(res.data.token || '');
        setTwoFaStep(true);
        return;
      }
      
      // Store Business Credentials & Branding (Requirement 1 & 2)
      localStorage.setItem('token', res.data.token);
      localStorage.setItem('school_id', res.data.school_id);
      const roles = Array.isArray(res.data.roles) ? res.data.roles : [res.data.role].filter(Boolean);
      localStorage.setItem('role', res.data.role);
      localStorage.setItem('roles', JSON.stringify(roles));
      localStorage.setItem('assigned_class', res.data.assigned_class || '');
      localStorage.setItem('subscription_plan', res.data.subscription_plan);
      localStorage.setItem('enabled_modules', JSON.stringify(res.data.enabled_modules || {}));
      localStorage.setItem('branding', JSON.stringify(res.data.branding));
      localStorage.setItem('branding_school_id', res.data.school_id);

      // Redirect based on Multi-level Access Control (Requirement 5)
      let target = '/teacher';
      if (roles.includes('proprietor')) {
        target = '/proprietor';
      } else if (roles.includes('headmaster')) {
        target = '/headmaster';
      } else if (roles.includes('finance')) {
        target = '/finance';
      } else if (roles.includes('inventory_manager')) {
        target = '/inventory';
      } else if (roles.includes('kitchen')) {
        target = '/kitchen';
      } else if ((roles.includes('homeroom') || roles.includes('teacher')) && res.data.assigned_class) {
        // Homeroom Teachers get their specific dashboard
        target = '/homeroom';
      }
      window.location.href = target;
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

      localStorage.setItem('token', res.data.token);
      localStorage.setItem('school_id', res.data.school_id);
      const roles = Array.isArray(res.data.roles) ? res.data.roles : [res.data.role].filter(Boolean);
      localStorage.setItem('role', res.data.role);
      localStorage.setItem('roles', JSON.stringify(roles));
      localStorage.setItem('assigned_class', res.data.assigned_class || '');
      localStorage.setItem('subscription_plan', res.data.subscription_plan);
      localStorage.setItem('enabled_modules', JSON.stringify(res.data.enabled_modules || {}));
      localStorage.setItem('branding', JSON.stringify(res.data.branding));
      localStorage.setItem('branding_school_id', res.data.school_id);

      let target = '/teacher';
      if (roles.includes('proprietor')) {
        target = '/proprietor';
      } else if (roles.includes('headmaster')) {
        target = '/headmaster';
      } else if (roles.includes('finance')) {
        target = '/finance';
      } else if (roles.includes('inventory_manager')) {
        target = '/inventory';
      } else if (roles.includes('kitchen')) {
        target = '/kitchen';
      } else if ((roles.includes('homeroom') || roles.includes('teacher')) && res.data.assigned_class) {
        target = '/homeroom';
      }
      window.location.href = target;
    } catch (err) {
      const msg = err.response?.data?.message || 'Invalid verification code';
      setError(msg);
    }
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

          <h1 className="text-3xl font-bold text-slate-800 mb-2">Welcome Back</h1>
          <p className="text-slate-500 mb-8">
            {twoFaStep ? 'Enter the verification code sent to your email.' : 'Enter your business credentials to access the dashboard.'}
          </p>
          
          {error && <div className="bg-red-50 text-red-600 p-4 rounded-xl mb-6 text-sm font-bold flex items-center gap-2">⚠️ {error}</div>}

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
              <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Staff Username</label>
              <input 
                className="w-full border border-slate-200 bg-slate-50 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition-all" 
                placeholder="Username" 
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
              <p className="text-slate-700">Email: <a href={`mailto:${SUPPORT_CONTACT.email}`} className="text-blue-600 font-semibold hover:underline">{SUPPORT_CONTACT.email}</a></p>
              <p className="text-slate-700">Phone/WhatsApp: <a href={`tel:${SUPPORT_CONTACT.phone.replace(/\s+/g, '')}`} className="text-blue-600 font-semibold hover:underline">{SUPPORT_CONTACT.phone}</a></p>
            </div>
            <p className="text-xs text-slate-500 mt-2">Typical response time: within 24 hours on business days.</p>
          </div>

          <div className="mt-4 p-4 bg-white border border-slate-200 rounded-xl">
            <p className="text-xs font-bold text-slate-500 uppercase mb-3">FAQ</p>
            <div className="space-y-3 text-sm">
              {helpContent.faqs.map((faq, index) => (
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

          {ownerModeEnabled && (
            <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-xl">
              <p className="text-xs font-bold text-amber-700 uppercase mb-3">Platform Owner • Global Help Content</p>
              <p className="text-xs text-amber-800 mb-3">This editor updates FAQ content for all tenants globally.</p>

              <div className="mb-4">
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Platform Owner Key</label>
                <input
                  type="password"
                  value={ownerKey}
                  onChange={(e) => setOwnerKey(e.target.value)}
                  className="w-full border border-slate-200 bg-white p-2 rounded-lg"
                  placeholder="Enter PLATFORM_OWNER_KEY"
                />
              </div>

              <div className="space-y-3 mb-4">
                <p className="text-xs font-bold text-slate-500 uppercase">FAQ Items</p>
                {helpContent.faqs.map((faq, index) => (
                  <div key={`edit-faq-${index}`} className="p-3 bg-white border border-slate-200 rounded-lg space-y-2">
                    <input
                      value={faq.question}
                      onChange={(e) => updateFaq(index, 'question', e.target.value)}
                      className="w-full border border-slate-200 p-2 rounded-lg"
                      placeholder="Question"
                    />
                    <textarea
                      value={faq.answer}
                      onChange={(e) => updateFaq(index, 'answer', e.target.value)}
                      className="w-full border border-slate-200 p-2 rounded-lg"
                      placeholder="Answer"
                      rows={2}
                    />
                    <button type="button" onClick={() => removeFaq(index)} className="text-xs text-red-600 font-semibold hover:underline">Remove</button>
                  </div>
                ))}
                <button type="button" onClick={addFaq} className="text-xs font-semibold text-blue-700 hover:underline">+ Add FAQ</button>
              </div>

              {ownerMessage && <p className="text-xs font-semibold text-slate-700 mb-3">{ownerMessage}</p>}

              <button
                type="button"
                disabled={isSavingOwnerContent}
                onClick={handleOwnerSave}
                className="w-full bg-slate-900 text-white py-2 rounded-lg font-semibold hover:bg-slate-800 disabled:opacity-50"
              >
                {isSavingOwnerContent ? 'Saving...' : 'Save Global Help Content'}
              </button>
            </div>
          )}

          <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
          <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
          <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
        </form>
      </div>
    </div>
  );
}