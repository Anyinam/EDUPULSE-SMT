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
          <p><strong>1. School-Controlled Data</strong><br/>For most student, guardian, academic, attendance, and admissions records, the school is the primary data controller and EduPulse acts as its processor or service provider.</p>
          <p><strong>2. Educational Use Only</strong><br/>EduPulse processes school data only for legitimate educational, administrative, billing, communication, admissions, and academic-analytics purposes authorised by the school.</p>
          <p><strong>3. Examination Records</strong><br/>If a school uploads WAEC or BECE result lists, those records must be used only for lawful school operations such as placement, trend analysis, and student support.</p>
          <p><strong>4. Access Controls</strong><br/>Access is restricted by role and organisation. Each school can access only its own records.</p>
          <p><strong>5. Your Rights</strong><br/>Parents, guardians, staff, and schools can request access, correction, or deletion of data as permitted by Ghana law and school obligations.</p>
          <p><strong>6. Contact</strong><br/>For privacy questions, contact danielasareanyinam2020@gmail.com.</p>
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
