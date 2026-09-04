import React, { useEffect, useState } from 'react';
import axios from 'axios';

function getHeaders(tokenStorageKey) {
  return {
    headers: {
      Authorization: `Bearer ${localStorage.getItem(tokenStorageKey)}`,
    },
  };
}

export default function PlatformComplianceQueue({ tokenStorageKey = 'platform_token' }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('all');

  const openProtectedDocument = async (documentItem) => {
    if (!documentItem?.download_path) {
      setError('This document is not available to open.');
      return;
    }

    try {
      const res = await axios.get(documentItem.download_path, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem(tokenStorageKey)}`,
        },
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
      setError(err.response?.data?.message || 'Failed to open verification document.');
    }
  };

  const fetchCases = async () => {
    try {
      setLoading(true);
      const res = await axios.get(
        `/api/platform/compliance/schools?status=${encodeURIComponent(selectedStatus)}`,
        getHeaders(tokenStorageKey),
      );
      setCases(Array.isArray(res.data?.cases) ? res.data.cases : []);
      setError('');
      setMessage('');
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load compliance queue.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedStatus]);

  const decide = async (schoolId, status) => {
    const reviewNotes = window.prompt(`Review notes for ${schoolId} (${status})`) || '';
    const riskTier = window.prompt('Risk tier: low, medium, high', 'medium') || 'medium';
    const expiresInDays = status === 'verified' ? Number(window.prompt('Verification expiry days', '365') || '365') : undefined;

    try {
      await axios.post(
        `/api/platform/compliance/schools/${schoolId}/decision`,
        {
          status,
          risk_tier: riskTier,
          review_notes: reviewNotes,
          expires_in_days: Number.isFinite(expiresInDays) ? expiresInDays : 365,
        },
        getHeaders(tokenStorageKey),
      );
      setMessage(`Decision saved for ${schoolId}.`);
      await fetchCases();
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to save decision.');
    }
  };

  return (
    <section className="rounded-3xl border border-slate-700 bg-slate-800 p-6 shadow-lg text-white">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.2em] text-slate-400">Platform Compliance</p>
          <h2 className="mt-1 text-2xl font-black text-white">School Verification Queue</h2>
          <p className="mt-2 max-w-2xl text-sm text-slate-300">Review newly registered schools, assign risk, and approve or reject verification before finance actions are allowed.</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">
            Status
            <select
              value={selectedStatus}
              onChange={(event) => setSelectedStatus(event.target.value)}
              className="ml-3 rounded-xl border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white"
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="verified">Verified</option>
              <option value="rejected">Rejected</option>
              <option value="suspended">Suspended</option>
              <option value="review_required">Review Required</option>
            </select>
          </label>
          <button
            type="button"
            onClick={fetchCases}
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-500"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {loading ? (
          <p className="text-sm text-slate-300">Loading verification cases...</p>
        ) : cases.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-600 bg-slate-900 p-4 text-sm text-slate-400">
            No cases in this queue.
          </div>
        ) : (
          cases.map((item) => (
            <div key={item.verification_id} className="rounded-2xl border border-slate-700 bg-slate-900 p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-bold text-white">{item.school_name}</p>
                  <p className="mt-1 text-xs text-slate-400">{item.school_id} • {item.status} • risk {item.risk_tier}</p>
                  <p className="mt-2 text-xs text-slate-300">Legal name: {item.legal_name || 'N/A'}</p>
                  <p className="text-xs text-slate-300">Registration: {item.registration_number || 'N/A'}</p>
                  <p className="text-xs text-slate-300">TIN: {item.tax_id || 'N/A'}</p>
                  <p className="text-xs text-slate-300">Owner: {item.owner_information?.full_name || item.owner_information?.name || 'N/A'}</p>
                  <p className="text-xs text-slate-300">Submitted: {item.submitted_at ? new Date(item.submitted_at).toLocaleString() : 'N/A'}</p>
                  {Array.isArray(item.documents) && item.documents.length > 0 && (
                    <div className="mt-3 rounded-2xl border border-slate-700 bg-slate-800/60 p-3">
                      <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400">Documents</p>
                      <div className="mt-2 space-y-2">
                        {item.documents.map((document, index) => {
                          const label = document?.original_filename || document?.name || document?.url || `Document ${index + 1}`;
                          const href = document?.download_path || document?.url || '';
                          return href ? (
                            <button
                              type="button"
                              key={`${item.verification_id}-${label}-${index}`}
                              onClick={() => openProtectedDocument(document)}
                              className="block text-xs font-semibold text-blue-300 underline-offset-2 hover:text-blue-200 hover:underline"
                            >
                              {label}
                            </button>
                          ) : (
                            <div key={`${item.verification_id}-${label}-${index}`} className="text-xs text-slate-300">
                              {label}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                  {item.review_notes && <p className="mt-2 text-xs text-amber-300">Review note: {item.review_notes}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => decide(item.school_id, 'verified')}
                    className="rounded-xl bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-500"
                  >
                    Verify
                  </button>
                  <button
                    type="button"
                    onClick={() => decide(item.school_id, 'review_required')}
                    className="rounded-xl bg-amber-600 px-3 py-2 text-xs font-bold text-white hover:bg-amber-500"
                  >
                    Review
                  </button>
                  <button
                    type="button"
                    onClick={() => decide(item.school_id, 'rejected')}
                    className="rounded-xl bg-red-600 px-3 py-2 text-xs font-bold text-white hover:bg-red-500"
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => decide(item.school_id, 'suspended')}
                    className="rounded-xl bg-slate-700 px-3 py-2 text-xs font-bold text-white hover:bg-slate-600"
                  >
                    Suspend
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {(message || error) && (
        <div className="mt-4 rounded-2xl border border-slate-700 bg-slate-900 p-4 text-sm">
          {message && <p className="font-semibold text-emerald-300">{message}</p>}
          {error && <p className="font-semibold text-red-300">{error}</p>}
        </div>
      )}
    </section>
  );
}
