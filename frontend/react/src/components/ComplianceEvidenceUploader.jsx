import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

export default function ComplianceEvidenceUploader({ artifactCount = 0 }) {
  const [artifacts, setArtifacts] = useState([]);
  const [category, setCategory] = useState('signed_form');
  const [note, setNote] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  }), []);

  const fetchArtifacts = async () => {
    try {
      const response = await axios.get('/api/school/settings/legacy-consent-evidence', { headers });
      setArtifacts(Array.isArray(response.data?.artifacts) ? response.data.artifacts : []);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load consent evidence artifacts.');
    }
  };

  useEffect(() => {
    fetchArtifacts();
  }, []);

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!selectedFile) {
      setError('Choose a file before uploading.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('category', category);
      formData.append('note', note);
      await axios.post('/api/school/settings/legacy-consent-evidence', formData, {
        headers: {
          ...headers,
          'Content-Type': 'multipart/form-data',
        },
      });
      setSelectedFile(null);
      setNote('');
      const fileInput = document.getElementById('legacy-consent-evidence-file');
      if (fileInput) fileInput.value = '';
      await fetchArtifacts();
    } catch (err) {
      setError(err.response?.data?.message || 'Upload failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-slate-800">Stored Consent Artifacts</p>
          <p className="text-xs text-slate-500">Upload scanned forms, signed letters, or office acknowledgements so the compliance workflow has documentary evidence.</p>
        </div>
        <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-bold text-blue-800">
          {Math.max(artifactCount, artifacts.length)} file{Math.max(artifactCount, artifacts.length) === 1 ? '' : 's'}
        </span>
      </div>

      <form onSubmit={handleUpload} className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Category</label>
          <select value={category} onChange={(event) => setCategory(event.target.value)} className="w-full rounded-lg border p-3 bg-white">
            <option value="signed_form">Signed Consent Form</option>
            <option value="notice_copy">Notice Copy</option>
            <option value="office_record">Office Record</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Evidence Note</label>
          <input value={note} onChange={(event) => setNote(event.target.value)} className="w-full rounded-lg border p-3 bg-white" placeholder="Example: signed forms from JHS 2 parents" />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Upload File</label>
          <input id="legacy-consent-evidence-file" type="file" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} className="w-full rounded-lg border p-3 bg-white" />
        </div>
        <div className="lg:col-span-3 flex flex-wrap items-center gap-3">
          <button type="submit" disabled={loading} className="rounded-lg bg-slate-900 px-4 py-3 text-sm font-bold text-white hover:bg-slate-800 disabled:opacity-60">
            {loading ? 'Uploading...' : 'Upload Evidence'}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      </form>

      <div className="mt-4 space-y-3">
        {artifacts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
            No consent evidence files uploaded yet.
          </div>
        ) : (
          artifacts.map((artifact) => (
            <div key={artifact.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-4">
              <div>
                <p className="text-sm font-bold text-slate-800">{artifact.original_filename}</p>
                <p className="text-xs text-slate-500">{artifact.category} • {artifact.note || 'No note added'}</p>
                <p className="text-xs text-slate-400">{artifact.uploaded_at ? new Date(artifact.uploaded_at).toLocaleString() : 'Unknown upload time'}</p>
              </div>
              <a href={artifact.download_path} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-bold text-white hover:bg-blue-700">
                Download
              </a>
            </div>
          ))
        )}
      </div>
    </div>
  );
}