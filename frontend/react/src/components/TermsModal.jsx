import React from 'react';

export default function TermsModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-6 border-b border-slate-100 flex justify-between items-center">
          <h3 className="text-xl font-bold text-slate-800">Terms of Service</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-xl">×</button>
        </div>
        
        <div className="p-6 overflow-y-auto text-slate-600 text-sm leading-relaxed space-y-4">
          <p><strong>1. Acceptance of Terms</strong><br/>By registering for EduPulse SMT, you agree to comply with and be bound by these Terms of Service.</p>
          <p><strong>2. Policy Bundle Acceptance</strong><br/>Registration also confirms acceptance of the Privacy Policy and Data Retention Policy that govern how school, staff, student, and guardian data is handled.</p>
          <p><strong>3. Data Privacy</strong><br/>We respect student privacy. Data is protected with access controls and secure transmission. EduPulse SMT processes data solely for providing governance insights.</p>
          <p><strong>4. Subscription & Payments</strong><br/>Free Tier accounts are limited to 100 students. Premium features require an active subscription. Failure to renew may result in restricted access.</p>
          <p><strong>5. User Responsibilities</strong><br/>You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account.</p>
          <p><strong>6. Termination</strong><br/>We reserve the right to terminate or suspend access to our service immediately, without prior notice or liability, for any reason whatsoever, including without limitation if you breach the Terms.</p>
        </div>

        <div className="p-6 border-t border-slate-100 bg-slate-50 rounded-b-2xl flex justify-end">
          <button onClick={onClose} className="bg-slate-800 text-white px-6 py-2 rounded-xl font-bold hover:bg-slate-700">
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}