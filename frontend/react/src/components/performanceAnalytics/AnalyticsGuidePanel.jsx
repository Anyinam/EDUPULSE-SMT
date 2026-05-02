import React from 'react';

export default function AnalyticsGuidePanel({
  analysisMode,
  presetName,
  presetFeedback,
  savedPresets,
  defaultPresetName,
  presetHistory,
  selectedPresetHistoryId,
  presetHistoryPreview,
  presetHistoryBusyId,
  onSetAnalysisMode,
  onPresetNameChange,
  onSavePreset,
  onSaveDefaultPreset,
  onApplyPreset,
  onDeletePreset,
  onSetDefaultPreset,
  onSelectPresetHistory,
  onRestorePresetHistory,
  onDownloadPresetHistory,
}) {
  const historyActionLabels = {
    save: 'Saved',
    set_default: 'Default updated',
    delete: 'Removed',
    restore: 'Restored',
  };

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

      <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-bold text-slate-800">Preset History</p>
            <p className="mt-1 text-xs text-slate-500">Every save, default change, delete, and restore keeps a recoverable preset shelf snapshot.</p>
          </div>
          <span className="rounded-full bg-slate-900 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-white">
            {presetHistory.length} snapshot{presetHistory.length === 1 ? '' : 's'}
          </span>
        </div>

        {presetHistory.length === 0 ? (
          <p className="mt-3 text-xs text-slate-500">No preset history yet.</p>
        ) : (
          <>
            <div className="mt-3 rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-slate-600">Snapshot Preview</p>
              {presetHistoryPreview.length === 0 ? (
                <p className="mt-2 text-xs text-slate-500">This snapshot matches the current preset shelf.</p>
              ) : (
                <div className="mt-2 space-y-1">
                  {presetHistoryPreview.map((line) => (
                    <p key={line} className="text-xs text-slate-600">{line}</p>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-3 space-y-2">
              {presetHistory.map((item) => {
                const isSelected = item.snapshot_id === selectedPresetHistoryId;
                return (
                  <div
                    key={item.snapshot_id}
                    className={`rounded-lg border p-3 ${isSelected ? 'border-blue-300 bg-blue-50/40' : 'border-slate-200 bg-white'}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-bold text-slate-800">{item.focus_preset_name || item.default_preset_name || 'Preset shelf snapshot'}</p>
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-slate-700">
                            {historyActionLabels[item.action] || item.action}
                          </span>
                          {item.is_current && (
                            <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-emerald-800">Current</span>
                          )}
                          {item.default_preset_name && (
                            <span className="rounded-full bg-blue-100 px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-blue-800">Default: {item.default_preset_name}</span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.preset_count} preset{item.preset_count === 1 ? '' : 's'}
                          {item.actor_name ? ` • by ${item.actor_name}` : ''}
                          {item.created_at ? ` • ${new Date(item.created_at).toLocaleString()}` : ''}
                        </p>
                        {Array.isArray(item.preset_names) && item.preset_names.length > 0 && (
                          <p className="mt-1 text-xs text-slate-500">Includes: {item.preset_names.join(', ')}</p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => onSelectPresetHistory(item.snapshot_id)}
                          className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
                        >
                          {isSelected ? 'Previewing' : 'Preview Diff'}
                        </button>
                        <button
                          onClick={() => onDownloadPresetHistory(item.snapshot_id, `${item.focus_preset_name || item.default_preset_name || item.snapshot_id}.json`)}
                          className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
                        >
                          Download
                        </button>
                        <button
                          onClick={() => onRestorePresetHistory(item.snapshot_id)}
                          disabled={item.is_current || presetHistoryBusyId === item.snapshot_id}
                          className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {presetHistoryBusyId === item.snapshot_id ? 'Restoring...' : item.is_current ? 'Current' : 'Restore Snapshot'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
