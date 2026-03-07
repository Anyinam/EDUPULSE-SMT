import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const TERM_OPTIONS = ['Term 1', 'Term 2', 'Term 3'];

export default function PerformanceAnalytics({ title = 'Class Performance Overview' }) {
  const [academicTerm, setAcademicTerm] = useState('');
  const [academicYear, setAcademicYear] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const headers = useMemo(() => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  }), []);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const params = {};
      if (academicTerm) params.academic_term = academicTerm;
      if (academicYear) params.academic_year = academicYear;

      const res = await axios.get('/api/analytics/class-performance', { headers, params });
      setData(res.data);
      if (!academicTerm && res.data?.academic_term) {
        setAcademicTerm(res.data.academic_term);
      }
      if (!academicYear && res.data?.academic_year) {
        setAcademicYear(res.data.academic_year);
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load performance analytics.');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const maxAverage = useMemo(() => {
    if (!data?.classes?.length) return 100;
    return Math.max(...data.classes.map(c => c.average || 0), 100);
  }, [data]);

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-800">📊 {title}</h3>
          {data?.compare_term && (
            <p className="text-xs text-slate-500">Comparing with {data.compare_term} {data.compare_year}</p>
          )}
        </div>
        <div className="flex gap-2">
          <select
            className="p-2 border rounded-lg bg-slate-50"
            value={academicTerm}
            onChange={(e) => setAcademicTerm(e.target.value)}
          >
            <option value="">Term</option>
            {TERM_OPTIONS.map(term => (
              <option key={term} value={term}>{term}</option>
            ))}
          </select>
          <input
            className="p-2 border rounded-lg bg-slate-50"
            placeholder="Academic Year (e.g., 2025/2026)"
            value={academicYear}
            onChange={(e) => setAcademicYear(e.target.value)}
          />
          <button
            onClick={fetchData}
            className="bg-blue-600 text-white px-4 rounded-lg text-sm font-bold hover:bg-blue-700"
          >
            View
          </button>
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">Loading performance data...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && data?.classes?.length > 0 && (
        <div className="space-y-3">
          {data.classes.map((row) => (
            <div key={row.class_name} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="font-semibold text-slate-800">{row.class_name}</p>
                  <p className="text-xs text-slate-500">{row.count} students</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-slate-800">{row.average}%</p>
                  {row.delta !== null && (
                    <p className={`text-xs font-bold ${row.delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {row.delta >= 0 ? '+' : ''}{row.delta}% vs previous
                    </p>
                  )}
                </div>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-blue-600"
                  style={{ width: `${Math.min(100, (row.average / maxAverage) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && (!data || data.classes?.length === 0) && (
        <p className="text-sm text-slate-500">No performance data available for the selected term/year.</p>
      )}
    </div>
  );
}
