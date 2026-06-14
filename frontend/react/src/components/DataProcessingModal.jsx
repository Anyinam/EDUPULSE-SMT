import React from 'react';

export default function DataProcessingModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-100 p-6">
          <h3 className="text-xl font-bold text-slate-800">Data Processing Agreement</h3>
          <button onClick={onClose} className="text-xl font-bold text-slate-400 hover:text-slate-600">×</button>
        </div>

        <div className="space-y-4 overflow-y-auto p-6 text-sm leading-relaxed text-slate-600">
          <p><strong>1. Controller and Processor Roles</strong><br/>For school-originated student, guardian, staff, admissions, academic, and examination records, the school acts as the Data Controller and EduPulse SMT acts as the Data Processor on the school's documented instructions.</p>
          <p><strong>2. Authorization for De-Identification</strong><br/>The school authorizes EduPulse SMT to de-identify and permanently anonymize lawfully supplied academic performance records, including mock exam scores, BECE results, and related institutional metadata, where this is covered by the onboarding notice and applicable law.</p>
          <p><strong>3. Irreversible Anonymization</strong><br/>Before approved data enters EduPulse SMT's shared analytics layer, direct identifiers such as student names, student IDs, contact details, and direct school names are intended to be removed or generalized so the resulting dataset is not reasonably traceable to an individual student or specific institution.</p>
          <p><strong>4. Permitted Aggregated Uses</strong><br/>Irreversibly anonymized data may be used for regional and national benchmarking, curriculum-gap analysis, research-style reporting, educational white papers, and system optimization. Shared outputs should remain aggregated and should not identify a student or named school unless separately authorized on a lawful basis.</p>
          <p><strong>5. Ownership Position</strong><br/>The school retains ownership of its raw, identifiable operational records. Subject to applicable law and contract, EduPulse SMT retains rights in the resulting anonymized aggregate datasets, benchmark models, visual metrics, and related analytics outputs generated from de-identified platform data.</p>
        </div>

        <div className="flex justify-end rounded-b-2xl border-t border-slate-100 bg-slate-50 p-6">
          <button onClick={onClose} className="rounded-xl bg-slate-800 px-6 py-2 font-bold text-white hover:bg-slate-700">
            I Understand
          </button>
        </div>
      </div>
    </div>
  );
}
