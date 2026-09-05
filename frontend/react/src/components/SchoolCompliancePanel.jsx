import React, { useEffect, useState } from 'react';
import axios from 'axios';

function getHeaders() {
  return {
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  };
}

async function extractBlobErrorMessage(err, fallbackMessage) {
  const responseData = err?.response?.data;
  if (!responseData) {
    return fallbackMessage;
  }

  if (typeof responseData?.text === 'function') {
    try {
      const rawText = await responseData.text();
      if (!rawText) {
        return fallbackMessage;
      }

      try {
        const parsed = JSON.parse(rawText);
        return parsed?.message || rawText || fallbackMessage;
      } catch {
        return rawText || fallbackMessage;
      }
    } catch {
      return fallbackMessage;
    }
  }

  return responseData?.message || fallbackMessage;
}

const EMPTY_FORM = {
  legal_name: '',
  registration_number: '',
  tax_id: '',
  license_number: '',
  owner_name: '',
  owner_phone: '',
  owner_email: '',
};

export default function SchoolCompliancePanel() {
  const [verification, setVerification] = useState(null);
  const [profile, setProfile] = useState(null);
  const [flags, setFlags] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [existingDocuments, setExistingDocuments] = useState([]);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const submissionLocked = ['pending', 'review_required', 'verified', 'suspended'].includes(verification?.status);

  const lockConfig = {
    pending: {
      title: 'Submission pending review',
      detail: 'Your documents have already been sent. Wait for the compliance review decision before trying again.',
      buttonLabel: 'Review Pending',
    },
    review_required: {
      title: 'Manual review in progress',
      detail: 'This case is already with the platform compliance team. If they need changes, they will send review notes instead of requiring a duplicate submission.',
      buttonLabel: 'Under Review',
    },
    verified: {
      title: 'School already verified',
      detail: 'No new submission is needed right now. Submit again only if the current verification expires or support asks for refreshed documents.',
      buttonLabel: 'Already Verified',
    },
    suspended: {
      title: 'Verification suspended',
      detail: 'This verification case is suspended. Contact platform support before attempting another submission.',
      buttonLabel: 'Suspended',
    },
  };
  const activeLock = lockConfig[verification?.status] || null;

  const fetchData = async ({ preserveMessage = false, nextMessage = '' } = {}) => {
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
        setExistingDocuments(Array.isArray(nextProfile.documents) ? nextProfile.documents : []);
        setForm({
          legal_name: nextProfile.legal_name || '',
          registration_number: nextProfile.registration_number || '',
          tax_id: nextProfile.tax_id || '',
          license_number: nextProfile.license_number || '',
          owner_name: ownerInfo.full_name || ownerInfo.name || '',
          owner_phone: ownerInfo.phone || ownerInfo.phone_number || '',
          owner_email: ownerInfo.email || '',
        });
      } else {
        setExistingDocuments([]);
      }
      setSelectedFiles([]);
      setFileInputKey((current) => current + 1);
      setError('');
      if (preserveMessage) {
        setMessage(nextMessage);
      } else {
        setMessage('');
      }
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

  const handleFileChange = (event) => {
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
    const files = Array.from(event.target.files || []).filter((file) => {
      if (allowedTypes.includes(file.type)) {
        return true;
      }
      return /\.(jpg|jpeg|png|pdf)$/i.test(file.name || '');
    });
    setSelectedFiles(files);
  };

  const openProtectedDocument = async (documentItem) => {
    if (!documentItem?.download_path) {
      setError('This document is not available to open.');
      return;
    }

    try {
      const res = await axios.get(documentItem.download_path, {
        headers: getHeaders(),
        responseType: 'blob',
      });
      const contentType = res.headers['content-type'] || documentItem.content_type || 'application/octet-stream';
      const blob = new Blob([res.data], { type: contentType });
      const blobUrl = window.URL.createObjectURL(blob);
      const opened = window.open(blobUrl, '_blank', 'noopener,noreferrer');

      if (!opened) {
        const link = document.createElement('a');
        link.href = blobUrl;
        link.setAttribute('download', documentItem.original_filename || documentItem.filename || 'verification-document');
        document.body.appendChild(link);
        link.click();
        link.remove();
      }

      window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
      setError('');
    } catch (err) {
      setError(await extractBlobErrorMessage(err, 'Failed to open verification document.'));
    }
  };

  const submitVerification = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');

    if (submissionLocked) {
      setError(activeLock?.detail || 'This school already has a submitted verification record. Wait for review before sending another one.');
      setSaving(false);
      return;
    }

    if (selectedFiles.length === 0 && existingDocuments.length === 0) {
      setError('Upload at least one JPG, PNG, or PDF verification document.');
      setSaving(false);
      return;
    }

    const ownerInformation = {
      full_name: form.owner_name.trim(),
      phone: form.owner_phone.trim(),
      email: form.owner_email.trim(),
    };
    try {
      const payload = new FormData();
      payload.append('legal_name', form.legal_name);
      payload.append('registration_number', form.registration_number);
      payload.append('tax_id', form.tax_id);
      payload.append('license_number', form.license_number);
      payload.append('owner_information', JSON.stringify(ownerInformation));
      payload.append('existing_documents', JSON.stringify(existingDocuments));
      selectedFiles.forEach((file) => {
        payload.append('documents', file);
      });

      const response = await axios.put('/api/school/verification', payload, {
        headers: {
          ...getHeaders(),
          'Content-Type': 'multipart/form-data',
        },
      });
      const successMessage = response.data?.message || 'Verification profile submitted.';
      setMessage(successMessage);
      await fetchData({ preserveMessage: true, nextMessage: successMessage });
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
            <p className="mt-2 max-w-2xl text-sm text-slate-600">Submit your school&apos;s legal identity, founder details, and certificate documents for review. EduPulse handles screening after submission, so onboarding stays focused on business verification only.</p>
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

        {submissionLocked && (
          <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            <span className="font-bold">{activeLock?.title || 'Submission locked'}:</span> {activeLock?.detail || 'This school already has a verification case in progress.'}
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
            <Field label="Proprietor / Owner Name" name="owner_name" value={form.owner_name} onChange={handleChange} placeholder="Full legal name of proprietor or owner" />
            <Field label="Owner Phone Number" name="owner_phone" value={form.owner_phone} onChange={handleChange} placeholder="Primary contact number" />
            <Field label="Owner Email Address" name="owner_email" value={form.owner_email} onChange={handleChange} placeholder="Primary compliance contact email" className="lg:col-span-2" />
            <div className="lg:col-span-2">
              <label className="block">
                <span className="mb-2 block text-xs font-black uppercase tracking-[0.2em] text-slate-400">Business Certificate Upload</span>
                <input
                  key={fileInputKey}
                  type="file"
                  multiple
                  required={existingDocuments.length === 0}
                  accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
                  onChange={handleFileChange}
                  className="w-full text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-bold file:text-white hover:file:bg-slate-800"
                />
              </label>
              <p className="mt-2 text-xs text-slate-500">Upload at least one JPG, PNG, or PDF file for the registration certificate, tax certificate, or education license.</p>
              {selectedFiles.length > 0 && (
                <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                  {selectedFiles.map((file) => (
                    <div key={`${file.name}-${file.size}`}>{file.name}</div>
                  ))}
                </div>
              )}
              {existingDocuments.length > 0 && (
                <div className="mt-3 rounded-2xl border border-slate-200 bg-white p-3">
                  <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">Uploaded Documents</p>
                  <div className="mt-2 space-y-2 text-sm text-slate-700">
                    {existingDocuments.map((entry, index) => {
                      const label = entry?.original_filename || entry?.name || entry?.url || `Document ${index + 1}`;
                      const href = entry?.download_path || entry?.url || '';
                      return href ? (
                        <button
                          type="button"
                          key={`${label}-${index}`}
                          onClick={() => openProtectedDocument(entry)}
                          className="block font-semibold text-slate-900 underline-offset-2 hover:underline"
                        >
                          {label}
                        </button>
                      ) : (
                        <div key={`${label}-${index}`}>{label}</div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <div className="lg:col-span-2 flex flex-wrap items-center gap-3 pt-2">
              <button
                type="submit"
                disabled={saving || submissionLocked}
                className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? 'Submitting...' : submissionLocked ? (activeLock?.buttonLabel || 'Already Submitted') : 'Submit for Review'}
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
