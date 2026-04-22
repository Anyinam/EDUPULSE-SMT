import React, { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowRight, CheckCircle2, FileText, ShieldCheck, Sparkles, UploadCloud } from 'lucide-react';
import usePublicSchoolProfile from '../hooks/usePublicSchoolProfile';

const validGrades = [
  'Nursery', 'KG', 'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6', 'JHS 1', 'JHS 2', 'JHS 3'
];

const intakeHighlights = [
  {
    title: 'Fast school review',
    description: 'The AI Registrar organizes documents and flags missing details before staff review begins.',
    icon: Sparkles,
  },
  {
    title: 'Flexible test path',
    description: 'Families can indicate whether online testing or an in-person visit works best.',
    icon: ShieldCheck,
  },
  {
    title: 'One tracking link',
    description: 'After submission, parents receive a status token they can use to track progress anytime.',
    icon: FileText,
  },
];

function FieldLabel({ children, helper }) {
  return (
    <div>
      <label className="block text-sm font-semibold tracking-wide text-slate-800">{children}</label>
      {helper ? <p className="mt-1 text-xs text-slate-500">{helper}</p> : null}
    </div>
  );
}

export default function ParentAdmissionsPortal() {
  const { schoolId } = useParams();
  const { schoolProfile } = usePublicSchoolProfile(schoolId);
  const [formData, setFormData] = useState({
    first_name: '',
    surname: '',
    gender: 'Male',
    date_of_birth: '',
    preferred_class: 'JHS 1',
    guardian_name: '',
    parent_email: '',
    parent_phone: '',
    prior_school: '',
    desired_test_mode: 'either',
    internet_quality: 'unknown',
    parent_notes: ''
  });
  const [documents, setDocuments] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const statusPath = useMemo(() => result?.status_path || '', [result]);
  const schoolName = schoolProfile?.school_name || schoolId;
  const schoolColor = schoolProfile?.theme_color || '#0f766e';

  const handleChange = (event) => {
    setFormData((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const payload = new FormData();
      Object.entries(formData).forEach(([key, value]) => payload.append(key, value));
      Array.from(documents).forEach((file) => payload.append('documents', file));

      const response = await axios.post(`/api/public/schools/${schoolId}/admissions/apply`, payload, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(response.data);
    } catch (requestError) {
      setError(requestError.response?.data?.message || 'Failed to submit application.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(8,145,178,0.18),_transparent_28%),linear-gradient(180deg,_#f8fbff_0%,_#ffffff_50%,_#f4fbf8_100%)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="relative overflow-hidden rounded-[2rem] border border-slate-200/80 bg-white/85 shadow-[0_30px_80px_-40px_rgba(15,23,42,0.45)] backdrop-blur">
          <div className="absolute inset-y-0 right-0 hidden w-2/5 bg-[linear-gradient(180deg,rgba(14,165,233,0.08),rgba(16,185,129,0.12))] lg:block" />
          <div className="relative grid gap-8 px-6 py-8 sm:px-10 sm:py-10 lg:grid-cols-[1.2fr,0.8fr]">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-700">EduPulse Parent Admissions</p>
              <h1 className="mt-4 max-w-3xl text-4xl font-black leading-tight text-slate-950 sm:text-5xl">
                Start admission for <span style={{ color: schoolColor }}>{schoolName}</span> without waiting at the front desk.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
                Submit the learner profile, upload any available records, and let the AI Registrar prepare the case for school review, correction, or testing.
              </p>

              <div className="mt-8 grid gap-4 md:grid-cols-3">
                {intakeHighlights.map(({ title, description, icon: Icon }) => (
                  <div key={title} className="rounded-3xl border border-slate-200 bg-slate-50/80 p-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-950 text-white">
                      <Icon size={18} />
                    </div>
                    <h2 className="mt-4 text-sm font-black uppercase tracking-[0.14em] text-slate-900">{title}</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
                  </div>
                ))}
              </div>
            </div>

            <aside className="rounded-[1.75rem] border border-slate-200 bg-slate-950 p-6 text-slate-100 shadow-xl shadow-slate-900/15">
              <div className="mb-5 flex items-center gap-4">
                {schoolProfile?.logo_url ? (
                  <img src={schoolProfile.logo_url} alt={`${schoolName} logo`} className="h-16 w-16 rounded-2xl object-cover ring-1 ring-white/10" />
                ) : (
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 text-lg font-black text-white">{schoolName.slice(0, 2).toUpperCase()}</div>
                )}
                <div>
                  <p className="text-lg font-black text-white">{schoolName}</p>
                  {schoolProfile?.motto ? <p className="text-sm text-slate-300">{schoolProfile.motto}</p> : null}
                </div>
              </div>
              <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-300">Before You Submit</p>
              <div className="mt-5 space-y-4">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm font-semibold text-white">Required for a clean first review</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">Learner name, class preference, guardian contact, and at least one parent email or phone number.</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="text-sm font-semibold text-white">Helpful supporting files</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">Previous report card, birth certificate, and any identity record you already have ready.</p>
                </div>
                {schoolProfile?.admission_fee?.enabled ? (
                  <div className="rounded-2xl border border-emerald-400/30 bg-emerald-400/10 p-4">
                    <p className="text-sm font-semibold text-white">Admission fee applies</p>
                    <p className="mt-2 text-sm leading-6 text-slate-200">This school currently charges {schoolProfile.admission_fee.currency} {Number(schoolProfile.admission_fee.amount || 0).toFixed(2)} as an admission fee after approval.</p>
                  </div>
                ) : null}
                <div className="rounded-2xl border border-cyan-400/30 bg-cyan-400/10 p-4 text-cyan-50">
                  <p className="text-sm font-semibold">Need to check an existing application?</p>
                  <Link to={`/apply/${schoolId}/status/check`} className="mt-3 inline-flex items-center gap-2 text-sm font-bold text-cyan-200 transition hover:text-white">
                    Open status tracker
                    <ArrowRight size={16} />
                  </Link>
                </div>
              </div>
            </aside>
          </div>
        </section>

        {result ? (
          <div className="rounded-[2rem] border border-emerald-200 bg-white p-8 shadow-[0_20px_60px_-35px_rgba(16,185,129,0.45)]">
            <div className="flex flex-wrap items-start justify-between gap-5">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-emerald-700">
                  <CheckCircle2 size={14} />
                  Application Submitted
                </div>
                <h2 className="mt-4 text-3xl font-black text-slate-900 sm:text-4xl">{result.application?.application_code}</h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{result.application?.ai_summary}</p>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">Status Token</p>
                <p className="mt-2 break-all text-sm font-semibold text-slate-900">{result.status_token}</p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">Status</p>
                <p className="mt-2 text-xl font-black text-slate-900">{result.application?.status}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">AI Recommendation</p>
                <p className="mt-2 text-xl font-black text-slate-900">{result.application?.ai_recommendation}</p>
              </div>
              <div className="rounded-3xl bg-slate-50 p-4">
                <p className="text-xs font-bold uppercase text-slate-500">Readiness Score</p>
                <p className="mt-2 text-xl font-black text-slate-900">{result.application?.ai_readiness_score}</p>
              </div>
            </div>

            {(result.application?.ai_missing_items || []).length > 0 ? (
              <div className="mt-6 rounded-3xl border border-amber-200 bg-amber-50 p-5">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-amber-700">Still Missing</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {result.application.ai_missing_items.map((item) => (
                    <span key={item} className="rounded-full bg-white px-3 py-2 text-xs font-bold uppercase tracking-wide text-amber-800">
                      {item.replaceAll('_', ' ')}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="mt-6 flex flex-wrap gap-3">
              <Link to={statusPath} className="inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800">
                Track Application Status
                <ArrowRight size={16} />
              </Link>
              <button
                onClick={() => {
                  setResult(null);
                  setDocuments([]);
                }}
                className="rounded-2xl border border-slate-300 px-5 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
              >
                Submit Another Application
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-[0_24px_70px_-45px_rgba(15,23,42,0.35)] sm:p-8">
            <div className="grid gap-8 lg:grid-cols-[0.9fr,1.1fr]">
              <div className="space-y-6 rounded-[1.75rem] bg-slate-950 p-6 text-slate-100">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.24em] text-cyan-300">Parent Guide</p>
                  <h2 className="mt-3 text-3xl font-black leading-tight text-white">A complete application gets reviewed faster.</h2>
                  <p className="mt-3 text-sm leading-7 text-slate-300">
                    Share the learner details clearly, then upload any records you already have. If the school needs corrections, the status page will reflect that.
                  </p>
                </div>

                <div className="space-y-3">
                  {[
                    'Use a guardian email or phone number that the school can reach quickly.',
                    'Attach a previous report card if available so the AI Registrar can pre-read academic history.',
                    'Choose online testing only if the learner has stable internet access.',
                  ].map((tip) => (
                    <div key={tip} className="flex gap-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-400/15 text-cyan-200">
                        <CheckCircle2 size={16} />
                      </div>
                      <p className="text-sm leading-6 text-slate-200">{tip}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded-3xl border border-dashed border-cyan-400/30 bg-cyan-400/10 p-5">
                  <div className="flex items-center gap-3 text-cyan-100">
                    <UploadCloud size={18} />
                    <p className="text-sm font-bold uppercase tracking-[0.16em]">Document Upload</p>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-cyan-50/90">
                    Photos from a phone are fine for report cards and identity documents. The system will attempt OCR on previous reports when possible.
                  </p>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-500">Application Form</p>
                  <h2 className="mt-2 text-3xl font-black text-slate-950">Learner and guardian details</h2>
                </div>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <FieldLabel>First Name</FieldLabel>
                <input name="first_name" value={formData.first_name} onChange={handleChange} required className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div>
                <FieldLabel>Surname</FieldLabel>
                <input name="surname" value={formData.surname} onChange={handleChange} required className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div>
                <FieldLabel helper="Choose the class you want the learner assessed for.">Preferred Class</FieldLabel>
                <select name="preferred_class" value={formData.preferred_class} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100">
                  {validGrades.map((grade) => <option key={grade} value={grade}>{grade}</option>)}
                </select>
              </div>
              <div>
                <FieldLabel>Gender</FieldLabel>
                <select name="gender" value={formData.gender} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100">
                  {['Male', 'Female', 'Other'].map((gender) => <option key={gender} value={gender}>{gender}</option>)}
                </select>
              </div>
              <div>
                <FieldLabel>Date of Birth</FieldLabel>
                <input name="date_of_birth" type="date" value={formData.date_of_birth} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div>
                <FieldLabel helper="The primary adult the school should contact first.">Guardian Name</FieldLabel>
                <input name="guardian_name" value={formData.guardian_name} onChange={handleChange} required className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div>
                <FieldLabel>Parent Email</FieldLabel>
                <input name="parent_email" type="email" value={formData.parent_email} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div>
                <FieldLabel>Parent Phone</FieldLabel>
                <input name="parent_phone" value={formData.parent_phone} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div>
                <FieldLabel>Preferred Test Mode</FieldLabel>
                <select name="desired_test_mode" value={formData.desired_test_mode} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100">
                  <option value="either">Either Remote or In-Person</option>
                  <option value="online">Online Test</option>
                  <option value="in_person">Visit School</option>
                </select>
              </div>
              <div>
                <FieldLabel helper="This helps the school decide whether remote assessment is realistic.">Internet Quality</FieldLabel>
                <select name="internet_quality" value={formData.internet_quality} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100">
                  <option value="unknown">Prefer not to say</option>
                  <option value="stable">Stable</option>
                  <option value="limited">Limited</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <FieldLabel>Previous School</FieldLabel>
                <input name="prior_school" value={formData.prior_school} onChange={handleChange} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
              <div className="md:col-span-2">
                <FieldLabel helper="Birth certificate, previous report, or guardian ID if available.">Supporting Documents</FieldLabel>
                <div className="mt-2 rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 p-4">
                  <input type="file" multiple onChange={(event) => setDocuments(event.target.files || [])} className="w-full text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-sm file:font-bold file:text-white hover:file:bg-slate-800" />
                  <p className="mt-3 text-xs text-slate-500">The AI Registrar will flag anything still missing. Previous report uploads may be OCR-scanned automatically.</p>
                  {documents.length > 0 ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {Array.from(documents).map((file) => (
                        <span key={`${file.name}-${file.size}`} className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200">
                          {file.name}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="md:col-span-2">
                <FieldLabel helper="Share any special context the school should know before review.">Notes</FieldLabel>
                <textarea name="parent_notes" value={formData.parent_notes} onChange={handleChange} rows={5} className="mt-2 w-full rounded-2xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100" />
              </div>
                </div>

                {error && <p className="text-sm font-semibold text-red-600">{error}</p>}

                <div className="flex flex-wrap gap-3 pt-2">
                  <button type="submit" disabled={submitting} className="inline-flex items-center gap-2 rounded-2xl bg-cyan-600 px-6 py-3 text-sm font-bold text-white transition hover:bg-cyan-700 disabled:opacity-60">
                    {submitting ? 'Submitting...' : 'Submit Application'}
                    <ArrowRight size={16} />
                  </button>
                  <Link to={`/apply/${schoolId}/status/check`} className="rounded-2xl border border-slate-300 px-6 py-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50">
                    Already applied? Track status
                  </Link>
                </div>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}