import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { toPng } from 'html-to-image';
import AnalyticsGuidePanel from './AnalyticsGuidePanel';
import MultiYearAnalyticsView from './MultiYearAnalyticsView';
import OverviewPanel from './OverviewPanel';
import PremiumFeatureNotice from '../PremiumFeatureNotice';
import SingleYearAnalyticsView from './SingleYearAnalyticsView';
import useSubscription from '../../hooks/useSubscription';
import useSchoolClasses from '../../hooks/useSchoolClasses';

const TERM_OPTIONS = ['Term 1', 'Term 2', 'Term 3'];

function normalizePresetFilters(filters = {}) {
  return {
    academicTerm: filters.academicTerm || '',
    academicYear: filters.academicYear || '',
    cohortFromClass: filters.cohortFromClass || '',
    cohortToClass: filters.cohortToClass || '',
    analysisMode: filters.analysisMode || 'single-year',
    activeView: filters.activeView || 'visualization',
  };
}

function normalizePresetNameKey(name = '') {
  return String(name || '').trim().toLowerCase();
}

function buildPresetHistoryPreview(savedPresets, defaultPresetName, snapshot) {
  if (!snapshot?.analytics_config) {
    return [];
  }

  const currentPresets = Array.isArray(savedPresets) ? savedPresets : [];
  const snapshotPresets = Array.isArray(snapshot.analytics_config?.presets) ? snapshot.analytics_config.presets : [];
  const currentNames = currentPresets.map((preset) => preset.name).filter(Boolean);
  const snapshotNames = snapshotPresets.map((preset) => preset.name).filter(Boolean);
  const currentNameKeys = new Set(currentNames.map((name) => normalizePresetNameKey(name)));
  const snapshotNameKeys = new Set(snapshotNames.map((name) => normalizePresetNameKey(name)));
  const lines = [];

  if ((snapshot.default_preset_name || '') !== (defaultPresetName || '')) {
    lines.push(`Default preset: ${snapshot.default_preset_name || 'None'} instead of ${defaultPresetName || 'None'}.`);
  }

  const snapshotOnly = snapshotNames.filter((name) => !currentNameKeys.has(normalizePresetNameKey(name)));
  const currentOnly = currentNames.filter((name) => !snapshotNameKeys.has(normalizePresetNameKey(name)));
  if (snapshotOnly.length > 0) {
    lines.push(`Snapshot includes ${snapshotOnly.join(', ')}.`);
  }
  if (currentOnly.length > 0) {
    lines.push(`Current shelf includes ${currentOnly.join(', ')} that would be removed.`);
  }

  const focusPresetName = snapshot.focus_preset_name || snapshot.default_preset_name || snapshotNames[0] || '';
  const snapshotFocusPreset = snapshotPresets.find(
    (preset) => normalizePresetNameKey(preset.name) === normalizePresetNameKey(focusPresetName)
  );
  const currentFocusPreset = currentPresets.find(
    (preset) => normalizePresetNameKey(preset.name) === normalizePresetNameKey(focusPresetName)
  );

  if (snapshotFocusPreset) {
    const currentFilters = normalizePresetFilters(currentFocusPreset?.filters || {});
    const snapshotFilters = normalizePresetFilters(snapshotFocusPreset.filters || {});
    const filterLabels = {
      academicTerm: 'Term',
      academicYear: 'Year',
      cohortFromClass: 'Cohort from',
      cohortToClass: 'Cohort to',
      analysisMode: 'Mode',
      activeView: 'View',
    };

    Object.entries(filterLabels).forEach(([key, label]) => {
      if ((snapshotFilters[key] || '') !== (currentFilters[key] || '')) {
        lines.push(`${label}: ${snapshotFilters[key] || 'None'} instead of ${currentFilters[key] || 'None'} for ${snapshotFocusPreset.name}.`);
      }
    });
  }

  return lines;
}

