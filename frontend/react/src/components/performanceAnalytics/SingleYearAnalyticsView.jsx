import React from 'react';

export default function SingleYearAnalyticsView({ data, classStats, scoreBandRows, topSubjectTrend }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase text-slate-500">Overall Avg</p>
          <p className="text-2xl font-black text-slate-800">{classStats.overallAverage}%</p>
        </div>
        <div className="rounded-lg border border-green-100 bg-green-50 p-3">
          <p className="text-xs font-semibold uppercase text-green-700">Top Class</p>
          <p className="text-sm font-bold text-green-900">{classStats.topClass?.class_name || 'N/A'}</p>
          <p className="text-lg font-black text-green-900">{classStats.topClass?.average || 0}%</p>
        </div>
        <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
          <p className="text-xs font-semibold uppercase text-amber-700">Lowest Class</p>
          <p className="text-sm font-bold text-amber-900">{classStats.lowestClass?.class_name || 'N/A'}</p>
          <p className="text-lg font-black text-amber-900">{classStats.lowestClass?.average || 0}%</p>
        </div>
        <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-3">
          <p className="text-xs font-semibold uppercase text-indigo-700">Classes</p>
          <p className="text-2xl font-black text-indigo-900">{data.classes.length}</p>
        </div>
        <div className="rounded-lg border border-cyan-100 bg-cyan-50 p-3">
          <p className="text-xs font-semibold uppercase text-cyan-700">Best Subject Lift</p>
          <p className="text-sm font-bold text-cyan-900">{topSubjectTrend?.subject || 'N/A'}</p>
          <p className="text-lg font-black text-cyan-900">
            {topSubjectTrend?.delta !== null && topSubjectTrend?.delta !== undefined ? `${topSubjectTrend.delta >= 0 ? '+' : ''}${topSubjectTrend.delta}%` : 'No baseline'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 p-4">
          <h4 className="mb-3 font-bold text-slate-800">Class Performance Ranking</h4>
          <div className="space-y-3">
            {[...data.classes]
              .sort((a, b) => (b.average || 0) - (a.average || 0))
              .map((row) => (
                <div key={`chart-${row.class_name}`}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-semibold text-slate-700">{row.class_name}</span>
                    <span className="font-bold text-slate-800">{row.average}%</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.max(3, Math.min(100, row.average || 0))}%` }} />
                  </div>
                </div>
              ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-4">
          <h4 className="mb-3 font-bold text-slate-800">Gender Distribution</h4>
          <div className="mb-3 space-y-2">
            {[
              { label: 'Male', count: classStats.maleCount, colorTrack: 'bg-blue-100', colorFill: 'bg-blue-600', colorText: 'text-blue-800' },
              { label: 'Female', count: classStats.femaleCount, colorTrack: 'bg-pink-100', colorFill: 'bg-pink-500', colorText: 'text-pink-800' },
              { label: 'Other', count: classStats.otherCount, colorTrack: 'bg-purple-100', colorFill: 'bg-purple-500', colorText: 'text-purple-800' },
            ].map((item) => {
              const total = classStats.maleCount + classStats.femaleCount + classStats.otherCount;
              const pct = total > 0 ? ((item.count / total) * 100).toFixed(1) : 0;
              return (
                <div key={item.label}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className={`font-semibold ${item.colorText}`}>{item.label}</span>
                    <span className="font-bold text-slate-700">{item.count} ({pct}%)</span>
                  </div>
                  <div className={`h-2.5 w-full overflow-hidden rounded-full ${item.colorTrack}`}>
                    <div className={`h-full rounded-full ${item.colorFill}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-200 p-4">
          <h4 className="mb-3 font-bold text-slate-800">Same-Term Year-over-Year Class Comparison</h4>
          <div className="space-y-3">
            {(data.year_over_year_classes || []).map((row) => {
              const current = Number(row.current_average || 0);
              const previous = Number(row.previous_year_average || 0);
              return (
                <div key={`yoy-${row.class_name}`} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-bold text-slate-800">{row.class_name}</p>
                    <p className={`text-xs font-bold ${row.delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {row.delta !== null && row.delta !== undefined ? `${row.delta >= 0 ? '+' : ''}${row.delta}% vs ${data.same_term_previous_year}` : 'No prior-year data'}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-slate-600">Current</span>
                        <span className="font-bold text-slate-800">{current}%</span>
                      </div>
                      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                        <div className="h-full rounded-full bg-blue-600" style={{ width: `${Math.max(3, Math.min(100, current))}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-slate-600">{data.same_term_previous_year}</span>
                        <span className="font-bold text-slate-800">{row.previous_year_average !== null && row.previous_year_average !== undefined ? `${previous}%` : 'N/A'}</span>
                      </div>
                      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                        <div className="h-full rounded-full bg-amber-500" style={{ width: `${Math.max(3, Math.min(100, previous || 0))}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 p-4">
          <h4 className="mb-3 font-bold text-slate-800">Score Distribution Bands</h4>
          <div className="space-y-3">
            {scoreBandRows.map((row) => (
              <div key={row.band}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="font-semibold text-slate-700">{row.band}</span>
                  <span className="font-bold text-slate-800">{row.count} students ({row.percentage}%)</span>
                </div>
                <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className={`h-full rounded-full ${row.band === '80-100' ? 'bg-green-600' : row.band === '70-79' ? 'bg-blue-600' : row.band === '65-69' ? 'bg-amber-500' : row.band === '50-64' ? 'bg-orange-500' : 'bg-red-500'}`} style={{ width: `${row.percentage}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 p-4">
        <h4 className="mb-3 font-bold text-slate-800">Subject Performance Trends</h4>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
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

      <div className="rounded-lg border border-slate-200 p-4">
        <h4 className="mb-3 font-bold text-slate-800">Cohort Migration Comparison</h4>
        <p className="mb-4 text-xs text-slate-500">Tracks the same students as they move from one class level to the next, for example {data?.same_term_previous_year || 'last year'} JHS 1 into {data?.academic_year || 'current year'} JHS 2.</p>
        <div className="space-y-3">
          {(data.cohort_migration_comparisons || []).length === 0 && (
            <p className="text-sm text-slate-500">No cohort migration data is available yet for the selected term and year.</p>
          )}
          {(data.cohort_migration_comparisons || []).map((row) => (
            <div key={`cohort-${row.from_class}-${row.to_class}`} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
              <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-sm font-bold text-slate-800">{row.from_class} {row.from_year} {'->'} {row.to_class} {row.to_year}</p>
                  <p className="text-xs text-slate-500">Matched students: {row.matched_students}</p>
                </div>
                <p className={`text-sm font-bold ${row.delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {row.delta >= 0 ? '+' : ''}{row.delta}% progression
                </p>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-slate-600">{row.from_class} average</span>
                    <span className="font-bold text-slate-800">{row.previous_average}%</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                    <div className="h-full rounded-full bg-amber-500" style={{ width: `${Math.max(3, Math.min(100, row.previous_average || 0))}%` }} />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-slate-600">{row.to_class} average</span>
                    <span className="font-bold text-slate-800">{row.current_average}%</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
                    <div className="h-full rounded-full bg-emerald-600" style={{ width: `${Math.max(3, Math.min(100, row.current_average || 0))}%` }} />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 p-4">
        <h4 className="mb-3 font-bold text-slate-800">Term Trend vs Previous Term</h4>
        <div className="space-y-2">
          {data.classes.map((row) => {
            const hasDelta = row.delta !== null && row.delta !== undefined;
            const deltaValue = hasDelta ? Number(row.delta) : 0;
            const isPositive = deltaValue >= 0;

            return (
              <div key={`trend-${row.class_name}`} className="grid grid-cols-12 items-center gap-2">
                <p className="col-span-4 text-xs font-semibold text-slate-700 md:col-span-3">{row.class_name}</p>
                <div className="col-span-8 h-2 overflow-hidden rounded-full bg-slate-100 md:col-span-6">
                  <div className={`h-full rounded-full ${isPositive ? 'bg-green-500' : 'bg-red-500'}`} style={{ width: `${Math.min(100, Math.max(2, Math.abs(deltaValue) * 10))}%` }} />
                </div>
                <p className={`col-span-12 text-right text-xs font-bold md:col-span-3 ${hasDelta ? (isPositive ? 'text-green-600' : 'text-red-600') : 'text-slate-400'}`}>
                  {hasDelta ? `${isPositive ? '+' : ''}${deltaValue}%` : 'No previous data'}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
