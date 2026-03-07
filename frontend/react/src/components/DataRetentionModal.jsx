import React from 'react';

export default function DataRetentionModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-6 border-b border-slate-100 flex justify-between items-center">
          <h3 className="text-xl font-bold text-slate-800">Data Retention Policy</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-xl">×</button>
        </div>

        <div className="p-6 overflow-y-auto text-slate-600 text-sm leading-relaxed space-y-4">
          <p><strong>1. Retention Periods</strong><br/>EduPulse retains data based on school operations and legal obligations (for example: student academic records, audit logs, and billing records).</p>
          <p><strong>2. Deletion and Anonymization</strong><br/>When retention periods expire, data is securely deleted or irreversibly anonymized where required.</p>
          <p><strong>3. Legal Holds</strong><br/>Data may be retained longer where required by law, investigations, or legal proceedings.</p>
          <p><strong>4. Data Subject Requests</strong><br/>Schools and authorized requestors may request access, correction, export, or deletion subject to legal constraints.</p>
          <p><strong>5. Acceptance</strong><br/>By registering, your school confirms it has reviewed and accepts this Data Retention Policy as part of onboarding.</p>
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
