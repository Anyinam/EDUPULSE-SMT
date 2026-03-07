import React, { useEffect, useState } from 'react';
import axios from 'axios';

const DEFAULT_FORM = {
  name: 'Term 1',
  academic_year: `${new Date().getFullYear()}/${new Date().getFullYear() + 1}`,
  start_date: '',
  end_date: '',
  reopening_date: '',
  is_active: false
};

export default function TermManagementPanel() {
  const [terms, setTerms] = useState([]);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const getAuthHeaders = () => ({
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const fetchTerms = async () => {
    try {
      const res = await axios.get('/api/school/terms', getAuthHeaders());
      setTerms(res.data.terms || []);
    } catch (err) {
      setMessage('Failed to load academic terms');
    }
  };

  useEffect(() => {
    fetchTerms();
  }, []);

  const handleCreateTerm = async (e) => {
    e.preventDefault();
    if (!form.name || !form.academic_year || !form.start_date || !form.end_date) {
      setMessage('Please complete all required term fields');
      return;
    }

    try {
      setSaving(true);
      setMessage('');
      await axios.post(
        '/api/school/terms',
        {
          name: form.name,
          academic_year: form.academic_year,
          start_date: form.start_date,
          end_date: form.end_date,
          billing_due_date: form.reopening_date || null,
          is_active: form.is_active
        },
        getAuthHeaders()
      );
      setMessage('Academic term saved successfully');
      setForm(DEFAULT_FORM);
      fetchTerms();
    } catch (err) {
      setMessage(err.response?.data?.message || 'Failed to save term');
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (termId) => {
    try {
      const res = await axios.post(`/api/school/terms/${termId}/activate`, {}, getAuthHeaders());
      
      if (res.data.billing_initiated && res.data.payment_link) {
        setMessage(`✅ ${res.data.message}\n\n💳 ${res.data.billing_message}\n\nCheck your email for payment details.`);
        
        // Optional: Ask if they want to pay now
        if (window.confirm('Payment link generated. Open payment page now?')) {
          window.open(res.data.payment_link, '_blank');
        }
      } else {
        setMessage(`✅ ${res.data.message}`);
      }
      
      fetchTerms();
    } catch (err) {
      setMessage(err.response?.data?.message || 'Failed to activate term');
    }
  };

  return (
    <div className="mt-10 border-t pt-8">
      <h3 className="text-xl font-bold text-slate-800 mb-4">🗓️ Academic Term Management</h3>
      <p className="text-sm text-slate-600 mb-4">
        Proprietor/Headmaster sets term calendar. Vacation Day maps to term end date; Reopening Date is stored and shown on terminal reports.
      </p>

      {message && (
        <div className="mb-4 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3 whitespace-pre-line">
          {message}
        </div>
      )}

      <form onSubmit={handleCreateTerm} className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6">
        <div>
          <label className="block text-xs font-bold text-slate-500 mb-1">Term Name</label>
          <select
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full p-2 border rounded-lg bg-white"
          >
            <option>Term 1</option>
            <option>Term 2</option>
            <option>Term 3</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 mb-1">Academic Year</label>
          <input
            value={form.academic_year}
            onChange={(e) => setForm({ ...form, academic_year: e.target.value })}
            className="w-full p-2 border rounded-lg bg-white"
            placeholder="e.g. 2025/2026"
          />
        </div>

        <div className="flex items-end">
          <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Set as active term
          </label>
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 mb-1">Term Start Date</label>
          <input
            type="date"
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            className="w-full p-2 border rounded-lg bg-white"
          />
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 mb-1">Vacation Day</label>
          <input
            type="date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
            className="w-full p-2 border rounded-lg bg-white"
          />
        </div>

        <div>
          <label className="block text-xs font-bold text-slate-500 mb-1">Reopening Date</label>
          <input
            type="date"
            value={form.reopening_date}
            onChange={(e) => setForm({ ...form, reopening_date: e.target.value })}
            className="w-full p-2 border rounded-lg bg-white"
          />
        </div>

        <div className="md:col-span-3">
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Term Calendar'}
          </button>
        </div>
      </form>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="p-3 text-left">Term</th>
              <th className="p-3 text-left">Year</th>
              <th className="p-3 text-left">Start</th>
              <th className="p-3 text-left">Vacation Day</th>
              <th className="p-3 text-left">Reopening</th>
              <th className="p-3 text-left">Status</th>
              <th className="p-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {terms.length === 0 ? (
              <tr><td colSpan="7" className="p-3 text-slate-500">No terms configured yet.</td></tr>
            ) : (
              terms.map((term) => (
                <tr key={term.id}>
                  <td className="p-3 font-semibold">{term.name}</td>
                  <td className="p-3">{term.academic_year}</td>
                  <td className="p-3">{term.start_date || '-'}</td>
                  <td className="p-3">{term.end_date || '-'}</td>
                  <td className="p-3">{term.billing_due_date || '-'}</td>
                  <td className="p-3">
                    {term.is_active ? (
                      <span className="px-2 py-1 text-xs font-bold bg-green-100 text-green-700 rounded-full">Active</span>
                    ) : (
                      <span className="px-2 py-1 text-xs font-bold bg-slate-100 text-slate-600 rounded-full">Inactive</span>
                    )}
                  </td>
                  <td className="p-3 text-right">
                    {!term.is_active && (
                      <button
                        onClick={() => handleActivate(term.id)}
                        className="text-xs font-bold text-blue-600 hover:text-blue-800"
                      >
                        Set Active
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
