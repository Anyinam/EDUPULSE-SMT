import React from 'react';

export default function PrivacyModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="p-6 border-b border-slate-100 flex justify-between items-center">
          <h3 className="text-xl font-bold text-slate-800">Privacy Policy</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 font-bold text-xl">×</button>
        </div>

        <div className="p-6 overflow-y-auto text-slate-600 text-sm leading-relaxed space-y-4">
          <p><strong>1. Data Use</strong><br/>EduPulse processes student and staff data only to provide the service to your school.</p>
          <p><strong>2. Access Controls</strong><br/>Access is restricted by role and organization. Each school sees only its own data.</p>
          <p><strong>3. Data Retention</strong><br/>We retain data as needed to provide the service and meet legal obligations.</p>
          <p><strong>4. Your Rights</strong><br/>You can request access, corrections, or deletion as permitted by law.</p>
          <p><strong>5. Contact</strong><br/>For privacy questions, contact privacy@edupulse.com.gh.</p>
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
