import React from 'react';
import TrendSparkline, { formatTrendDelta } from './TrendSparkline';

export default function MultiYearAnalyticsView({ availableAcademicYears, multiYearTrendRows, subjectMultiYearTrendRows }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Tracked Years</p>
          <p className="text-2xl font-black text-slate-800">{availableAcademicYears?.length || 0}</p>
        </div>
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 md:col-span-3">
          <p className="text-xs font-semibold uppercase text-blue-700">Available Years</p>
          <p className="mt-1 text-sm font-bold text-blue-900">{availableAcademicYears?.join(', ') || 'No history available'}</p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 p-4">
        <h4 className="mb-3 font-bold text-slate-800">Multi-Year Class Trend Lines</h4>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {multiYearTrendRows.map((row) => {
            const firstPoint = row.points[0];
            const lastPoint = row.points[row.points.length - 1];
            const delta = firstPoint && lastPoint ? Number((lastPoint.average - firstPoint.average).toFixed(2)) : null;

            return (
              <div key={`line-${row.class_name}`} className="rounded-lg border border-slate-100 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-slate-800">{row.class_name}</p>
                    <p className="text-xs text-slate-500">{row.points.length} year points tracked</p>
                  </div>
                  <p className={`text-xs font-bold ${delta !== null && delta < 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {formatTrendDelta(delta)}
                  </p>
                </div>
                <div className="mt-3">
                  <TrendSparkline points={row.points} label={`Trend for ${row.class_name}`} strokeClass="stroke-indigo-600" fillClass="fill-indigo-600" />
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {row.points.map((point) => (
                    <span key={`${row.class_name}-${point.academic_year}`} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">
                      {point.academic_year}: {point.average}%
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 p-4">
        <h4 className="mb-3 font-bold text-slate-800">Multi-Year Class Detail</h4>
        <div className="space-y-4">
          {multiYearTrendRows.length === 0 && (
            <p className="text-sm text-slate-500">No multi-year trend data is available for the selected term.</p>
          )}
          {multiYearTrendRows.map((row) => (
            <div key={`multi-${row.class_name}`} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-bold text-slate-800">{row.class_name}</p>
                <p className="text-xs text-slate-500">{row.points.length} year points</p>
              </div>
              <div className="space-y-2">
                {row.points.map((point) => (
                  <div key={`${row.class_name}-${point.academic_year}`}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-slate-600">{point.academic_year}</span>
                      <span className="font-bold text-slate-800">{point.average}% ({point.count} students)</span>
                    </div>
                    <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                      <div className="h-full rounded-full bg-indigo-600" style={{ width: `${Math.max(3, Math.min(100, point.average || 0))}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 p-4">
        <h4 className="mb-3 font-bold text-slate-800">Per-Subject Multi-Year Trends</h4>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {subjectMultiYearTrendRows.length === 0 && (
            <p className="text-sm text-slate-500">No subject trend history is available for the selected term.</p>
          )}
          {subjectMultiYearTrendRows.map((row) => (
            <div key={`subject-trend-${row.subject}`} className="rounded-lg border border-slate-100 bg-slate-50 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-slate-800">{row.subject}</p>
                  <p className="text-xs text-slate-500">Latest average: {row.latest_average}%</p>
                </div>
                <p className={`text-xs font-bold ${row.delta !== null && row.delta < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                  {formatTrendDelta(row.delta)}
                </p>
              </div>
              <div className="mt-3">
                <TrendSparkline points={row.points} label={`Trend for ${row.subject}`} strokeClass="stroke-emerald-600" fillClass="fill-emerald-600" />
              </div>
              <div className="mt-2 space-y-1">
                {row.points.map((point) => (
                  <div key={`${row.subject}-${point.academic_year}`} className="flex items-center justify-between text-xs text-slate-600">
                    <span>{point.academic_year}</span>
                    <span className="font-bold text-slate-800">{point.average}% ({point.count} entries)</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
