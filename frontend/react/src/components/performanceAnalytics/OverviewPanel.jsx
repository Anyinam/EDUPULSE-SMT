import React from 'react';

export default function OverviewPanel({ data, maxAverage }) {
  return (
    <div className="space-y-3">
      {data.classes.map((row) => (
        <div key={row.class_name} className="border rounded-lg p-3">
          <div className="mb-2 flex items-center justify-between">
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
          <div className="mb-3 h-2 w-full rounded-full bg-slate-100">
            <div
              className="h-2 rounded-full bg-blue-600"
              style={{ width: `${Math.min(100, (row.average / maxAverage) * 100)}%` }}
            />
          </div>
          {row.gender_breakdown && Object.keys(row.gender_breakdown).length > 0 && (
            <div className="mt-2 flex gap-3 border-t border-slate-200 pt-2">
              {row.gender_breakdown.Male && (
                <div className="flex-1 rounded-lg bg-blue-50 p-2">
                  <p className="text-xs font-bold text-blue-800">👨 Male</p>
                  <p className="text-sm font-semibold text-blue-900">{row.gender_breakdown.Male.average}%</p>
                  <p className="text-xs text-blue-700">{row.gender_breakdown.Male.count} students</p>
                </div>
              )}
              {row.gender_breakdown.Female && (
                <div className="flex-1 rounded-lg bg-pink-50 p-2">
                  <p className="text-xs font-bold text-pink-800">👩 Female</p>
                  <p className="text-sm font-semibold text-pink-900">{row.gender_breakdown.Female.average}%</p>
                  <p className="text-xs text-pink-700">{row.gender_breakdown.Female.count} students</p>
                </div>
              )}
              {row.gender_breakdown.Other && (
                <div className="flex-1 rounded-lg bg-purple-50 p-2">
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
  );
}
