import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, Menu, X } from 'lucide-react';
import { Logo } from './Logo';
import TermsModal from './TermsModal';
import PrivacyModal from './PrivacyModal';
import DataRetentionModal from './DataRetentionModal';
import '../styles/public-site.css';

export default function PublicSiteLayout({ children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [policy, setPolicy] = useState(null);
  const menuButton = useRef(null);
  const policyTrigger = useRef(null);
  const policyDialog = useRef(null);
  const { pathname } = useLocation();
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && menuOpen) {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [menuOpen]);
  useEffect(() => {
    if (!policy) return;
    const focusable = () => [...policyDialog.current.querySelectorAll('button, a[href], input, [tabindex="0"]')];
    focusable()[0]?.focus();
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        setPolicy(null);
        policyTrigger.current?.focus();
      } else if (event.key === 'Tab') {
        const controls = focusable();
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [policy]);
  const closePolicy = () => { setPolicy(null); policyTrigger.current?.focus(); };
  useEffect(() => {
    const titles = { '/': 'EduPulse SMT | Connected school management', '/pricing': 'Pricing | EduPulse SMT', '/pricing-comparison': 'Pricing | EduPulse SMT', '/login': 'Log in | EduPulse SMT', '/register': 'Create your account | EduPulse SMT', '/forgot-password': 'Recover your account | EduPulse SMT', '/reset-password': 'Reset your password | EduPulse SMT' };
    const previousTitle = document.title;
    document.title = titles[pathname] || 'EduPulse SMT';
    return () => { document.title = previousTitle; };
  }, [pathname]);
  return (
    <div className="public-site">
      <a className="public-skip" href="#public-content">Skip to content</a>
      <header className="public-header">
        <div className="public-container public-navigation">
          <Link to="/" className="public-brand" aria-label="EduPulse SMT home"><Logo size="md" /><span>EduPulse <strong>SMT</strong></span></Link>
          <button ref={menuButton} className="public-menu-toggle" type="button" aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen} aria-controls="public-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={24} /> : <Menu size={24} />}</button>
          <nav id="public-navigation" aria-label="Main navigation" className={`public-links ${menuOpen ? 'is-open' : ''}`} onClick={() => setMenuOpen(false)}>
            <a href="/#why-edupulse">Why EduPulse SMT</a>
            <a href="/#school-operations">Our platform</a>
            <Link to="/pricing">Pricing</Link>
            <Link to="/login" className="public-login">Log in</Link>
            <Link to="/register" className="public-button public-button-small">Create free account <ArrowRight size={16} /></Link>
          </nav>
        </div>
      </header>
      <main id="public-content">{children}</main>
      <footer className="public-footer">
        <div className="public-container public-footer-grid">
          <div><Link to="/" className="public-brand"><Logo size="md" /><span>EduPulse <strong>SMT</strong></span></Link><p>Thoughtful technology. <br />Better school operations.</p></div>
          <div><h3>Explore</h3><a href="/#why-edupulse">Why EduPulse SMT</a><a href="/#school-operations">School operations</a><Link to="/pricing">Pricing</Link></div>
          <div><h3>Your school</h3><Link to="/register">Create free account</Link><Link to="/login">Log in</Link><a href="mailto:info@edupulsesmt.com">Contact support</a></div>
          <div><h3>Let's talk</h3><a href="mailto:info@edupulsesmt.com">info@edupulsesmt.com</a><a href="tel:+233552141384">+233 552 141 384</a><p>Built for schools in Ghana and beyond.</p></div>
        </div>
        <div className="public-container public-footer-policies" aria-label="Legal policies">{['Terms of Service', 'Privacy Policy', 'Data Retention Policy'].map(label => <button key={label} type="button" onClick={event => { policyTrigger.current = event.currentTarget; setPolicy(label); }}>{label}</button>)}</div>
        <div className="public-container public-footer-bottom"><span>EduPulse SMT</span><span>School management, with clarity.</span></div>
      </footer>
      {policy && <div ref={policyDialog} className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={policy}>
        <TermsModal isOpen={policy === 'Terms of Service'} onClose={closePolicy} />
        <PrivacyModal isOpen={policy === 'Privacy Policy'} onClose={closePolicy} />
        <DataRetentionModal isOpen={policy === 'Data Retention Policy'} onClose={closePolicy} />
      </div>}
    </div>
  );
}