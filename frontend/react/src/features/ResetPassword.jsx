import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, Loader } from 'lucide-react';
import PublicSiteLayout from '../components/PublicSiteLayout';
import '../styles/public-auth.css';

export default function ResetPassword() {
  const { search } = useLocation();
  const token = new URLSearchParams(search).get('token');
  const hasToken = Boolean(token?.trim());
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [status, setStatus] = useState({ type: '', msg: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitting = useRef(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting.current || status.type === 'success' || !hasToken) return;
    const effectivePassword = password.trim();
    if (effectivePassword.length < 8 || !/[A-Z]/.test(effectivePassword) || !/[0-9]/.test(effectivePassword)) {
      setStatus({ type: 'error', msg: 'Password must be at least 8 characters and contain an uppercase letter and a digit.' });
      return;
    }
    if (confirmation && confirmation !== password) {
      setStatus({ type: 'error', msg: 'Passwords do not match.' });
      return;
    }
    submitting.current = true;
    setIsSubmitting(true);
    setStatus({ type: '', msg: '' });
    try {
      await axios.post('/api/reset-password', { token, password });
      setStatus({ type: 'success', msg: 'Password reset successfully! You can now log in with your new password.' });
    } catch (err) {
      setStatus({ type: 'error', msg: err.response?.data?.message || "Reset failed. Token may be expired." });
    } finally {
      submitting.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <PublicSiteLayout>
      <section className="public-auth" aria-labelledby="reset-heading">
        <div className="public-auth-heading">
          <h1 id="reset-heading">Set new password</h1>
          <p>Restore access to your EduPulse SMT account.</p>
        </div>
        {!hasToken ? (
          <>
            <div className="public-auth-error" role="alert">Invalid or missing reset token.</div>
            <Link to="/forgot-password">Request a new reset link</Link>
          </>
        ) : (
          <>
            {status.msg && <div className={status.type === 'error' ? 'public-auth-error' : 'public-auth-notice'} role={status.type === 'error' ? 'alert' : 'status'}>{status.msg}</div>}
            {status.type === 'success' ? <Link to="/login" className="public-auth-secondary">Back to login <ArrowRight size={18} aria-hidden="true" /></Link> : (
              <form onSubmit={handleSubmit} aria-label="Reset password" aria-busy={isSubmitting}>
                <div className="public-auth-fields">
                  <div className="public-auth-field">
                    <label htmlFor="reset-password">New password</label>
                    <input id="reset-password" name="password" type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="new-password" required minLength={8} disabled={isSubmitting} aria-describedby="reset-password-hint" />
                    <p id="reset-password-hint" className="public-auth-hint">At least 8 characters, including an uppercase letter and a digit.</p>
                  </div>
                  <div className="public-auth-field">
                    <label htmlFor="reset-confirmation">Confirm new password (optional)</label>
                    <input id="reset-confirmation" name="confirmation" type="password" value={confirmation} onChange={event => setConfirmation(event.target.value)} autoComplete="new-password" disabled={isSubmitting} />
                  </div>
                </div>
                <button type="submit" className="public-auth-primary" disabled={isSubmitting}>
                  {isSubmitting ? <Loader size={18} className="public-auth-spinner" aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
                  {isSubmitting ? 'Resetting...' : 'Reset password'}
                </button>
              </form>
            )}
            {status.type !== 'success' && <p className="public-auth-switch"><Link to="/forgot-password">Request a new reset link</Link></p>}
          </>
        )}
      </section>
    </PublicSiteLayout>
  );
}