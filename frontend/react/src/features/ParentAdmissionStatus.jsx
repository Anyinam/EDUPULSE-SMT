import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { AlertCircle, ArrowRight, CheckCircle2, Clock3, FileSearch, Wallet } from 'lucide-react';
import usePublicSchoolProfile from '../hooks/usePublicSchoolProfile';

const statusConfig = {
  Submitted: { label: 'Submitted', tone: 'bg-slate-900 text-white', icon: Clock3 },
  ReviewReady: { label: 'Ready for review', tone: 'bg-cyan-600 text-white', icon: FileSearch },
  TestReady: { label: 'Test ready', tone: 'bg-emerald-600 text-white', icon: CheckCircle2 },
  VisitRequired: { label: 'Visit required', tone: 'bg-amber-500 text-white', icon: AlertCircle },
  NeedsCorrection: { label: 'Needs correction', tone: 'bg-rose-600 text-white', icon: AlertCircle },
  Approved: { label: 'Approved', tone: 'bg-emerald-700 text-white', icon: CheckCircle2 },
  Rejected: { label: 'Closed', tone: 'bg-slate-700 text-white', icon: AlertCircle },
};

function formatDate(value) {
  if (!value) return 'N/A';
  return new Date(value).toLocaleString();
}

export default function ParentAdmissionStatus() {
  const { schoolId, statusToken } = useParams();
  const navigate = useNavigate();
  const { schoolProfile } = usePublicSchoolProfile(schoolId);
  const [tokenInput, setTokenInput] = useState(statusToken === 'check' ? '' : statusToken);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resubmitting, setResubmitting] = useState(false);
  const [resubmitMessage, setResubmitMessage] = useState('');
  const [resubmitFiles, setResubmitFiles] = useState([]);
  const [resubmitForm, setResubmitForm] = useState({
    guardian_name: '',
    parent_email: '',
    parent_phone: '',
    preferred_class: '',
    desired_test_mode: 'either',
    internet_quality: 'unknown',
    parent_notes: '',
  });

  const fetchStatus = async (event, overrideToken) => {
    event?.preventDefault();
    const token = (overrideToken || tokenInput).trim();
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`/api/public/schools/${schoolId}/admissions/status/${token}`);
      setPayload(response.data);
      setResubmitForm({
        guardian_name: response.data.school?.guardian_name || response.data.guardian_name || '',
        parent_email: response.data.parent_email || '',
        parent_phone: response.data.parent_phone || '',
        preferred_class: response.data.preferred_class || '',
        desired_test_mode: response.data.desired_test_mode || 'either',
        internet_quality: response.data.internet_quality || 'unknown',
        parent_notes: '',
      });
      navigate(`/apply/${schoolId}/status/${token}`, { replace: true });
    } catch (requestError) {
      setError(requestError.response?.data?.message || 'Unable to load application status.');
      setPayload(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (statusToken && statusToken !== 'check') {
      setTokenInput(statusToken);
      fetchStatus(undefined, statusToken);
    }
  }, [statusToken]);

  const handleResubmitChange = (event) => {
    setResubmitForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const handleResubmit = async (event) => {
    event.preventDefault();
    if (!payload) return;
    setResubmitting(true);
    setResubmitMessage('');
    try {
      const formPayload = new FormData();
      Object.entries(resubmitForm).forEach(([key, value]) => formPayload.append(key, value));
      Array.from(resubmitFiles).forEach((file) => formPayload.append('documents', file));
      const response = await axios.post(
        `/api/public/schools/${schoolId}/admissions/status/${payload.status_path?.split('/').at(-1) || tokenInput}/resubmit`,
        formPayload,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setPayload((current) => ({ ...current, ...response.data.application }));
      setResubmitFiles([]);
      setResubmitForm((current) => ({ ...current, parent_notes: '' }));
      setResubmitMessage('Correction update submitted successfully.');
    } catch (requestError) {
      setResubmitMessage(requestError.response?.data?.message || 'Unable to submit corrections.');
    } finally {
      setResubmitting(false);
    }
  };

  const currentStatus = statusConfig[payload?.status] || statusConfig.Submitted;
  const StatusIcon = currentStatus.icon;
  const schoolName = payload?.school?.school_name || schoolProfile?.school_name || schoolId;
  const schoolColor = payload?.school?.theme_color || schoolProfile?.theme_color || '#0891b2';

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_right,_rgba(14,165,233,0.16),_transparent_24%),linear-gradient(180deg,_#f8fbff_0%,_#ffffff_52%,_#f7fafc_100%)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-5xl space-y-8">
        <section className="rounded-[2rem] border border-slate-200 bg-white px-6 py-8 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.35)] sm:px-8">
          <div className="grid gap-6 lg:grid-cols-[1fr,0.8fr] lg:items-end">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-600">Parent Admissions Status</p>
              <h1 className="mt-3 text-4xl font-black text-slate-950">Track your application for <span style={{ color: schoolColor }}>{schoolName}</span> in one place.</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                Enter the status token you received after submission. If the school has requested corrections, scheduled a visit, or approved admission, it will appear here.
              </p>
            </div>

            <form onSubmit={fetchStatus} className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 sm:p-5">
              <label className="block text-xs font-black uppercase tracking-[0.18em] text-slate-500">Status Token</label>
              <div className="mt-3 flex flex-col gap-3 md:flex-row">
                <input value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} placeholder="Enter your status token" className="flex-1 rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
                <button type="submit" disabled={loading} className="rounded-2xl bg-slate-950 px-6 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:opacity-60">
              {loading ? 'Checking...' : 'Check Status'}
                </button>
              </div>
            </form>
          </div>

          {error && <p className="mt-3 text-sm font-semibold text-red-600">{error}</p>}
        </section>

        {payload && (
          <div className="space-y-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-[0_24px_70px_-40px_rgba(15,23,42,0.35)] sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.24em] text-slate-500">Application</p>
                <h2 className="mt-2 text-3xl font-black text-slate-900">{payload.application_code}</h2>
                <p className="mt-1 text-sm text-slate-500">{payload.student_name} • {payload.preferred_class}</p>
              </div>
              <div className={`rounded-3xl px-4 py-3 ${currentStatus.tone}`}>
                <p className="text-xs font-bold uppercase text-slate-300">Status</p>
                <div className="mt-1 flex items-center gap-2 text-xl font-black">
                  <StatusIcon size={18} />
                  <span>{currentStatus.label}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">AI Recommendation</p>
                <p className="mt-2 text-lg font-black text-slate-900">{payload.ai_recommendation}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">Readiness Score</p>
                <p className="mt-2 text-lg font-black text-slate-900">{payload.ai_readiness_score}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">Submitted</p>
                <p className="mt-2 text-lg font-black text-slate-900">{formatDate(payload.submitted_at)}</p>
              </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-[1fr,0.85fr]">
              <div className="rounded-[1.75rem] border border-cyan-100 bg-cyan-50 p-5">
              <p className="text-xs font-bold uppercase text-cyan-600">AI Registrar Summary</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">{payload.ai_summary}</p>
                {(payload.ai_missing_items || []).length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                  {payload.ai_missing_items.map((item) => (
                      <span key={item} className="rounded-full bg-white px-3 py-2 text-xs font-bold uppercase tracking-wide text-cyan-700 shadow-sm ring-1 ring-cyan-100">Missing: {item.replaceAll('_', ' ')}</span>
                  ))}
                  </div>
                )}
              </div>

              <div className="rounded-[1.75rem] border border-slate-200 bg-slate-950 p-5 text-slate-100">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-300">What Happens Next</p>
                <div className="mt-4 space-y-3">
                  {[
                    'If corrections are needed, update the school with the missing items listed here.',
                    'If the school approves the learner, a payment link will appear below.',
                    'If a visit or test is required, follow the school notes and contact instructions.',
                  ].map((step) => (
                    <div key={step} className="flex gap-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="mt-0.5 h-2.5 w-2.5 rounded-full bg-cyan-300" />
                      <p className="text-sm leading-6 text-slate-200">{step}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {payload.reviewer_notes && (
              <div className="rounded-[1.75rem] border border-amber-200 bg-amber-50 p-5">
                <p className="text-xs font-bold uppercase text-amber-700">School Review Notes</p>
                <p className="mt-3 text-sm leading-7 text-slate-700">{payload.reviewer_notes}</p>
              </div>
            )}

            {payload.status === 'NeedsCorrection' && (
              <form onSubmit={handleResubmit} className="rounded-[1.75rem] border border-rose-200 bg-rose-50 p-5">
                <p className="text-xs font-bold uppercase text-rose-700">Submit Missing Corrections</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">Upload the missing documents or update guardian contact details here. The application will be re-evaluated automatically.</p>

                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <input name="guardian_name" value={resubmitForm.guardian_name} onChange={handleResubmitChange} placeholder="Guardian name" className="rounded-2xl border border-rose-200 bg-white px-4 py-3" />
                  <input name="parent_email" value={resubmitForm.parent_email} onChange={handleResubmitChange} placeholder="Parent email" className="rounded-2xl border border-rose-200 bg-white px-4 py-3" />
                  <input name="parent_phone" value={resubmitForm.parent_phone} onChange={handleResubmitChange} placeholder="Parent phone" className="rounded-2xl border border-rose-200 bg-white px-4 py-3" />
                  <input name="preferred_class" value={resubmitForm.preferred_class} onChange={handleResubmitChange} placeholder="Preferred class" className="rounded-2xl border border-rose-200 bg-white px-4 py-3" />
                  <select name="desired_test_mode" value={resubmitForm.desired_test_mode} onChange={handleResubmitChange} className="rounded-2xl border border-rose-200 bg-white px-4 py-3">
                    <option value="either">Either Remote or In-Person</option>
                    <option value="online">Online Test</option>
                    <option value="in_person">Visit School</option>
                  </select>
                  <select name="internet_quality" value={resubmitForm.internet_quality} onChange={handleResubmitChange} className="rounded-2xl border border-rose-200 bg-white px-4 py-3">
                    <option value="unknown">Prefer not to say</option>
                    <option value="stable">Stable</option>
                    <option value="limited">Limited</option>
                  </select>
                  <div className="md:col-span-2">
                    <textarea name="parent_notes" value={resubmitForm.parent_notes} onChange={handleResubmitChange} rows={4} placeholder="What have you added or corrected?" className="w-full rounded-2xl border border-rose-200 bg-white px-4 py-3" />
                  </div>
                  <div className="md:col-span-2 rounded-2xl border border-dashed border-rose-200 bg-white p-4">
                    <input type="file" multiple onChange={(event) => setResubmitFiles(event.target.files || [])} className="w-full text-sm file:mr-4 file:rounded-full file:border-0 file:bg-rose-600 file:px-4 file:py-2 file:font-bold file:text-white" />
                    {resubmitFiles.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {Array.from(resubmitFiles).map((file) => (
                          <span key={`${file.name}-${file.size}`} className="rounded-full bg-rose-100 px-3 py-2 text-xs font-semibold text-rose-800">{file.name}</span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>

                {resubmitMessage ? <p className="mt-4 text-sm font-semibold text-rose-700">{resubmitMessage}</p> : null}

                <div className="mt-4">
                  <button type="submit" disabled={resubmitting} className="rounded-2xl bg-rose-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-rose-700 disabled:opacity-60">
                    {resubmitting ? 'Submitting update...' : 'Submit correction update'}
                  </button>
                </div>
              </form>
            )}

            <div className="flex flex-wrap gap-3">
              {payload.payment_path && (
                <Link to={payload.payment_path} className="inline-flex items-center gap-2 rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-emerald-700">
                  <Wallet size={16} />
                  View Payment Options
                </Link>
              )}
              <Link to={`/apply/${schoolId}`} className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 px-5 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50">
                Back to Admissions Page
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}