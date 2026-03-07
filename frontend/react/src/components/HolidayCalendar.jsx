import React, { useEffect, useState } from 'react';
import axios from 'axios';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export default function HolidayCalendar() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({ date: '', name: '', is_holiday: true });

  const getAuthHeaders = () => ({
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const fetchHolidays = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`/api/calendar/holidays?year=${year}&month=${month}`, getAuthHeaders());
      setHolidays(res.data.holidays || []);
    } catch (err) {
      setMessage('Failed to load holidays.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHolidays();
  }, [year, month]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.date) {
      setMessage('Please select a date.');
      return;
    }
    try {
      await axios.post('/api/calendar/holidays', form, getAuthHeaders());
      setForm({ date: '', name: '', is_holiday: true });
      setMessage('Holiday saved.');
      fetchHolidays();
    } catch (err) {
      setMessage('Failed to save holiday.');
    }
  };

  const handleDelete = async (date) => {
    try {
      await axios.delete(`/api/calendar/holidays/${date}`, getAuthHeaders());
      setMessage('Holiday deleted.');
      fetchHolidays();
    } catch (err) {
      setMessage('Failed to delete holiday.');
    }
  };

  return (
    <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">📅 Holiday Calendar</h2>
          <p className="text-sm text-slate-500">Auto-detected national holidays + school overrides.</p>
        </div>
        <div className="flex gap-2">
          <select
            value={month}
            onChange={(e) => setMonth(parseInt(e.target.value, 10))}
            className="p-2 border rounded-lg bg-slate-50"
          >
            {MONTHS.map((label, idx) => (
              <option key={label} value={idx + 1}>{label}</option>
            ))}
          </select>
          <input
            type="number"
            value={year}
            min="2000"
            max="2100"
            onChange={(e) => setYear(parseInt(e.target.value, 10) || now.getFullYear())}
            className="p-2 border rounded-lg bg-slate-50 w-28"
          />
        </div>
      </div>

      {message && (
        <div className="mb-4 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
          {message}
        </div>
      )}

      <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-xs font-bold text-slate-500 mb-1">Date</label>
          <input
            type="date"
            value={form.date}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            className="w-full p-2 border rounded-lg bg-slate-50"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-xs font-bold text-slate-500 mb-1">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full p-2 border rounded-lg bg-slate-50"
            placeholder="e.g. Founders Day"
          />
        </div>
        <div className="flex items-end gap-3">
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_holiday}
              onChange={(e) => setForm({ ...form, is_holiday: e.target.checked })}
            />
            Holiday
          </label>
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg font-bold"
          >
            Save
          </button>
        </div>
      </form>

      <div className="bg-slate-50 border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-100 text-slate-600">
            <tr>
              <th className="p-3 text-left">Date</th>
              <th className="p-3 text-left">Name</th>
              <th className="p-3 text-left">Source</th>
              <th className="p-3 text-left">Status</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {loading && (
              <tr><td className="p-3" colSpan="5">Loading holidays...</td></tr>
            )}
            {!loading && holidays.length === 0 && (
              <tr><td className="p-3" colSpan="5">No holidays for this month.</td></tr>
            )}
            {!loading && holidays.map((holiday) => (
              <tr key={`${holiday.date}-${holiday.name}`} className="bg-white">
                <td className="p-3 font-mono">{holiday.date}</td>
                <td className="p-3">{holiday.name}</td>
                <td className="p-3 capitalize">{holiday.source}</td>
                <td className="p-3">
                  {holiday.source === 'anniversary' ? (
                    <span className="px-2 py-1 text-xs font-bold bg-purple-100 text-purple-700 rounded-full">🎉 Anniversary</span>
                  ) : holiday.is_holiday ? (
                    <span className="px-2 py-1 text-xs font-bold bg-red-100 text-red-700 rounded-full">Holiday</span>
                  ) : (
                    <span className="px-2 py-1 text-xs font-bold bg-green-100 text-green-700 rounded-full">Open Day</span>
                  )}
                </td>
                <td className="p-3 text-right">
                  {(holiday.source === 'custom' || holiday.source === 'override') && (
                    <button
                      onClick={() => handleDelete(holiday.date)}
                      className="text-xs font-bold text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
