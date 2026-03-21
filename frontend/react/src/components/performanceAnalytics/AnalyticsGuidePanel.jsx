import React from 'react';

export default function AnalyticsGuidePanel({
  analysisMode,
  presetName,
  presetFeedback,
  savedPresets,
  defaultPresetName,
  onSetAnalysisMode,
  onPresetNameChange,
  onSavePreset,
  onSaveDefaultPreset,
  onApplyPreset,
  onDeletePreset,
  onSetDefaultPreset,
}) {
  return (
    <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-bold text-slate-800">Analytics Guide</p>
          <p className="mt-1 text-xs text-slate-600">Use single-year mode for current-term diagnostics and multi-year mode to compare class performance across academic years for the same term.</p>
        </div>
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
          <button
            onClick={() => onSetAnalysisMode('single-year')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold ${analysisMode === 'single-year' ? 'bg-slate-800 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
          >
            Single-Year
          </button>
          <button
            onClick={() => onSetAnalysisMode('multi-year')}
            className={`px-3 py-1.5 rounded-md text-sm font-semibold ${analysisMode === 'multi-year' ? 'bg-slate-800 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
          >
            Multi-Year
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-slate-600 md:grid-cols-3">
        <p><span className="font-bold text-slate-800">Year-over-year:</span> same class compared against the same term in the previous academic year.</p>
        <p><span className="font-bold text-slate-800">Cohort migration:</span> matched students tracked from one class to the next class level.</p>
        <p><span className="font-bold text-slate-800">Score bands:</span> distribution of students across performance ranges.</p>
      </div>

      <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-bold text-slate-800">Saved Presets</p>
            <p className="mt-1 text-xs text-slate-500">Save term, year, cohort filters, and view mode to reload the same analytics view quickly.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
              placeholder="Preset name"
              value={presetName}
              onChange={(e) => onPresetNameChange(e.target.value)}
            />
            <button
              onClick={onSavePreset}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-bold text-white hover:bg-slate-900"
            >
              Save Preset
            </button>
            <button
              onClick={onSaveDefaultPreset}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white hover:bg-blue-700"
            >
              Save as Default
            </button>
          </div>
        </div>

        {presetFeedback && (
          <p className="mt-3 text-xs font-semibold text-slate-600">{presetFeedback}</p>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          {savedPresets.length === 0 && (
            <p className="text-xs text-slate-500">No saved presets yet.</p>
          )}
          {savedPresets.map((preset) => {
            const isDefault = preset.name === defaultPresetName;
            return (
              <div key={preset.name} className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-1 py-1">
                <button
                  onClick={() => onApplyPreset(preset)}
                  className="rounded-full px-3 py-1 text-xs font-bold text-slate-700 hover:bg-white"
                >
                  {preset.name}
                </button>
                <button
                  onClick={() => onSetDefaultPreset(preset.name)}
                  className={`rounded-full px-2 py-1 text-xs font-bold ${isDefault ? 'bg-blue-600 text-white' : 'text-blue-700 hover:bg-blue-50'}`}
                  aria-label={isDefault ? `${preset.name} is default preset` : `Set ${preset.name} as default preset`}
                >
                  {isDefault ? 'Default' : 'Make Default'}
                </button>
                <button
                  onClick={() => onDeletePreset(preset.name)}
                  className="rounded-full px-2 py-1 text-xs font-bold text-red-600 hover:bg-red-50"
                  aria-label={`Delete preset ${preset.name}`}
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
