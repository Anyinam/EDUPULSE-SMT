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
  owner_information: '{}',
  screening_results: '{}',
  documents: '[]',
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
        setForm({
          legal_name: nextProfile.legal_name || '',
          registration_number: nextProfile.registration_number || '',
          tax_id: nextProfile.tax_id || '',
          license_number: nextProfile.license_number || '',
          bank_account_name: nextProfile.bank_account_name || '',
          bank_account_number: '',
          bank_name: nextProfile.bank_name || '',
          owner_information: JSON.stringify(nextProfile.owner_information || {}, null, 2),
          screening_results: JSON.stringify(nextProfile.screening_results || {}, null, 2),
          documents: JSON.stringify(nextProfile.documents || [], null, 2),
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

    let ownerInformation = {};
    let screeningResults = {};
    let documents = [];

    try {
      ownerInformation = form.owner_information ? JSON.parse(form.owner_information) : {};
    } catch {
      setError('Owner information must be valid JSON.');
      setSaving(false);
      return;
    }

    try {
      screeningResults = form.screening_results ? JSON.parse(form.screening_results) : {};
    } catch {
      setError('Screening results must be valid JSON.');
      setSaving(false);
      return;
    }

    try {
      documents = form.documents ? JSON.parse(form.documents) : [];
    } catch {
      setError('Documents must be valid JSON.');
      setSaving(false);
      return;
    }

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
        screening_results: screeningResults,
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
            <p className="mt-2 max-w-2xl text-sm text-slate-600">Submit your school&apos;s legal identity and bank details for review. Financial actions stay limited until verification is approved.</p>
          </div>
          <div className={`rounded-2xl border px-4 py-3 text-sm font-bold ${statusTone}`}>
            {verification?.is_verified ? 'Verified' : (verification?.status || 'Not submitted')}
          </div>
        </div>

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
            <TextAreaField label="Owner Information (JSON)" name="owner_information" value={form.owner_information} onChange={handleChange} rows={5} />
            <TextAreaField label="Screening Results (JSON)" name="screening_results" value={form.screening_results} onChange={handleChange} rows={5} />
            <div className="lg:col-span-2">
              <TextAreaField label="Supporting Documents (JSON array)" name="documents" value={form.documents} onChange={handleChange} rows={4} />
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
