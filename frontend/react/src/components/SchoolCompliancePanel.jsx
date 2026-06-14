import React, { useEffect, useState } from 'react';
import axios from 'axios';

function getHeaders() {
  return {
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  };
}

const EMPTY_FORM = {
  legal_name: '',
  registration_number: '',
  tax_id: '',
  license_number: '',
  bank_account_name: '',
  bank_account_number: '',
  bank_name: '',
  owner_name: '',
  owner_phone: '',
  owner_email: '',
  document_links: '',
};

export default function SchoolCompliancePanel() {
  const [verification, setVerification] = useState(null);
  const [profile, setProfile] = useState(null);
  const [flags, setFlags] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const fetchData = async () => {
    try {
      setLoading(true);
      const [verificationRes, flagsRes] = await Promise.all([
        axios.get('/api/school/verification', { headers: getHeaders() }),
        axios.get('/api/proprietor/compliance/aml-flags', { headers: getHeaders() }),
      ]);
      setVerification(verificationRes.data?.verification || null);
      setProfile(verificationRes.data?.profile || null);
      setFlags(Array.isArray(flagsRes.data?.flags) ? flagsRes.data.flags : []);
      if (verificationRes.data?.profile) {
        const nextProfile = verificationRes.data.profile;
        const ownerInfo = nextProfile.owner_information || {};
        const documentLinks = Array.isArray(nextProfile.documents)
          ? nextProfile.documents.map((entry) => {
              if (typeof entry === 'string') {
                return entry;
              }
              if (entry && typeof entry === 'object') {
                return entry.url || entry.link || entry.name || '';
              }
              return '';
            }).filter(Boolean).join('\n')
          : '';
        setForm({
          legal_name: nextProfile.legal_name || '',
          registration_number: nextProfile.registration_number || '',
          tax_id: nextProfile.tax_id || '',
          license_number: nextProfile.license_number || '',
          bank_account_name: nextProfile.bank_account_name || '',
          bank_account_number: '',
          bank_name: nextProfile.bank_name || '',
          owner_name: ownerInfo.full_name || ownerInfo.name || '',
          owner_phone: ownerInfo.phone || ownerInfo.phone_number || '',
          owner_email: ownerInfo.email || '',
          document_links: documentLinks,
        });
      }
      setError('');
      setMessage('');
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load compliance data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const submitVerification = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');

    const ownerInformation = {
      full_name: form.owner_name.trim(),
      phone: form.owner_phone.trim(),
      email: form.owner_email.trim(),
    };
    const documents = form.document_links
      .split('\n')
      .map((entry) => entry.trim())
      .filter(Boolean)
      .map((url) => ({ url }));

    try {
      const payload = {
        legal_name: form.legal_name,
        registration_number: form.registration_number,
        tax_id: form.tax_id,
        license_number: form.license_number,
        bank_account_name: form.bank_account_name,
        bank_account_number: form.bank_account_number,
        bank_name: form.bank_name,
        owner_information: ownerInformation,
        documents,
      };
      const response = await axios.put('/api/school/verification', payload, { headers: getHeaders() });
      setMessage(response.data?.message || 'Verification profile submitted.');
      await fetchData();
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to submit verification.');
    } finally {
      setSaving(false);
    }
  };

  const resolveFlag = async (flagId) => {
    const notes = window.prompt('Resolution notes (optional):') || '';
    try {
      await axios.post(
        `/api/proprietor/compliance/aml-flags/${flagId}/resolve`,
        { notes },
        { headers: getHeaders() },
      );
      await fetchData();
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to resolve AML flag.');
    }
  };

  const statusTone = verification?.is_verified
    ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
    : verification?.status === 'pending'
      ? 'bg-amber-100 text-amber-800 border-amber-200'
      : 'bg-slate-100 text-slate-700 border-slate-200';

  return (
    <div className="space-y-8">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">Compliance Center</p>
            <h2 className="mt-1 text-2xl font-black text-slate-900">School Verification</h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-600">Submit your school&apos;s legal identity and banking details for review. EduPulse handles screening after submission, so this form stays focused on the business information only.</p>
          </div>
          <div className={`rounded-2xl border px-4 py-3 text-sm font-bold ${statusTone}`}>
            {verification?.is_verified ? 'Verified' : (verification?.status || 'Not submitted')}
          </div>
        </div>

        {verification?.review_notes && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <span className="font-bold">Review note:</span> {verification.review_notes}
          </div>
        )}

        {loading ? (
          <p className="mt-6 text-sm text-slate-500">Loading compliance data...</p>
        ) : (
          <form onSubmit={submitVerification} className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Field label="Legal Name" name="legal_name" value={form.legal_name} onChange={handleChange} placeholder="Registered school name" />
            <Field label="Organization / Tenant ID" value={localStorage.getItem('school_id') || ''} readOnly />
            <Field label="Registration Number" name="registration_number" value={form.registration_number} onChange={handleChange} placeholder="Registrar-General number" />
            <Field label="Tax ID" name="tax_id" value={form.tax_id} onChange={handleChange} placeholder="TIN or equivalent" />
            <Field label="License Number" name="license_number" value={form.license_number} onChange={handleChange} placeholder="Education license, if applicable" />
            <Field label="Bank Account Name" name="bank_account_name" value={form.bank_account_name} onChange={handleChange} placeholder="Must match school legal name" />
            <Field label="Bank Account Number" name="bank_account_number" value={form.bank_account_number} onChange={handleChange} placeholder="For verification only" />
            <Field label="Bank Name" name="bank_name" value={form.bank_name} onChange={handleChange} placeholder="Bank of account" />
            <Field label="Proprietor / Owner Name" name="owner_name" value={form.owner_name} onChange={handleChange} placeholder="Full legal name of proprietor or owner" />
            <Field label="Owner Phone Number" name="owner_phone" value={form.owner_phone} onChange={handleChange} placeholder="Primary contact number" />
            <Field label="Owner Email Address" name="owner_email" value={form.owner_email} onChange={handleChange} placeholder="Primary compliance contact email" className="lg:col-span-2" />
            <div className="lg:col-span-2">
              <TextAreaField label="Supporting Document Links" name="document_links" value={form.document_links} onChange={handleChange} rows={4} placeholder="Paste one document link per line (optional)" />
              <p className="mt-2 text-xs text-slate-500">Examples: certificate of registration, tax certificate, education license, or bank confirmation letter.</p>
            </div>
            <div className="lg:col-span-2 flex flex-wrap items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={saving}
                className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? 'Submitting...' : 'Submit for Review'}
              </button>
              {message && <p className="text-sm font-semibold text-emerald-700">{message}</p>}
              {error && <p className="text-sm font-semibold text-red-600">{error}</p>}
            </div>
          </form>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">AML Monitoring</p>
            <h3 className="mt-1 text-xl font-black text-slate-900">Open Transaction Flags</h3>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">{flags.length} open</span>
        </div>

        <div className="mt-4 space-y-3">
          {flags.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
              No AML flags at the moment.
            </div>
          ) : (
            flags.map((flag) => (
              <div key={flag.id} className="rounded-2xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-slate-900">{flag.summary}</p>
                    <p className="mt-1 text-xs text-slate-500">{flag.rule_code} • {flag.severity} • {flag.created_at ? new Date(flag.created_at).toLocaleString() : 'Recently'}</p>
                    {flag.details && Object.keys(flag.details).length > 0 && (
                      <pre className="mt-3 overflow-x-auto rounded-xl bg-slate-50 p-3 text-[11px] text-slate-600">{JSON.stringify(flag.details, null, 2)}</pre>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => resolveFlag(flag.id)}
                    className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700"
                  >
                    Mark Resolved
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function Field({ label, className = '', ...props }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-2 block text-xs font-black uppercase tracking-[0.2em] text-slate-400">{label}</span>
      <input
        {...props}
        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
      />
    </label>
  );
}

function TextAreaField({ label, className = '', ...props }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-2 block text-xs font-black uppercase tracking-[0.2em] text-slate-400">{label}</span>
      <textarea
        {...props}
        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
      />
    </label>
  );
}
