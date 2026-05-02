import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import PremiumFeatureNotice from './PremiumFeatureNotice';

export default function AcademicGuidancePanel({ title = 'Academic Guidance Intelligence' }) {
  const currentPlan = localStorage.getItem('subscription_plan') || 'Free Tier';
  const canAccessAcademicGuidance = currentPlan === 'Premium';
  const [guidance, setGuidance] = useState(null);
  const [library, setLibrary] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  }), []);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const [guidanceRes, libraryRes] = await Promise.all([
        axios.get('/api/analytics/academic-guidance', { headers }),
        axios.get('/api/analytics/chief-examiner-library', { headers }),
      ]);
      setGuidance(guidanceRes.data || null);
      setLibrary(libraryRes.data || null);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load academic guidance.');
      setGuidance(null);
      setLibrary(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!canAccessAcademicGuidance) {
      setLoading(false);
      return;
    }
    fetchData();
  }, [headers, canAccessAcademicGuidance]);

  if (!canAccessAcademicGuidance) {
    return (
      <PremiumFeatureNotice
        title={title}
        description="Diagnostic hotspots, chief examiner insight libraries, and pathway guidance are available on the Premium plan only."
      />
    );
  }

  if (loading) {
    return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Loading academic guidance...</div>;
  }

  if (error) {
    return <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">{error}</div>;
  }

  if (!guidance) {
    return null;
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-cyan-700">Academic Guidance</p>
          <h3 className="mt-2 text-2xl font-black text-slate-900">{title}</h3>
          <p className="mt-2 text-sm text-slate-600">{guidance.scope?.academic_term || 'Latest term'} {guidance.scope?.academic_year || ''} guidance for {guidance.scope?.role_label || 'school staff'}.</p>
        </div>
        <div className="rounded-2xl bg-cyan-50 px-4 py-3 text-sm font-bold text-cyan-900">
          {guidance.summary?.reports_analyzed || 0} reports analyzed
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl bg-slate-900 p-4 text-white">
          <p className="text-xs uppercase tracking-wide text-slate-300">Tracked Subjects</p>
          <p className="mt-2 text-3xl font-black">{guidance.summary?.tracked_subjects || 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">Classes In Scope</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{guidance.summary?.classes_in_scope || 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-xs uppercase tracking-wide text-slate-500">Role Scope</p>
          <p className="mt-2 text-sm font-bold text-slate-900">
            {(guidance.scope?.allowed_subjects || []).join(', ') || (guidance.scope?.allowed_classes || []).join(', ') || 'Whole school overview'}
          </p>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200 p-4">
          <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Diagnostic Hotspots</h4>
          <div className="mt-4 space-y-3">
            {(guidance.diagnostic_hotspots || []).length === 0 ? (
              <p className="text-sm text-slate-500">No diagnostic hotspots have been recorded yet for the current scope.</p>
            ) : (
              guidance.diagnostic_hotspots.map((item) => (
                <div key={`${item.subject}-${item.topic}`} className="rounded-lg bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-bold text-slate-800">{item.subject} - {item.topic}</p>
                    <span className="text-xs font-bold text-red-600">{item.low_report_count} low reports</span>
                  </div>
                  {item.chief_examiner_issue && <p className="mt-2 text-xs text-slate-600">Issue: {item.chief_examiner_issue}</p>}
                  {item.advice && <p className="mt-2 text-xs text-cyan-900">Action: {item.advice}</p>}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 p-4">
          <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Pathway Signals</h4>
          <div className="mt-4 space-y-3">
            {(guidance.pathway_distribution || []).length === 0 ? (
              <p className="text-sm text-slate-500">Pathway signals will appear after enough reports include subject scores.</p>
            ) : (
              guidance.pathway_distribution.map((item) => (
                <div key={item.pathway} className="rounded-lg bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-bold text-slate-800">{item.pathway}</p>
                    <span className="text-xs font-bold text-slate-500">{item.student_count} learners</span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600">Average fit score {Number(item.average_fit_score || 0).toFixed(1)}%</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 p-4">
        <div>
          <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Examiner Insight Library</h4>
        </div>

        <div className="mt-4 space-y-3">
          {(library?.subjects || []).length === 0 ? (
            <p className="text-sm text-slate-500">No subject library is available for your current scope.</p>
          ) : (
            library.subjects.map((subject) => (
              <details key={subject.subject} className="rounded-lg bg-slate-50 p-4">
                <summary className="cursor-pointer text-sm font-bold text-slate-800">{subject.subject}</summary>
                <div className="mt-3 space-y-3">
                  {subject.topics.map((topic) => (
                    <div key={`${subject.subject}-${topic.topic}`} className="rounded-lg border border-slate-200 bg-white p-3">
                      <p className="text-sm font-bold text-slate-800">{topic.topic}</p>
                      <p className="mt-1 text-xs text-slate-600">Issue: {topic.issue}</p>
                      <p className="mt-1 text-xs text-cyan-900">Advice: {topic.advice}</p>
                      {(topic.practice || []).length > 0 && (
                        <p className="mt-1 text-xs text-slate-500">Practice: {topic.practice.join(', ')}</p>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            ))
          )}
        </div>

      </div>
    </section>
  );
}