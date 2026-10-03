import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { ArrowRight, Loader } from 'lucide-react';
import PublicSiteLayout from '../components/PublicSiteLayout';
import TermsModal from '../components/TermsModal';
import PrivacyModal from '../components/PrivacyModal';
import DataRetentionModal from '../components/DataRetentionModal';
import '../styles/public-auth.css';

export default function ForgotPassword() {
  const [form, setForm] = useState({ schoolCode: '', email: '' });
  const [status, setStatus] = useState({ type: '', msg: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitting = useRef(false);
  const [showTerms, setShowTerms] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showRetention, setShowRetention] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setIsSubmitting(true);
    setStatus({ type: '', msg: '' });
    try {
      const res = await axios.post('/api/forgot-password', {
        schoolCode: form.schoolCode.trim().toUpperCase(),
        email: form.email.trim()
      });
      setStatus({ type: 'success', msg: res.data.message || 'If an account exists, a reset link has been sent.' });
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.message || 'Request failed. Please try again.' });
    } finally {
      submitting.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <PublicSiteLayout>
      <section className="public-auth" aria-labelledby="recovery-heading">
        <div className="public-auth-heading">
          <h1 id="recovery-heading">Forgot password?</h1>
          <p>Enter your school ID and registered email to receive a reset link.</p>
        </div>
        {status.msg && <div className={status.type === 'error' ? 'public-auth-error' : 'public-auth-notice'} role={status.type === 'error' ? 'alert' : 'status'}>{status.msg}</div>}
        <form onSubmit={handleSubmit} aria-label="Request password reset" aria-busy={isSubmitting}>
          <div className="public-auth-fields">
            <div className="public-auth-field">
              <label htmlFor="recovery-school">School ID</label>
              <input id="recovery-school" name="schoolCode" placeholder="e.g. CCA-OFK" value={form.schoolCode} onChange={event => setForm({ ...form, schoolCode: event.target.value })} autoComplete="organization" required disabled={isSubmitting} />
            </div>
            <div className="public-auth-field">
              <label htmlFor="recovery-email">Registered email</label>
              <input id="recovery-email" name="email" type="email" placeholder="staff@school.edu" value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} autoComplete="email" required disabled={isSubmitting} />
            </div>
          </div>
          <button type="submit" className="public-auth-primary" disabled={isSubmitting}>
            {isSubmitting ? <Loader size={18} className="public-auth-spinner" aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
            {isSubmitting ? 'Sending...' : 'Send reset link'}
          </button>
        </form>
        <p className="public-auth-switch"><Link to="/login">Back to login</Link></p>
        <aside className="public-auth-help" aria-label="Account policies">
          <details>
            <summary>Legal policies</summary>
            <div className="public-auth-legal">
              <button type="button" onClick={() => setShowTerms(true)} className="public-auth-link">Terms of Service</button>
              <button type="button" onClick={() => setShowPrivacy(true)} className="public-auth-link">Privacy Policy</button>
              <button type="button" onClick={() => setShowRetention(true)} className="public-auth-link">Data Retention Policy</button>
            </div>
          </details>
        </aside>
      </section>
      <TermsModal isOpen={showTerms} onClose={() => setShowTerms(false)} />
      <PrivacyModal isOpen={showPrivacy} onClose={() => setShowPrivacy(false)} />
      <DataRetentionModal isOpen={showRetention} onClose={() => setShowRetention(false)} />
    </PublicSiteLayout>
  );
}