export default function PerformanceAnalyticsShell({
  title = 'Class Performance Overview',
  defaultView = 'overview',
}) {
  const { hasFeature, loading: planLoading } = useSubscription();
  const canAccessAdvancedAnalytics = hasFeature('advanced_analytics');
  const [academicTerm, setAcademicTerm] = useState('');
  const [academicYear, setAcademicYear] = useState('');
  const [cohortFromClass, setCohortFromClass] = useState('');
  const [cohortToClass, setCohortToClass] = useState('');
  const [analysisMode, setAnalysisMode] = useState('single-year');
  const [activeView, setActiveView] = useState(defaultView === 'visualization' ? 'visualization' : 'overview');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [savedPresets, setSavedPresets] = useState([]);
  const [defaultPresetName, setDefaultPresetName] = useState('');
  const [presetName, setPresetName] = useState('');
  const [presetFeedback, setPresetFeedback] = useState('');
  const [presetHistory, setPresetHistory] = useState([]);
  const [presetHistoryBusyId, setPresetHistoryBusyId] = useState('');
  const [selectedPresetHistoryId, setSelectedPresetHistoryId] = useState('');
  const analyticsRef = useRef(null);
  const { classes: schoolClasses } = useSchoolClasses();

  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  }), []);

  const applyPresetFilters = (filters = {}) => {
    const normalized = normalizePresetFilters(filters);
    setAcademicTerm(normalized.academicTerm);
    setAcademicYear(normalized.academicYear);
    setCohortFromClass(normalized.cohortFromClass);
    setCohortToClass(normalized.cohortToClass);
    setAnalysisMode(normalized.analysisMode);
    setActiveView(normalized.activeView);
    return normalized;
  };

  const syncPresetResponse = (payload) => {
    const presets = Array.isArray(payload?.presets) ? payload.presets : [];
    setSavedPresets(presets);
    setDefaultPresetName(payload?.default_preset_name || '');
    return presets.find((preset) => preset.name === payload?.default_preset_name) || null;
  };

  const fetchPresets = async () => {
    const res = await axios.get('/api/analytics/presets', { headers });
    syncPresetResponse(res.data);
    return res.data;
  };

  const syncPresetHistoryResponse = (payload) => {
    const history = Array.isArray(payload?.history) ? payload.history : [];
    setPresetHistory(history);
    setSelectedPresetHistoryId((currentValue) => {
      if (history.some((item) => item.snapshot_id === currentValue)) {
        return currentValue;
      }
      const preferredItem = history.find((item) => !item.is_current) || history[0];
      return preferredItem?.snapshot_id || '';
    });
    return history;
  };

  const fetchPresetHistory = async () => {
    const res = await axios.get('/api/analytics/presets/history', { headers });
    syncPresetHistoryResponse(res.data);
    return res.data;
  };

  const fetchData = async (overrides = {}) => {
    const selectedFilters = {
      academicTerm: overrides.academicTerm ?? academicTerm,
      academicYear: overrides.academicYear ?? academicYear,
      cohortFromClass: overrides.cohortFromClass ?? cohortFromClass,
      cohortToClass: overrides.cohortToClass ?? cohortToClass,
    };

    setLoading(true);
    setError('');
    try {
      const params = {};
      if (selectedFilters.academicTerm) params.academic_term = selectedFilters.academicTerm;
      if (selectedFilters.academicYear) params.academic_year = selectedFilters.academicYear;
      if (selectedFilters.cohortFromClass) params.cohort_from_class = selectedFilters.cohortFromClass;
      if (selectedFilters.cohortToClass) params.cohort_to_class = selectedFilters.cohortToClass;

      const res = await axios.get('/api/analytics/class-performance', { headers, params });
      setData(res.data);
      if (!selectedFilters.academicTerm && res.data?.academic_term) {
        setAcademicTerm(res.data.academic_term);
      }
      if (!selectedFilters.academicYear && res.data?.academic_year) {
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
    if (!canAccessAdvancedAnalytics) return;
    let cancelled = false;

    const initialize = async () => {
      try {
        const presetPayload = await fetchPresets();
        await fetchPresetHistory();
        if (cancelled) return;
        const defaultPreset = (presetPayload?.presets || []).find(
          (preset) => preset.name === presetPayload?.default_preset_name
        );

        if (defaultPreset?.filters) {
          const filters = applyPresetFilters(defaultPreset.filters);
          setPresetFeedback(`Loaded default preset ${defaultPreset.name}.`);
          await fetchData(filters);
          return;
        }
      } catch {
        if (cancelled) return;
      }

      if (!cancelled) {
        await fetchData();
      }
    };

    initialize();

    return () => {
      cancelled = true;
    };
  }, [canAccessAdvancedAnalytics]);

  const maxAverage = useMemo(() => {
    if (!data?.classes?.length) return 100;
    return Math.max(...data.classes.map((row) => row.average || 0), 100);
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

    return {
      topClass: sorted[0],
      lowestClass: sorted[sorted.length - 1],
      overallAverage,
      maleCount: data.classes.reduce((sum, row) => sum + (row.gender_breakdown?.Male?.count || 0), 0),
      femaleCount: data.classes.reduce((sum, row) => sum + (row.gender_breakdown?.Female?.count || 0), 0),
      otherCount: data.classes.reduce((sum, row) => sum + (row.gender_breakdown?.Other?.count || 0), 0),
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

  const multiYearTrendRows = useMemo(() => data?.multi_year_trends || [], [data]);
  const subjectMultiYearTrendRows = useMemo(() => data?.subject_multi_year_trends || [], [data]);
  const selectedPresetHistoryItem = useMemo(
    () => presetHistory.find((item) => item.snapshot_id === selectedPresetHistoryId) || null,
    [presetHistory, selectedPresetHistoryId]
  );
  const presetHistoryPreview = useMemo(
    () => buildPresetHistoryPreview(savedPresets, defaultPresetName, selectedPresetHistoryItem),
    [savedPresets, defaultPresetName, selectedPresetHistoryItem]
  );

  const buildInsightsCsvRows = () => {
    return [
      ['Section', 'Metric', 'Value', 'Context'],
      ['Summary', 'Academic Term', data?.academic_term || 'N/A', ''],
      ['Summary', 'Academic Year', data?.academic_year || 'N/A', ''],
      ['Summary', 'Comparison Term', data?.compare_term || 'N/A', data?.compare_year || ''],
      ['Summary', 'Previous Year Baseline', data?.same_term_previous_year || 'N/A', ''],
      [],
      ['Class Overview', 'Class', 'Average', 'Students'],
      ...((data?.classes || []).map((row) => ['Class Overview', row.class_name, row.average, row.count])),
      [],
      ['Score Bands', 'Band', 'Count', 'Percentage'],
      ...scoreBandRows.map((row) => ['Score Bands', row.band, row.count, `${row.percentage}%`]),
      [],
      ['Subject Trends', 'Subject', 'Current Avg', `Baseline ${data?.same_term_previous_year || ''}`],
      ...((data?.subject_trends || []).map((row) => ['Subject Trends', row.subject, row.current_average, row.previous_average ?? 'N/A'])),
      [],
      ['Subject Multi-Year', 'Subject', 'Year', 'Average'],
      ...((data?.subject_multi_year_trends || []).flatMap((row) => row.points.map((point) => ['Subject Multi-Year', row.subject, point.academic_year, point.average]))),
      [],
      ['Cohort Migration', 'From -> To', 'Current Avg', 'Previous Avg'],
      ...((data?.cohort_migration_comparisons || []).map((row) => ['Cohort Migration', `${row.from_class} -> ${row.to_class}`, row.current_average, row.previous_average])),
    ];
  };

  const downloadCSV = () => {
    if (!data?.classes?.length) return;
    const csvRows = buildInsightsCsvRows();
    const csvContent = csvRows.map((row) => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `class-performance-${academicTerm || 'current'}-${academicYear || 'year'}.csv`;
    anchor.click();
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
        ${data.same_term_previous_year ? `<p><em>Same-term previous year: ${data.same_term_previous_year}</em></p>` : ''}
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
            ${data.classes.map((row) => `
              <tr>
                <td><strong>${row.class_name}</strong></td>
                <td>${row.average}%</td>
                <td>${row.count}</td>
                <td>${row.prev_average !== null ? `${row.prev_average}%` : 'N/A'}</td>
                <td class="${row.delta !== null ? (row.delta >= 0 ? 'positive' : 'negative') : ''}">
                  ${row.delta !== null ? `${row.delta >= 0 ? '+' : ''}${row.delta}%` : 'N/A'}
                </td>
                <td>${row.gender_breakdown?.Male?.average || 'N/A'}${row.gender_breakdown?.Male?.average ? '%' : ''}</td>
                <td>${row.gender_breakdown?.Male?.count || 0}</td>
                <td>${row.gender_breakdown?.Female?.average || 'N/A'}${row.gender_breakdown?.Female?.average ? '%' : ''}</td>
                <td>${row.gender_breakdown?.Female?.count || 0}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <h2 style="margin-top:24px;color:#0f172a;">Score Distribution</h2>
        <ul>
          ${scoreBandRows.map((row) => `<li>${row.band}: ${row.count} students (${row.percentage}%)</li>`).join('')}
        </ul>
        <h2 style="margin-top:24px;color:#0f172a;">Subject Trends</h2>
        <ul>
          ${(data.subject_trends || []).map((row) => `<li>${row.subject}: ${row.current_average}% ${row.delta !== null && row.delta !== undefined ? `(${row.delta >= 0 ? '+' : ''}${row.delta}% vs baseline)` : ''}</li>`).join('')}
        </ul>
        <h2 style="margin-top:24px;color:#0f172a;">Cohort Migration</h2>
        <ul>
          ${(data.cohort_migration_comparisons || []).map((row) => `<li>${row.from_class} to ${row.to_class}: ${row.previous_average}% -> ${row.current_average}% (${row.delta >= 0 ? '+' : ''}${row.delta}%)</li>`).join('')}
        </ul>
        <h2 style="margin-top:24px;color:#0f172a;">Multi-Year Trends</h2>
        <ul>
          ${(data.multi_year_trends || []).map((row) => `<li>${row.class_name}: ${row.points.map((point) => `${point.academic_year} ${point.average}%`).join(' | ')}</li>`).join('')}
        </ul>
        <h2 style="margin-top:24px;color:#0f172a;">Subject Multi-Year Trends</h2>
        <ul>
          ${(data.subject_multi_year_trends || []).map((row) => `<li>${row.subject}: ${row.points.map((point) => `${point.academic_year} ${point.average}%`).join(' | ')}</li>`).join('')}
        </ul>
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

  const downloadPNG = async () => {
    if (!analyticsRef.current) return;
    const dataUrl = await toPng(analyticsRef.current, { cacheBust: true, pixelRatio: 2 });
    const link = document.createElement('a');
    link.download = `class-performance-${academicTerm || 'current'}-${academicYear || 'year'}.png`;
    link.href = dataUrl;
    link.click();
  };

  const handleSavePreset = async (isDefault = false) => {
    const trimmedName = presetName.trim();
    if (!trimmedName) {
      setPresetFeedback('Enter a preset name before saving.');
      return;
    }

    try {
      const res = await axios.post('/api/analytics/presets', {
        name: trimmedName,
        filters: {
          academicTerm,
          academicYear,
          cohortFromClass,
          cohortToClass,
          analysisMode,
          activeView,
        },
        is_default: isDefault,
      }, { headers });
      syncPresetResponse(res.data);
      await fetchPresetHistory();
      setPresetName('');
      setPresetFeedback(isDefault ? `Saved preset ${trimmedName} as default.` : `Saved preset ${trimmedName}.`);
    } catch (err) {
      setPresetFeedback(err.response?.data?.message || 'Failed to save preset.');
    }
  };

  const handleApplyPreset = async (preset) => {
    const filters = applyPresetFilters(preset.filters || {});
    setPresetFeedback(`Loaded preset ${preset.name}.`);
    await fetchData(filters);
  };

  const handleDeletePreset = async (presetNameToRemove) => {
    try {
      const res = await axios.delete(`/api/analytics/presets/${encodeURIComponent(presetNameToRemove)}`, { headers });
      syncPresetResponse(res.data);
      await fetchPresetHistory();
      setPresetFeedback(`Removed preset ${presetNameToRemove}.`);
    } catch (err) {
      setPresetFeedback(err.response?.data?.message || 'Failed to remove preset.');
    }
  };

  const handleSetDefaultPreset = async (presetNameToSet) => {
    try {
      const res = await axios.put(`/api/analytics/presets/${encodeURIComponent(presetNameToSet)}/default`, {}, { headers });
      syncPresetResponse(res.data);
      await fetchPresetHistory();
      setPresetFeedback(`Set ${presetNameToSet} as the default preset.`);
    } catch (err) {
      setPresetFeedback(err.response?.data?.message || 'Failed to update default preset.');
    }
  };

  const handleRestorePresetHistory = async (snapshotId) => {
    try {
      setPresetHistoryBusyId(snapshotId);
      const res = await axios.post(`/api/analytics/presets/history/${snapshotId}/restore`, {}, { headers });
      syncPresetResponse(res.data);
      await fetchPresetHistory();
      setPresetFeedback('Restored analytics preset history snapshot.');
    } catch (err) {
      setPresetFeedback(err.response?.data?.message || 'Failed to restore preset history.');
    } finally {
      setPresetHistoryBusyId('');
    }
  };

  const handleDownloadPresetHistory = async (snapshotId, fallbackName) => {
    try {
      const res = await axios.get(`/api/analytics/presets/history/${snapshotId}/download`, {
        headers,
        responseType: 'blob',
      });
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = fallbackName || `${snapshotId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setPresetFeedback(err.response?.data?.message || 'Failed to download preset snapshot.');
    }
  };

  const onViewClick = async () => {
    await fetchData();
    setActiveView('visualization');
  };

  if (planLoading) {
    return <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Checking plan access...</div>;
  }

  if (!canAccessAdvancedAnalytics) {
    return (
      <PremiumFeatureNotice
        title={title}
        description="Class performance analytics, saved preset history, and comparison views are available on School OS Plus."
      />
    );
  }

  return (
    <div ref={analyticsRef} className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
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
          <select className="rounded-lg border bg-slate-50 p-2 text-sm" value={academicTerm} onChange={(e) => setAcademicTerm(e.target.value)}>
            <option value="">Select Term</option>
            {TERM_OPTIONS.map((term) => (
              <option key={term} value={term}>{term}</option>
            ))}
          </select>
          <input className="rounded-lg border bg-slate-50 p-2 text-sm" placeholder="Year (e.g., 2025/2026)" value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} />
          <select className="rounded-lg border bg-slate-50 p-2 text-sm" value={cohortFromClass} onChange={(e) => setCohortFromClass(e.target.value)}>
            <option value="">Cohort From Class</option>
            {schoolClasses.map((className) => (
              <option key={`from-${className}`} value={className}>{className}</option>
            ))}
          </select>
          <select className="rounded-lg border bg-slate-50 p-2 text-sm" value={cohortToClass} onChange={(e) => setCohortToClass(e.target.value)}>
            <option value="">Cohort To Class</option>
            {schoolClasses.map((className) => (
              <option key={`to-${className}`} value={className}>{className}</option>
            ))}
          </select>
          <button onClick={onViewClick} className="rounded-lg bg-blue-600 px-4 text-sm font-bold text-white hover:bg-blue-700">View</button>
          {data?.classes?.length > 0 && (
            <>
              <button onClick={downloadCSV} className="rounded-lg bg-green-600 px-3 text-sm font-bold text-white hover:bg-green-700" title="Download analytics CSV">📊 Export CSV</button>
              <button onClick={downloadPDF} className="rounded-lg bg-purple-600 px-3 text-sm font-bold text-white hover:bg-purple-700" title="Print or save analytics PDF">📄 Export PDF</button>
              <button onClick={downloadPNG} className="rounded-lg bg-slate-800 px-3 text-sm font-bold text-white hover:bg-slate-900" title="Export analytics as PNG">🖼 Export PNG</button>
            </>
          )}
        </div>
      </div>

      <AnalyticsGuidePanel
        analysisMode={analysisMode}
        presetName={presetName}
        presetFeedback={presetFeedback}
        savedPresets={savedPresets}
        defaultPresetName={defaultPresetName}
        presetHistory={presetHistory}
        selectedPresetHistoryId={selectedPresetHistoryId}
        presetHistoryPreview={presetHistoryPreview}
        presetHistoryBusyId={presetHistoryBusyId}
        onSetAnalysisMode={setAnalysisMode}
        onPresetNameChange={setPresetName}
        onSavePreset={() => handleSavePreset(false)}
        onSaveDefaultPreset={() => handleSavePreset(true)}
        onApplyPreset={handleApplyPreset}
        onDeletePreset={handleDeletePreset}
        onSetDefaultPreset={handleSetDefaultPreset}
        onSelectPresetHistory={setSelectedPresetHistoryId}
        onRestorePresetHistory={handleRestorePresetHistory}
        onDownloadPresetHistory={handleDownloadPresetHistory}
      />

      {loading && <p className="text-sm text-slate-500">Loading performance data...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && !error && data?.classes?.length > 0 && (
        <div className="mb-4 flex gap-2 border-b border-slate-200 pb-2">
          <button onClick={() => setActiveView('overview')} className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors ${activeView === 'overview' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}>Overview</button>
          <button onClick={() => setActiveView('visualization')} className={`rounded-md px-3 py-1.5 text-sm font-semibold transition-colors ${activeView === 'visualization' ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700 hover:bg-blue-100'}`}>Visualization</button>
        </div>
      )}

      {!loading && !error && data?.classes?.length > 0 && activeView === 'overview' && (
        <OverviewPanel data={data} maxAverage={maxAverage} />
      )}

      {!loading && !error && data?.classes?.length > 0 && activeView === 'visualization' && analysisMode === 'single-year' && (
        <SingleYearAnalyticsView data={data} classStats={classStats} scoreBandRows={scoreBandRows} topSubjectTrend={topSubjectTrend} />
      )}

      {!loading && !error && analysisMode === 'multi-year' && (
        <MultiYearAnalyticsView availableAcademicYears={data?.available_academic_years || []} multiYearTrendRows={multiYearTrendRows} subjectMultiYearTrendRows={subjectMultiYearTrendRows} />
      )}

      {!loading && !error && (!data || data.classes?.length === 0) && (
        <p className="text-sm text-slate-500">No performance data available for the selected term/year.</p>
      )}
    </div>
  );
}
