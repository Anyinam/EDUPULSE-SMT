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

  const downloadCSV = () => {
    if (!data?.classes?.length) return;
    
    const csvRows = [
      ['Class', 'Average (%)', 'Students', 'Previous Average (%)', 'Change (%)', 'Male Avg (%)', 'Male Count', 'Female Avg (%)', 'Female Count'],
      ...data.classes.map(c => [
        c.class_name,
        c.average,
        c.count,
        c.prev_average || 'N/A',
        c.delta !== null ? c.delta : 'N/A',
        c.gender_breakdown?.Male?.average || 'N/A',
        c.gender_breakdown?.Male?.count || 0,
        c.gender_breakdown?.Female?.average || 'N/A',
        c.gender_breakdown?.Female?.count || 0
      ])
    ];
    
    const csvContent = csvRows.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `class-performance-${academicTerm || 'current'}-${academicYear || 'year'}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadPDF = () => {
    if (!data?.classes?.length) return;
    
    const printWindow = window.open('', '', 'width=800,height=600');
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Class Performance Report</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; }
          h1 { color: #1e3a8a; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; }
          th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
          th { background-color: #1e3a8a; color: white; }
          tr:nth-child(even) { background-color: #f9fafb; }
          .positive { color: green; font-weight: bold; }
          .negative { color: red; font-weight: bold; }
        </style>
      </head>
      <body>
        <h1>📊 ${title}</h1>
        <p><strong>Academic Term:</strong> ${data.academic_term || 'N/A'} | <strong>Year:</strong> ${data.academic_year || 'N/A'}</p>
        ${data.compare_term ? `<p><em>Compared with ${data.compare_term} ${data.compare_year}</em></p>` : ''}
        <table>
          <thead>
            <tr>
              <th>Class</th>
              <th>Average (%)</th>
              <th>Students</th>
              <th>Previous Average (%)</th>
              <th>Change (%)</th>
              <th colspan="2">Male</th>
              <th colspan="2">Female</th>
            </tr>
            <tr>
              <th colspan="5"></th>
              <th>Avg %</th>
              <th>Count</th>
              <th>Avg %</th>
              <th>Count</th>
            </tr>
          </thead>
          <tbody>
            ${data.classes.map(c => `
              <tr>
                <td><strong>${c.class_name}</strong></td>
                <td>${c.average}%</td>
                <td>${c.count}</td>
                <td>${c.prev_average !== null ? c.prev_average + '%' : 'N/A'}</td>
                <td class="${c.delta !== null ? (c.delta >= 0 ? 'positive' : 'negative') : ''}">
                  ${c.delta !== null ? (c.delta >= 0 ? '+' : '') + c.delta + '%' : 'N/A'}
                </td>
                <td>${c.gender_breakdown?.Male?.average || 'N/A'}${c.gender_breakdown?.Male?.average ? '%' : ''}</td>
                <td>${c.gender_breakdown?.Male?.count || 0}</td>
                <td>${c.gender_breakdown?.Female?.average || 'N/A'}${c.gender_breakdown?.Female?.average ? '%' : ''}</td>
                <td>${c.gender_breakdown?.Female?.count || 0}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <p style="margin-top: 30px; color: #64748b; font-size: 12px;">
          Generated on ${new Date().toLocaleString()} | EduPulse SMT
        </p>
      </body>
      </html>
    `;
    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);
  };

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-800">📊 {title}</h3>
          {data?.compare_term && (
            <p className="text-xs text-slate-500">Comparing with {data.compare_term} {data.compare_year}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="p-2 border rounded-lg bg-slate-50 text-sm"
            value={academicTerm}
            onChange={(e) => setAcademicTerm(e.target.value)}
          >
            <option value="">Select Term</option>
            {TERM_OPTIONS.map(term => (
              <option key={term} value={term}>{term}</option>
            ))}
          </select>
          <input
            className="p-2 border rounded-lg bg-slate-50 text-sm"
            placeholder="Year (e.g., 2025/2026)"
            value={academicYear}
            onChange={(e) => setAcademicYear(e.target.value)}
          />
          <button
            onClick={fetchData}
            className="bg-blue-600 text-white px-4 rounded-lg text-sm font-bold hover:bg-blue-700"
          >
            View
          </button>
          {data?.classes?.length > 0 && (
            <>
              <button
                onClick={downloadCSV}
                className="bg-green-600 text-white px-3 rounded-lg text-sm font-bold hover:bg-green-700"
                title="Download CSV"
              >
                📊 CSV
              </button>
              <button
                onClick={downloadPDF}
                className="bg-purple-600 text-white px-3 rounded-lg text-sm font-bold hover:bg-purple-700"
                title="Print/Save as PDF"
              >
                📄 PDF
              </button>
            </>
          )}
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
              <div className="w-full bg-slate-100 rounded-full h-2 mb-3">
                <div
                  className="h-2 rounded-full bg-blue-600"
                  style={{ width: `${Math.min(100, (row.average / maxAverage) * 100)}%` }}
                />
              </div>
              {row.gender_breakdown && Object.keys(row.gender_breakdown).length > 0 && (
                <div className="flex gap-3 mt-2 pt-2 border-t border-slate-200">
                  {row.gender_breakdown.Male && (
                    <div className="flex-1 bg-blue-50 rounded-lg p-2">
                      <p className="text-xs font-bold text-blue-800">👨 Male</p>
                      <p className="text-sm font-semibold text-blue-900">{row.gender_breakdown.Male.average}%</p>
                      <p className="text-xs text-blue-700">{row.gender_breakdown.Male.count} students</p>
                    </div>
                  )}
                  {row.gender_breakdown.Female && (
                    <div className="flex-1 bg-pink-50 rounded-lg p-2">
                      <p className="text-xs font-bold text-pink-800">👩 Female</p>
                      <p className="text-sm font-semibold text-pink-900">{row.gender_breakdown.Female.average}%</p>
                      <p className="text-xs text-pink-700">{row.gender_breakdown.Female.count} students</p>
                    </div>
                  )}
                  {row.gender_breakdown.Other && (
                    <div className="flex-1 bg-purple-50 rounded-lg p-2">
                      <p className="text-xs font-bold text-purple-800">Other</p>
                      <p className="text-sm font-semibold text-purple-900">{row.gender_breakdown.Other.average}%</p>
                      <p className="text-xs text-purple-700">{row.gender_breakdown.Other.count} students</p>
                    </div>
                  )}
                </div>
              )}
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
