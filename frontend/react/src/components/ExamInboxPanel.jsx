import React, { useEffect, useState } from 'react';
import axios from 'axios';

export default function ExamInboxPanel({ title = 'Exam Inbox', onInboxChange }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);

  const getAuthHeaders = () => ({
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const fetchInbox = async () => {
    try {
      setLoading(true);
      const res = await axios.get('/api/exams/papers/inbox', getAuthHeaders());
      const inbox = Array.isArray(res.data) ? res.data : [];
      setItems(inbox);
      if (typeof onInboxChange === 'function') {
        onInboxChange(inbox.length);
      }
    } catch (error) {
      console.error('Failed to load exam inbox', error);
      setItems([]);
      if (typeof onInboxChange === 'function') {
        onInboxChange(0);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInbox();

    const refreshTimer = setInterval(() => {
      fetchInbox();
    }, 45000);

    return () => clearInterval(refreshTimer);
  }, []);

  const viewPaper = async (paperId) => {
    try {
      const res = await axios.get(`/api/exams/papers/${paperId}`, getAuthHeaders());
      setSelectedPaper(res.data);
    } catch (error) {
      console.error('Failed to open exam paper', error);
      alert('Failed to load full exam paper details.');
    }
  };

  const reviewPaper = async (paperId, action) => {
    const feedback = window.prompt(
      action === 'approve' ? 'Optional feedback for approval:' : 'Optional reason for return:'
    );
    if (feedback === null) return;

    try {
      setReviewLoading(true);
      await axios.post(
        `/api/exams/papers/${paperId}/review`,
        { action, feedback },
        getAuthHeaders()
      );
      alert(`Exam paper ${action === 'approve' ? 'processed successfully' : 'returned to teacher'}.`);
      if (selectedPaper?.id === paperId) {
        setSelectedPaper(null);
      }
      fetchInbox();
    } catch (error) {
      console.error('Review action failed', error);
      alert(error.response?.data?.message || 'Review action failed.');
    } finally {
      setReviewLoading(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-indigo-100">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-indigo-900">📥 {title}</h3>
        <button
          onClick={fetchInbox}
          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
        >
          Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-sm text-slate-500">Loading exam inbox...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No submitted exam papers in your queue.</p>
      ) : (
        <div className="space-y-3">
          {items.slice(0, 8).map((paper) => (
            <div key={paper.id} className="p-3 border rounded-lg bg-indigo-50">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-800">{paper.title}</p>
                  <p className="text-xs text-slate-600">{paper.class_name} • {paper.subject_name}</p>
                  <p className="text-xs text-slate-500">From: {paper.teacher_name || `Teacher #${paper.teacher_id}`}</p>
                  <p className="text-xs text-indigo-700 font-semibold mt-1">{paper.status}</p>
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => viewPaper(paper.id)}
                    className="px-3 py-1.5 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
                  >
                    View
                  </button>
                  <button
                    disabled={reviewLoading}
                    onClick={() => reviewPaper(paper.id, 'approve')}
                    className="px-3 py-1.5 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    disabled={reviewLoading}
                    onClick={() => reviewPaper(paper.id, 'reject')}
                    className="px-3 py-1.5 text-xs rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                  >
                    Return
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedPaper && (
        <div className="mt-5 p-4 border rounded-lg bg-slate-50">
          <div className="flex justify-between items-start mb-2">
            <h4 className="font-bold text-slate-800">{selectedPaper.title}</h4>
            <button
              onClick={() => setSelectedPaper(null)}
              className="text-xs px-2 py-1 rounded bg-slate-200 hover:bg-slate-300"
            >
              Close
            </button>
          </div>
          <p className="text-xs text-slate-600 mb-2">
            {selectedPaper.class_name} • {selectedPaper.subject_name} • {selectedPaper.exam_type}
          </p>
          <p className="text-xs text-slate-700 mb-3">{selectedPaper.instructions || 'No instructions provided.'}</p>
          <div className="max-h-48 overflow-y-auto space-y-2">
            {(selectedPaper.questions || []).map((q, index) => (
              <div key={`${index}-${q.question || 'question'}`} className="bg-white p-2 rounded border text-xs">
                <p className="font-semibold">Q{index + 1}. {q.question}</p>
                {Array.isArray(q.options) && q.options.length > 0 && (
                  <ul className="mt-1 list-disc ml-4 text-slate-600">
                    {q.options.filter(Boolean).map((opt) => (
                      <li key={`${index}-${opt}`}>{opt}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
