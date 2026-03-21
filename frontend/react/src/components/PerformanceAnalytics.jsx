import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const TERM_OPTIONS = ['Term 1', 'Term 2', 'Term 3'];

export default function PerformanceAnalytics({
  title = 'Class Performance Overview',
  defaultView = 'overview',
}) {
  const [academicTerm, setAcademicTerm] = useState('');
  const [academicYear, setAcademicYear] = useState('');
  const [activeView, setActiveView] = useState(defaultView === 'visualization' ? 'visualization' : 'overview');
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

  const classStats = useMemo(() => {
    if (!data?.classes?.length) {
      return {
        topClass: null,
        lowestClass: null,
        overallAverage: 0,
        maleCount: 0,
        femaleCount: 0,
        otherCount: 0,
      };
    }

    const sorted = [...data.classes].sort((a, b) => (b.average || 0) - (a.average || 0));
    const overallAverage = (
      data.classes.reduce((sum, row) => sum + (row.average || 0), 0) / data.classes.length
    ).toFixed(2);

    const maleCount = data.classes.reduce(
      (sum, row) => sum + (row.gender_breakdown?.Male?.count || 0),
      0
    );
    const femaleCount = data.classes.reduce(
      (sum, row) => sum + (row.gender_breakdown?.Female?.count || 0),
      0
    );
    const otherCount = data.classes.reduce(
      (sum, row) => sum + (row.gender_breakdown?.Other?.count || 0),
      0
    );

    return {
      topClass: sorted[0],
      lowestClass: sorted[sorted.length - 1],
      overallAverage,
      maleCount,
      femaleCount,
      otherCount,
    };
  }, [data]);

  const scoreBandRows = useMemo(() => {
    const bands = data?.score_bands || {};
    const total = Object.values(bands).reduce((sum, count) => sum + Number(count || 0), 0);
    return ['80-100', '70-79', '65-69', '50-64', '0-49'].map((band) => ({
      band,
      count: Number(bands[band] || 0),
      percentage: total > 0 ? ((Number(bands[band] || 0) / total) * 100).toFixed(1) : '0.0',
    }));
  }, [data]);

  const topSubjectTrend = useMemo(() => {
    if (!data?.subject_trends?.length) return null;
    return [...data.subject_trends].sort((a, b) => (b.delta || -999) - (a.delta || -999))[0];
  }, [data]);

  const onViewClick = async () => {
    await fetchData();
    setActiveView('visualization');
  };

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
          {data?.same_term_previous_year && (
            <p className="text-xs text-slate-500">Year-on-year cohort benchmark against {data.same_term_previous_year}</p>
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
            onClick={onViewClick}
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
        <div className="mb-4 flex gap-2 border-b border-slate-200 pb-2">
          <button
            onClick={() => setActiveView('overview')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold transition-colors ${
              activeView === 'overview'
                ? 'bg-slate-800 text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveView('visualization')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold transition-colors ${
              activeView === 'visualization'
                ? 'bg-blue-600 text-white'
                : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
            }`}
          >
            Visualization
          </button>
        </div>
      )}

      {!loading && !error && data?.classes?.length > 0 && activeView === 'overview' && (
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

      {!loading && !error && data?.classes?.length > 0 && activeView === 'visualization' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
              <p className="text-xs font-semibold text-slate-500 uppercase">Overall Avg</p>
              <p className="text-2xl font-black text-slate-800">{classStats.overallAverage}%</p>
            </div>
            <div className="bg-green-50 border border-green-100 rounded-lg p-3">
              <p className="text-xs font-semibold text-green-700 uppercase">Top Class</p>
              <p className="text-sm font-bold text-green-900">{classStats.topClass?.class_name || 'N/A'}</p>
              <p className="text-lg font-black text-green-900">{classStats.topClass?.average || 0}%</p>
            </div>
            <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
              <p className="text-xs font-semibold text-amber-700 uppercase">Lowest Class</p>
              <p className="text-sm font-bold text-amber-900">{classStats.lowestClass?.class_name || 'N/A'}</p>
              <p className="text-lg font-black text-amber-900">{classStats.lowestClass?.average || 0}%</p>
            </div>
            <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
              <p className="text-xs font-semibold text-indigo-700 uppercase">Classes</p>
              <p className="text-2xl font-black text-indigo-900">{data.classes.length}</p>
            </div>
            <div className="bg-cyan-50 border border-cyan-100 rounded-lg p-3">
              <p className="text-xs font-semibold text-cyan-700 uppercase">Best Subject Lift</p>
              <p className="text-sm font-bold text-cyan-900">{topSubjectTrend?.subject || 'N/A'}</p>
              <p className="text-lg font-black text-cyan-900">
                {topSubjectTrend?.delta !== null && topSubjectTrend?.delta !== undefined ? `${topSubjectTrend.delta >= 0 ? '+' : ''}${topSubjectTrend.delta}%` : 'No baseline'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="border border-slate-200 rounded-lg p-4">
              <h4 className="font-bold text-slate-800 mb-3">Class Performance Ranking</h4>
              <div className="space-y-3">
                {[...data.classes]
                  .sort((a, b) => (b.average || 0) - (a.average || 0))
                  .map((row) => (
                    <div key={`chart-${row.class_name}`}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-semibold text-slate-700">{row.class_name}</span>
                        <span className="font-bold text-slate-800">{row.average}%</span>
                      </div>
                      <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-600 rounded-full"
                          style={{ width: `${Math.max(3, Math.min(100, row.average || 0))}%` }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div className="border border-slate-200 rounded-lg p-4">
              <h4 className="font-bold text-slate-800 mb-3">Gender Distribution</h4>
              <div className="space-y-2 mb-3">
                {[
                  {
                    label: 'Male',
                    count: classStats.maleCount,
                    colorTrack: 'bg-blue-100',
                    colorFill: 'bg-blue-600',
                    colorText: 'text-blue-800',
                  },
                  {
                    label: 'Female',
                    count: classStats.femaleCount,
                    colorTrack: 'bg-pink-100',
                    colorFill: 'bg-pink-500',
                    colorText: 'text-pink-800',
                  },
                  {
                    label: 'Other',
                    count: classStats.otherCount,
                    colorTrack: 'bg-purple-100',
                    colorFill: 'bg-purple-500',
                    colorText: 'text-purple-800',
                  },
                ].map((item) => {
                  const total = classStats.maleCount + classStats.femaleCount + classStats.otherCount;
                  const pct = total > 0 ? ((item.count / total) * 100).toFixed(1) : 0;

                  return (
                    <div key={item.label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className={`font-semibold ${item.colorText}`}>{item.label}</span>
                        <span className="font-bold text-slate-700">{item.count} ({pct}%)</span>
                      </div>
                      <div className={`w-full h-2.5 rounded-full overflow-hidden ${item.colorTrack}`}>
                        <div className={`h-full rounded-full ${item.colorFill}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div className="border border-slate-200 rounded-lg p-4">
              <h4 className="font-bold text-slate-800 mb-3">Same-Term Year-over-Year Class Comparison</h4>
              <div className="space-y-3">
                {(data.year_over_year_classes || []).map((row) => {
                  const current = Number(row.current_average || 0);
                  const previous = Number(row.previous_year_average || 0);
                  return (
                    <div key={`yoy-${row.class_name}`} className="border border-slate-100 rounded-lg p-3 bg-slate-50">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-bold text-slate-800">{row.class_name}</p>
                        <p className={`text-xs font-bold ${row.delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {row.delta !== null && row.delta !== undefined ? `${row.delta >= 0 ? '+' : ''}${row.delta}% vs ${data.same_term_previous_year}` : 'No prior-year data'}
                        </p>
                      </div>
                      <div className="space-y-2">
                        <div>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-600">Current</span>
                            <span className="font-bold text-slate-800">{current}%</span>
                          </div>
                          <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-600 rounded-full" style={{ width: `${Math.max(3, Math.min(100, current))}%` }} />
                          </div>
                        </div>
                        <div>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-600">{data.same_term_previous_year}</span>
                            <span className="font-bold text-slate-800">{row.previous_year_average !== null && row.previous_year_average !== undefined ? `${previous}%` : 'N/A'}</span>
                          </div>
                          <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 rounded-full" style={{ width: `${Math.max(3, Math.min(100, previous || 0))}%` }} />
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="border border-slate-200 rounded-lg p-4">
              <h4 className="font-bold text-slate-800 mb-3">Score Distribution Bands</h4>
              <div className="space-y-3">
                {scoreBandRows.map((row) => (
                  <div key={row.band}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-semibold text-slate-700">{row.band}</span>
                      <span className="font-bold text-slate-800">{row.count} students ({row.percentage}%)</span>
                    </div>
                    <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${row.band === '80-100' ? 'bg-green-600' : row.band === '70-79' ? 'bg-blue-600' : row.band === '65-69' ? 'bg-amber-500' : row.band === '50-64' ? 'bg-orange-500' : 'bg-red-500'}`}
                        style={{ width: `${row.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="border border-slate-200 rounded-lg p-4">
            <h4 className="font-bold text-slate-800 mb-3">Subject Performance Trends</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {(data.subject_trends || []).map((subject) => (
                <div key={subject.subject} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-bold text-slate-800">{subject.subject}</p>
                    <span className={`text-xs font-bold ${subject.delta !== null && subject.delta !== undefined ? (subject.delta >= 0 ? 'text-green-600' : 'text-red-600') : 'text-slate-400'}`}>
                      {subject.delta !== null && subject.delta !== undefined ? `${subject.delta >= 0 ? '+' : ''}${subject.delta}%` : 'New'}
                    </span>
                  </div>
                  <div className="mt-3 space-y-1 text-xs text-slate-600">
                    <p>Current average: <span className="font-bold text-slate-800">{subject.current_average}%</span></p>
                    <p>{data.same_term_previous_year}: <span className="font-bold text-slate-800">{subject.previous_average !== null && subject.previous_average !== undefined ? `${subject.previous_average}%` : 'N/A'}</span></p>
                    <p>Entries analysed: <span className="font-bold text-slate-800">{subject.count}</span></p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-slate-200 rounded-lg p-4">
            <h4 className="font-bold text-slate-800 mb-3">Cohort Migration Comparison</h4>
            <p className="text-xs text-slate-500 mb-4">Tracks the same students as they move from one class level to the next, for example {data?.same_term_previous_year || 'last year'} JHS 1 into {data?.academic_year || 'current year'} JHS 2.</p>
            <div className="space-y-3">
              {(data.cohort_migration_comparisons || []).length === 0 && (
                <p className="text-sm text-slate-500">No cohort migration data is available yet for the selected term and year.</p>
              )}
              {(data.cohort_migration_comparisons || []).map((row) => (
                <div key={`cohort-${row.from_class}-${row.to_class}`} className="border border-slate-100 rounded-lg p-3 bg-slate-50">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-3">
                    <div>
                      <p className="text-sm font-bold text-slate-800">{row.from_class} {row.from_year} {'->'} {row.to_class} {row.to_year}</p>
                      <p className="text-xs text-slate-500">Matched students: {row.matched_students}</p>
                    </div>
                    <p className={`text-sm font-bold ${row.delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {row.delta >= 0 ? '+' : ''}{row.delta}% progression
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-600">{row.from_class} average</span>
                        <span className="font-bold text-slate-800">{row.previous_average}%</span>
                      </div>
                      <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-amber-500 rounded-full" style={{ width: `${Math.max(3, Math.min(100, row.previous_average || 0))}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-600">{row.to_class} average</span>
                        <span className="font-bold text-slate-800">{row.current_average}%</span>
                      </div>
                      <div className="w-full h-2.5 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-600 rounded-full" style={{ width: `${Math.max(3, Math.min(100, row.current_average || 0))}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-slate-200 rounded-lg p-4">
            <h4 className="font-bold text-slate-800 mb-3">Term Trend vs Previous Term</h4>
            <div className="space-y-2">
              {data.classes.map((row) => {
                const hasDelta = row.delta !== null && row.delta !== undefined;
                const deltaValue = hasDelta ? Number(row.delta) : 0;
                const isPositive = deltaValue >= 0;

                return (
                  <div key={`trend-${row.class_name}`} className="grid grid-cols-12 gap-2 items-center">
                    <p className="col-span-4 md:col-span-3 text-xs font-semibold text-slate-700">{row.class_name}</p>
                    <div className="col-span-8 md:col-span-6 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
                        style={{
                          width: `${Math.min(100, Math.max(2, Math.abs(deltaValue) * 10))}%`,
                        }}
                      />
                    </div>
                    <p
                      className={`col-span-12 md:col-span-3 text-xs font-bold text-right ${
                        hasDelta ? (isPositive ? 'text-green-600' : 'text-red-600') : 'text-slate-400'
                      }`}
                    >
                      {hasDelta ? `${isPositive ? '+' : ''}${deltaValue}%` : 'No previous data'}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {!loading && !error && (!data || data.classes?.length === 0) && (
        <p className="text-sm text-slate-500">No performance data available for the selected term/year.</p>
      )}
    </div>
  );
}
