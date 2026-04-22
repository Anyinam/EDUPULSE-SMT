import React from 'react';
import StudentRescueAgent from '../components/StudentRescueAgent';

export default function RescueActivityCenter({ endpointBase = '/api/proprietor/student-rescue-agent' }) {
  return (
    <div className="space-y-6">
      <div className="rounded-3xl bg-linear-to-r from-slate-950 via-red-900 to-orange-700 px-8 py-8 text-white shadow-xl">
        <p className="text-xs font-black uppercase tracking-[0.24em] text-red-100">Intervention Operations</p>
        <h1 className="mt-3 text-4xl font-black">Rescue Activity Center</h1>
        <p className="mt-3 max-w-3xl text-sm text-red-50">
          Review open rescue cases, monitor intervention progress, send guardian emails, and track resolved cases from one place.
        </p>
        <div className="mt-5 flex flex-wrap gap-3 text-xs font-bold text-red-100">
          <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">Open vs Resolved Tracking</span>
          <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">Editable Guardian Emails</span>
          <span className="rounded-full border border-white/20 bg-white/10 px-3 py-1">WhatsApp Deferred For Cost Control</span>
        </div>
      </div>

      <StudentRescueAgent endpointBase={endpointBase} />
    </div>
  );
}