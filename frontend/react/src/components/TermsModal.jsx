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
          <p><strong>3. School Responsibility</strong><br/>Schools must ensure they have lawful authority to upload student, guardian, admissions, legacy-record, and examination data into the platform, and must send any required parent or guardian consent form before student biodata is first uploaded into EduPulse SMT.</p>
          <p><strong>4. Data Privacy</strong><br/>We protect school data with access controls and secure transmission. EduPulse SMT must not be used for unauthorised disclosure of student records.</p>
          <p><strong>5. Subscription & Payments</strong><br/>Plan access, billing, and feature availability are governed by the school's selected subscription and payment status.</p>
          <p><strong>6. User Responsibilities</strong><br/>You are responsible for keeping credentials secure and for ensuring the data you upload is accurate, lawful, and school-authorised.</p>
          <p><strong>7. Termination</strong><br/>We may suspend or terminate access where these terms are breached or where continued access would create legal, security, or operational risk.</p>
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