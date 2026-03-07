import React from 'react';

export default function StudentProfile({ student }) {
  if (!student) return null;

  return (
    <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 max-w-md mx-auto transition-all transform hover:scale-[1.02]">
      <div className="text-center mb-6">
        <div className="w-24 h-24 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4 border-4 border-white shadow-sm">
          <span className="text-4xl">🎓</span>
        </div>
        <h2 className="text-2xl font-black text-slate-800">{student.name}</h2>
        <span className="inline-block bg-slate-100 text-slate-500 text-xs font-mono px-2 py-1 rounded mt-2">
          {student.student_code}
        </span>
      </div>

      <div className="space-y-3">
        <ProfileRow label="Class Assigned" value={student.class_assigned} />
        <ProfileRow label="Guardian Name" value={student.guardian_name} />
        <ProfileRow label="Parent Email" value={student.parent_email} />
        
        <div className="flex justify-between items-center p-3 bg-slate-50 rounded-xl mt-4">
          <span className="text-slate-400 text-xs font-bold uppercase">Entrance Score</span>
          <span className={`text-lg font-black ${
            student.score >= 75 ? 'text-green-600' : 
            student.score >= 50 ? 'text-blue-600' : 'text-orange-500'
          }`}>
            {student.score}%
          </span>
        </div>
      </div>
    </div>
  );
}

function ProfileRow({ label, value }) {
  return (
    <div className="flex justify-between items-center border-b border-slate-50 pb-2 last:border-0">
      <span className="text-slate-400 text-xs font-bold uppercase">{label}</span>
      <span className="font-bold text-slate-700 text-sm">{value || 'N/A'}</span>
    </div>
  );
}