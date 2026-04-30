import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

export default function ExamIntelligencePanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [examType, setExamType] = useState('BECE');
  const [academicYear, setAcademicYear] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [resultText, setResultText] = useState('');

  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  }), []);

  const fetchDashboard = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get('/api/analytics/exam-intelligence', { headers });
      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load exam intelligence.');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!selectedFile) {
      setError('Choose the school result document before importing.');
      return;
    }

    setUploading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('exam_type', examType);
      formData.append('academic_year', academicYear);
      formData.append('result_text', resultText);
      await axios.post('/api/analytics/exam-imports', formData, {
        headers: {
          ...headers,
          'Content-Type': 'multipart/form-data',
        },
      });
      setSelectedFile(null);
      setResultText('');
      const fileInput = document.getElementById('exam-intelligence-file');
      if (fileInput) fileInput.value = '';
      await fetchDashboard();
    } catch (err) {
      setError(err.response?.data?.message || 'Exam import failed.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.3em] text-emerald-700">Exam Intelligence</p>
          <h3 className="mt-2 text-2xl font-black text-slate-900">BECE and WAEC Import Workspace</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-600">Upload school-owned result lists as CSV, keep each batch downloadable, and turn them into year-over-year subject and gender performance signals for leadership review.</p>
        </div>
        <div className={`rounded-2xl px-4 py-3 text-sm font-bold ${data?.compliance_ready ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
          {data?.compliance_ready ? 'Compliance checks ready for import' : 'Complete school settings checks before import'}
        </div>
      </div>

      {!data?.compliance_ready && data?.compliance_gaps && (
        <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-bold">Required before BECE or WAEC import</p>
          <p className="mt-1">School data authority: {data.compliance_gaps.school_data_authority_confirmed ? 'confirmed' : 'missing'} | Exam processing enabled: {data.compliance_gaps.bece_result_processing_enabled ? 'confirmed' : 'missing'} | Parent notice basis: {data.compliance_gaps.bece_parent_notice_confirmed ? 'confirmed' : 'missing'}</p>
        </div>
      )}

      <form onSubmit={handleUpload} className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Exam Type</label>
          <select value={examType} onChange={(event) => setExamType(event.target.value)} className="w-full rounded-xl border p-3 bg-white">
            <option value="BECE">BECE</option>
            <option value="WAEC">WAEC</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Academic Year</label>
          <input value={academicYear} onChange={(event) => setAcademicYear(event.target.value)} className="w-full rounded-xl border p-3 bg-white" placeholder="2025/2026" />
        </div>
        <div>
          <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Result Document</label>
          <input id="exam-intelligence-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} className="w-full rounded-xl border p-3 bg-white" />
        </div>
        <div className="flex items-end">
          <button type="submit" disabled={uploading} className="w-full rounded-xl bg-emerald-700 px-4 py-3 text-sm font-bold text-white hover:bg-emerald-800 disabled:opacity-60">
            {uploading ? 'Importing...' : 'Import Result List'}
          </button>
        </div>
      </form>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <label className="block text-xs font-bold uppercase tracking-wide text-slate-500 mb-2">Extracted Result Text</label>
        <textarea
          value={resultText}
          onChange={(event) => setResultText(event.target.value)}
          rows={6}
          className="w-full rounded-xl border p-3 bg-white"
          placeholder={
            'Paste extracted rows here when the uploaded PDF cannot be parsed automatically.\nFormat:\nAma Mensah | Female | Mathematics | 82 | A1\nAma Mensah | Female | English Language | 79 | B2'
          }
        />
        <p className="mt-2 text-xs text-slate-500">
          Use this when the uploaded result sheet is a scan, a photo, or a PDF that does not expose text cleanly. Text-based PDFs can now be parsed automatically. Image files can also be OCR-processed when the print quality is good enough.
        </p>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {loading ? (
        <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-500">Loading exam intelligence...</div>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-2xl bg-slate-900 p-5 text-white">
              <p className="text-xs uppercase tracking-wide text-slate-300">Imported Batches</p>
              <p className="mt-2 text-3xl font-black">{data?.summary?.total_imports || 0}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 p-5">
              <p className="text-xs uppercase tracking-wide text-slate-500">Latest Average</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{Number(data?.summary?.latest_average_score || 0).toFixed(1)}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 p-5">
              <p className="text-xs uppercase tracking-wide text-slate-500">Latest Pass Rate</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{Number(data?.summary?.latest_pass_rate || 0).toFixed(1)}%</p>
            </div>
            <div className="rounded-2xl border border-slate-200 p-5">
              <p className="text-xs uppercase tracking-wide text-slate-500">Latest Candidates</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{data?.summary?.latest_candidate_count || 0}</p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 p-5">
              <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Subject Trend Snapshot</h4>
              <div className="mt-4 space-y-3">
                {(data?.subject_trends || []).length === 0 ? (
                  <p className="text-sm text-slate-500">Upload at least one batch to compute subject trends.</p>
                ) : (
                  data.subject_trends.map((item) => (
                    <div key={item.subject} className="rounded-xl bg-slate-50 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-bold text-slate-800">{item.subject}</p>
                        <span className={`text-xs font-bold ${item.delta === null ? 'text-slate-500' : item.delta >= 0 ? 'text-emerald-700' : 'text-red-600'}`}>
                          {item.delta === null ? 'No prior baseline' : `${item.delta >= 0 ? '+' : ''}${item.delta.toFixed(1)} pts`}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">Latest average {Number(item.latest_average || 0).toFixed(1)} • Pass rate {Number(item.latest_pass_rate || 0).toFixed(1)}%</p>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 p-5">
              <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Latest Gender Comparison</h4>
              <div className="mt-4 space-y-3">
                {(data?.gender_comparison || []).length === 0 ? (
                  <p className="text-sm text-slate-500">No gender breakdown available yet.</p>
                ) : (
                  data.gender_comparison.map((item) => (
                    <div key={item.gender} className="rounded-xl bg-slate-50 p-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-bold text-slate-800">{item.gender}</p>
                        <p className="text-xs text-slate-500">{item.entries} subject entries</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold text-slate-800">{Number(item.average_score || 0).toFixed(1)}</p>
                        <p className="text-xs text-slate-500">{Number(item.pass_rate || 0).toFixed(1)}% pass</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-slate-200 p-5">
            <h4 className="text-sm font-bold uppercase tracking-wide text-slate-700">Imported Result Batches</h4>
            <div className="mt-4 space-y-3">
              {(data?.batches || []).length === 0 ? (
                <p className="text-sm text-slate-500">No result lists imported yet.</p>
              ) : (
                data.batches.map((batch) => (
                  <div key={batch.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-200 p-4">
                    <div>
                      <p className="text-sm font-bold text-slate-800">{batch.exam_type} • {batch.academic_year}</p>
                      <p className="text-xs text-slate-500">{batch.source_filename} • {batch.candidate_count} candidates • {Number(batch.average_score || 0).toFixed(1)} average • {Number(batch.pass_rate || 0).toFixed(1)}% pass</p>
                      <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-400">Source: {batch.source_format || 'document'} • Parse mode: {batch.parse_mode || 'structured_text'}</p>
                    </div>
                    <a href={batch.download_path} className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-bold text-white hover:bg-slate-800">
                      Download Source File
                    </a>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}