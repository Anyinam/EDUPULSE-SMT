import React, { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import axios from 'axios';
import { ArrowRight, CheckCircle2, FileText, ShieldCheck, Sparkles, UploadCloud } from 'lucide-react';
import usePublicSchoolProfile from '../hooks/usePublicSchoolProfile';

const PARENT_ADMISSION_CONSENT_VERSION = '2026-04-29';

const validGrades = [
  'Nursery', 'KG', 'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6', 'JHS 1', 'JHS 2', 'JHS 3'
];

const intakeHighlights = [
  {
    title: 'Structured review',
    description: 'Applications arrive with learner details and uploaded records organised for school review.',
    icon: Sparkles,
  },
  {
    title: 'Assessment preference',
    description: 'Parents can indicate whether an online assessment or school visit is more practical.',
    icon: ShieldCheck,
  },
  {
    title: 'Status tracking',
    description: 'Each application receives a tracking link so families can monitor the next school update.',
    icon: FileText,
  },
];

const submissionChecklist = [
  'Use a phone number or email address the school can reach quickly.',
  'Upload any available records such as a report card, birth certificate, or guardian ID.',
  'Choose the assessment option that best matches the learner’s internet access and travel plan.',
];

const reviewTimeline = [
  'Application submitted',
  'School reviews learner details and supporting documents',
  'Parent receives a status update, correction request, test path, or visit plan',
];

const inputClassName = 'mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-cyan-600 focus:ring-4 focus:ring-cyan-100';
const cardClassName = 'rounded-3xl border border-slate-200 bg-white p-5 shadow-sm';

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
  const [consentAccepted, setConsentAccepted] = useState(false);

  const statusPath = useMemo(() => result?.status_path || '', [result]);
  const schoolName = schoolProfile?.school_name || schoolId;
  const schoolColor = schoolProfile?.theme_color || '#0f766e';

  const getDocumentKey = (file) => `${file.name}-${file.size}-${file.lastModified}`;

  const handleChange = (event) => {
    setFormData((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const handleDocumentChange = (event) => {
    const nextFiles = Array.from(event.target.files || []);
    if (!nextFiles.length) {
      return;
    }

    setDocuments((current) => {
      const seenKeys = new Set(current.map(getDocumentKey));
      const merged = [...current];

      nextFiles.forEach((file) => {
        const fileKey = getDocumentKey(file);
        if (!seenKeys.has(fileKey)) {
          seenKeys.add(fileKey);
          merged.push(file);
        }
      });

      return merged;
    });

    event.target.value = '';
  };

  const handleRemoveDocument = (fileToRemove) => {
    const fileKey = getDocumentKey(fileToRemove);
    setDocuments((current) => current.filter((file) => getDocumentKey(file) !== fileKey));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    if (!consentAccepted) {
      setError('You must confirm that you are the parent or lawful guardian before submitting this application.');
      setSubmitting(false);
      return;
    }
    try {
      const payload = new FormData();
      Object.entries(formData).forEach(([key, value]) => payload.append(key, value));
      Array.from(documents).forEach((file) => payload.append('documents', file));
      payload.append('consent_confirmed', 'true');
      payload.append('consent_version', PARENT_ADMISSION_CONSENT_VERSION);

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
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7fafc_0%,#ffffff_35%,#f6fbff_100%)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="overflow-hidden rounded-4xl border border-slate-200 bg-white shadow-[0_30px_80px_-45px_rgba(15,23,42,0.22)]">
          <div className="grid gap-8 px-6 py-8 sm:px-10 sm:py-10 lg:grid-cols-[1.15fr,0.85fr]">
            <div>
              <div className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-4 py-2 text-xs font-bold uppercase tracking-[0.2em] text-cyan-800">
                Parent Admissions Application
              </div>
              <h1 className="mt-5 max-w-3xl text-4xl font-black leading-tight text-slate-950 sm:text-5xl">
                Apply to <span style={{ color: schoolColor }}>{schoolName}</span> with a complete, review-ready submission.
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
                Provide the learner profile, guardian contact details, and any supporting records. The school will use this application to decide the next step for review, testing, or a school visit.
              </p>

              <div className="mt-8 grid gap-4 md:grid-cols-3">
                {intakeHighlights.map(({ title, description, icon: Icon }) => (
                  <div key={title} className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900 text-white">
                      <Icon size={18} />
                    </div>
                    <h2 className="mt-4 text-sm font-black uppercase tracking-[0.14em] text-slate-900">{title}</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
                  </div>
                ))}
              </div>
            </div>

            <aside className="rounded-4xl border border-slate-200 bg-slate-50 p-6">
              <div className="mb-6 flex items-center gap-4">
                {schoolProfile?.logo_url ? (
                  <img src={schoolProfile.logo_url} alt={`${schoolName} logo`} className="h-16 w-16 rounded-2xl object-cover ring-1 ring-slate-200" />
                ) : (
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-900 text-lg font-black text-white">{schoolName.slice(0, 2).toUpperCase()}</div>
                )}
                <div>
                  <p className="text-lg font-black text-slate-950">{schoolName}</p>
                  {schoolProfile?.motto ? <p className="text-sm text-slate-600">{schoolProfile.motto}</p> : null}
                </div>
              </div>
              <p className="text-xs font-black uppercase tracking-[0.22em] text-slate-500">What to Expect</p>
              <div className="mt-5 space-y-4">
                <div className={cardClassName}>
                  <p className="text-sm font-semibold text-slate-950">Required for first review</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">Learner name, preferred class, guardian contact, and at least one working parent email or phone number.</p>
                </div>
                <div className={cardClassName}>
                  <p className="text-sm font-semibold text-slate-950">Review timeline</p>
                  <div className="mt-3 space-y-3">
                    {reviewTimeline.map((step, index) => (
                      <div key={step} className="flex gap-3">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
                          {index + 1}
                        </div>
                        <p className="text-sm leading-6 text-slate-600">{step}</p>
                      </div>
                    ))}
                  </div>
                </div>
                {schoolProfile?.admission_fee?.enabled ? (
                  <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5">
                    <p className="text-sm font-semibold text-emerald-950">Admission fee policy</p>
                    <p className="mt-2 text-sm leading-6 text-emerald-900/80">This school currently charges {schoolProfile.admission_fee.currency} {Number(schoolProfile.admission_fee.amount || 0).toFixed(2)} after admission approval.</p>
                  </div>
                ) : null}
                <div className="rounded-3xl border border-cyan-200 bg-cyan-50 p-5">
                  <p className="text-sm font-semibold text-slate-950">Need to check an existing application?</p>
                  <Link to={`/apply/${schoolId}/status/check`} className="mt-3 inline-flex items-center gap-2 text-sm font-bold text-cyan-800 transition hover:text-cyan-950">
                    Open status tracker
                    <ArrowRight size={16} />
                  </Link>
                </div>
              </div>
            </aside>
          </div>
        </section>

        {result ? (
          <div className="rounded-4xl border border-emerald-200 bg-white p-8 shadow-[0_20px_60px_-35px_rgba(16,185,129,0.3)]">
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
          <form onSubmit={handleSubmit} className="rounded-4xl border border-slate-200 bg-white p-6 shadow-[0_24px_70px_-45px_rgba(15,23,42,0.18)] sm:p-8">
            <div className="grid gap-8 lg:grid-cols-[0.85fr,1.15fr]">
              <div className="space-y-5 rounded-4xl border border-slate-200 bg-slate-50 p-6">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.22em] text-slate-500">Parent Checklist</p>
                  <h2 className="mt-3 text-3xl font-black leading-tight text-slate-950">Prepare a complete admission request.</h2>
                  <p className="mt-3 text-sm leading-7 text-slate-600">
                    Complete the form carefully so the admissions team can review the learner without avoidable back-and-forth.
                  </p>
                </div>

                <div className="space-y-3">
                  {submissionChecklist.map((tip) => (
                    <div key={tip} className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-100 text-cyan-700">
                        <CheckCircle2 size={16} />
                      </div>
                      <p className="text-sm leading-6 text-slate-700">{tip}</p>
                    </div>
                  ))}
                </div>

                <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-5">
                  <div className="flex items-center gap-3 text-slate-900">
                    <UploadCloud size={18} />
                    <p className="text-sm font-bold uppercase tracking-[0.16em]">Supporting Documents</p>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">
                    Clear photos or PDFs are acceptable for report cards, birth certificates, and identity documents. Previous reports may be scanned for academic details automatically.
                  </p>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-500">Application Form</p>
                  <h2 className="mt-2 text-3xl font-black text-slate-950">Learner and guardian details</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">Fields marked here help the school decide the appropriate review path and follow-up action.</p>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">Learner Profile</p>
                  <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <FieldLabel>First Name</FieldLabel>
                <input name="first_name" value={formData.first_name} onChange={handleChange} required className={inputClassName} />
              </div>
              <div>
                <FieldLabel>Surname</FieldLabel>
                <input name="surname" value={formData.surname} onChange={handleChange} required className={inputClassName} />
              </div>
              <div>
                <FieldLabel helper="Choose the class you want the learner assessed for.">Preferred Class</FieldLabel>
                <select name="preferred_class" value={formData.preferred_class} onChange={handleChange} className={inputClassName}>
                  {validGrades.map((grade) => <option key={grade} value={grade}>{grade}</option>)}
                </select>
              </div>
              <div>
                <FieldLabel>Gender</FieldLabel>
                <select name="gender" value={formData.gender} onChange={handleChange} className={inputClassName}>
                  {['Male', 'Female', 'Other'].map((gender) => <option key={gender} value={gender}>{gender}</option>)}
                </select>
              </div>
              <div>
                <FieldLabel>Date of Birth</FieldLabel>
                <input name="date_of_birth" type="date" value={formData.date_of_birth} onChange={handleChange} className={inputClassName} />
              </div>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">Guardian Contact</p>
                  <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <FieldLabel helper="The primary adult the school should contact first.">Guardian Name</FieldLabel>
                <input name="guardian_name" value={formData.guardian_name} onChange={handleChange} required className={inputClassName} />
              </div>
              <div>
                <FieldLabel>Parent Email</FieldLabel>
                <input name="parent_email" type="email" value={formData.parent_email} onChange={handleChange} className={inputClassName} />
              </div>
              <div>
                <FieldLabel>Parent Phone</FieldLabel>
                <input name="parent_phone" value={formData.parent_phone} onChange={handleChange} className={inputClassName} />
              </div>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">Assessment Planning</p>
                  <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
              <div>
                <FieldLabel>Preferred Test Mode</FieldLabel>
                <select name="desired_test_mode" value={formData.desired_test_mode} onChange={handleChange} className={inputClassName}>
                  <option value="either">Either Remote or In-Person</option>
                  <option value="online">Online Test</option>
                  <option value="in_person">Visit School</option>
                </select>
              </div>
              <div>
                <FieldLabel helper="This helps the school decide whether remote assessment is realistic.">Internet Quality</FieldLabel>
                <select name="internet_quality" value={formData.internet_quality} onChange={handleChange} className={inputClassName}>
                  <option value="unknown">Prefer not to say</option>
                  <option value="stable">Stable</option>
                  <option value="limited">Limited</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <FieldLabel>Previous School</FieldLabel>
                <input name="prior_school" value={formData.prior_school} onChange={handleChange} className={inputClassName} />
              </div>
                  </div>
                </div>

                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">Documents and Notes</p>
                  <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="md:col-span-2">
                <FieldLabel helper="Birth certificate, previous report, or guardian ID if available.">Supporting Documents</FieldLabel>
                <div className="mt-2 rounded-3xl border border-dashed border-slate-300 bg-white p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Upload supporting records</p>
                      <p className="mt-1 text-xs text-slate-500">Add as many documents as needed. You can reopen the picker to continue adding files before submission.</p>
                    </div>
                    <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold uppercase tracking-[0.14em] text-slate-600">
                      {documents.length} file{documents.length === 1 ? '' : 's'} selected
                    </div>
                  </div>
                  <input type="file" multiple onChange={handleDocumentChange} className="mt-4 w-full text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-sm file:font-bold file:text-white hover:file:bg-slate-800" />
                  <p className="mt-3 text-xs text-slate-500">Previous reports may be scanned automatically to help the admissions team review academic history.</p>
                  {documents.length > 0 ? (
                    <div className="mt-4 space-y-2">
                      {Array.from(documents).map((file) => (
                        <div
                          key={getDocumentKey(file)}
                          className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
                        >
                          <div>
                            <p className="text-sm font-semibold text-slate-800">{file.name}</p>
                            <p className="text-xs text-slate-500">{Math.max(1, Math.round(file.size / 1024))} KB</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleRemoveDocument(file)}
                            className="rounded-full border border-slate-300 px-3 py-1 text-xs font-bold text-slate-600 transition hover:bg-white"
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="md:col-span-2">
                <FieldLabel helper="Share any special context the school should know before review.">Notes</FieldLabel>
                <textarea name="parent_notes" value={formData.parent_notes} onChange={handleChange} rows={5} className={inputClassName} />
              </div>
                  </div>
                </div>

                {error && <p className="text-sm font-semibold text-red-600">{error}</p>}

                <label className="flex items-start gap-3 rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-600">
                  <input
                    type="checkbox"
                    checked={consentAccepted}
                    onChange={(event) => setConsentAccepted(event.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-slate-300"
                  />
                  <span>
                    I confirm that I am the parent or lawful guardian of the learner and I authorise the school to review the submitted details and documents for admissions, placement, school communication, and related educational follow-up.
                  </span>
                </label>

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