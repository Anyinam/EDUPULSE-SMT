import React, { useEffect, useState } from 'react';
import axios from 'axios';

const buildActivationMessage = (payload) => {
  if (!payload) {
    return 'Failed to activate term';
  }

  if (payload.error === 'billing_payment_required') {
    return `${payload.message}\n\nPayment link ready: ${payload.payment_link}\nReference: ${payload.reference}\n\nThe term will activate after payment is completed.`;
  }

  if (payload.error === 'billing_charge_failed' || payload.error === 'billing_processing_failed' || payload.error === 'billing_precheck_failed') {
    return `${payload.message}\n\nThe term remains inactive until billing is resolved.`;
  }

  return payload.message || 'Failed to activate term';
};

const fallbackAcademicYear = () => {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth() + 1;
  return month >= 8 ? `${year}/${year + 1}` : `${year - 1}/${year}`;
};

const DEFAULT_FORM = {
  name: 'Term 1',
  academic_year: fallbackAcademicYear(),
  start_date: '',
  end_date: '',
  reopening_date: '',
  is_active: false
};

export default function TermManagementPanel() {
  const [terms, setTerms] = useState([]);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');
  const schoolId = localStorage.getItem('school_id') || 'unknown-school';

  const getPromptStorageKey = (academicYear) => `term_calendar_prompted:${schoolId}:${academicYear}`;

  const getAuthHeaders = () => ({
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const fetchTerms = async () => {
    try {
      setLoading(true);
      const res = await axios.get('/api/school/terms', getAuthHeaders());
      setTerms(res.data.terms || []);
      if (res.data?.suggested_academic_year) {
        setForm((current) => ({ ...current, academic_year: res.data.suggested_academic_year }));
      }
    } catch (err) {
      setMessage('Failed to load academic terms');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTerms();
  }, []);

  useEffect(() => {
    if (loading || terms.length > 0 || importing || !form.academic_year) {
      return;
    }

    const promptStorageKey = getPromptStorageKey(form.academic_year);
    if (localStorage.getItem(promptStorageKey)) {
      return;
    }

    localStorage.setItem(promptStorageKey, 'true');
    const shouldImport = window.confirm(
      'No academic terms are configured for this school yet.\n\nImport the published GES academic calendar now?\n\nYou can edit the dates afterward if your school uses a different schedule.'
    );

    if (shouldImport) {
      handleImportGesCalendar();
    } else {
      setMessage('No term calendar imported yet. You can import the published GES academic calendar below or enter dates manually.');
    }
  }, [form.academic_year, importing, loading, terms.length]);

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
      const payload = err?.response?.data || {};
      setMessage(buildActivationMessage(payload));

      if (payload.error === 'billing_payment_required' && payload.payment_link) {
        if (window.confirm('Payment is required before activation. Open the payment page now?')) {
          window.open(payload.payment_link, '_blank', 'noopener,noreferrer');
        }
      }
    }
  };

  const handleImportGesCalendar = async () => {
    try {
      setImporting(true);
      setMessage('');
      const res = await axios.post(
        '/api/school/terms/import-national-calendar',
        form.academic_year ? { academic_year: form.academic_year } : {},
        getAuthHeaders()
      );
      const { created_count: createdCount, skipped_count: skippedCount } = res.data || {};
      setMessage(
        `${res.data?.message || 'Published GES calendar imported.'}${
          skippedCount ? ` ${skippedCount} term(s) were already present.` : ''
        }`
      );
      if (createdCount) {
        fetchTerms();
      }
    } catch (err) {
      setMessage(err.response?.data?.message || 'Failed to import published GES calendar');
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="mt-10 border-t pt-8">
      <h3 className="text-xl font-bold text-slate-800 mb-4">🗓️ Academic Term Management</h3>
      <p className="text-sm text-slate-600 mb-4">
        Proprietor/Headmaster sets term calendar. Vacation Day maps to term end date; Reopening Date is stored and shown on terminal reports.
      </p>
      <p className="text-sm text-slate-600 mb-4">
        Schools can enter dates manually or import the published GES academic calendar, then edit any school-specific changes.
      </p>

      {!loading && terms.length === 0 && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          No academic terms are set up yet. Import the published GES academic calendar or enter your school's dates manually before billing and term rollover depend on them.
        </div>
      )}

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
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={saving || importing}
              className="px-5 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Term Calendar'}
            </button>
            <button
              type="button"
              onClick={handleImportGesCalendar}
              disabled={saving || importing}
              className="px-5 py-2 bg-slate-800 text-white rounded-lg font-bold hover:bg-slate-900 disabled:opacity-50"
            >
              {importing ? 'Importing...' : 'Import GES Academic Calendar'}
            </button>
          </div>
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
