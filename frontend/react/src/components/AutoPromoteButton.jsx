import React, { useState } from 'react';
import { AlertCircle, Check, Loader, Zap } from 'lucide-react';
import axios from 'axios';

const CLASS_OPTIONS = [
  'Nursery', 'KG', 'Class 1', 'Class 2', 'Class 3', 'Class 4', 'Class 5', 'Class 6',
  'JHS 1', 'JHS 2', 'JHS 3'
];

const NEXT_CLASS_MAP = {
  'Nursery': 'KG',
  'KG': 'Class 1',
  'Class 1': 'Class 2',
  'Class 2': 'Class 3',
  'Class 3': 'Class 4',
  'Class 4': 'Class 5',
  'Class 5': 'Class 6',
  'Class 6': 'JHS 1',
  'JHS 1': 'JHS 2',
  'JHS 2': 'JHS 3',
  'JHS 3': 'Alumni'
};

const AutoPromoteButton = () => {
  const [showModal, setShowModal] = useState(false);
  const [selectedClass, setSelectedClass] = useState('JHS 3');
  const [nextClass, setNextClass] = useState(NEXT_CLASS_MAP['JHS 3']);
  const [dryRun, setDryRun] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleClassChange = (cls) => {
    setSelectedClass(cls);
    setNextClass(NEXT_CLASS_MAP[cls] || 'Alumni');
  };

  const handleAutoPromote = async (isDryRun) => {
    if (!selectedClass || !nextClass) {
      alert('Please select both current and next class');
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const schoolId = localStorage.getItem('school_id');

      const response = await axios.post(
        '/api/admissions/auto-promote',
        {
          class_name: selectedClass,
          new_class: nextClass,
          dry_run: isDryRun
        },
        { 
          headers: { 
            'Authorization': `Bearer ${token}`,
            'X-School-ID': schoolId
          } 
        }
      );

      setResult({
        success: true,
        message: response.data.message,
        promoted_count: response.data.promoted_count,
        not_promoted_count: response.data.not_promoted_count,
        promoted_students: response.data.promoted_students || [],
        not_promoted_students: response.data.not_promoted_students || [],
        isDryRun: isDryRun
      });

    } catch (error) {
      setResult({
        success: false,
        message: error.response?.data?.message || 'Failed to execute auto-promotion',
        error: error.response?.data?.error
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Main Button */}
      <button
        onClick={() => {
          setResult(null);
          setShowModal(true);
        }}
        className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 font-bold flex items-center gap-2"
      >
        <Zap size={18} />
        Auto-Promote by Performance
      </button>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-80 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto text-slate-900">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-slate-800">⚡ Auto-Promote Students by Performance</h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            {!result ? (
              <>
                {/* Class Selection */}
                <div className="bg-blue-50 p-4 rounded-lg mb-6 border border-blue-200">
                  <p className="text-sm text-blue-900 mb-4 font-medium">
                    Select which class to promote. Students will be evaluated based on their average marks and promotion thresholds.
                  </p>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">
                        Current Class
                      </label>
                      <select
                        value={selectedClass}
                        onChange={(e) => handleClassChange(e.target.value)}
                        className="w-full p-3 border rounded-lg bg-white font-medium text-slate-900"
                      >
                        {CLASS_OPTIONS.map(cls => (
                          <option key={cls} value={cls}>{cls}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">
                        Promote To
                      </label>
                      <input
                        type="text"
                        value={nextClass}
                        onChange={(e) => setNextClass(e.target.value)}
                        className="w-full p-3 border rounded-lg bg-white font-medium text-slate-900"
                        placeholder="e.g., JHS 2"
                      />
                    </div>
                  </div>
                </div>

                {/* Info Box */}
                <div className="bg-amber-50 p-4 rounded-lg mb-6 border border-amber-200">
                  <p className="text-sm text-amber-900 font-medium">
                    📊 How it works:
                  </p>
                  <ul className="text-sm text-amber-800 mt-2 space-y-1 list-disc list-inside">
                    <li>System calculates average marks for each active student in {selectedClass}</li>
                    <li>Compares against the configured performance threshold</li>
                    <li>Students above threshold are automatically promoted to {nextClass}</li>
                    <li>If no threshold is set, all active students are promoted</li>
                  </ul>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-4">
                  <button
                    onClick={() => handleAutoPromote(true)}
                    disabled={loading}
                    className="flex-1 p-3 bg-slate-200 text-slate-800 rounded-lg hover:bg-slate-300 font-bold disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <>
                        <Loader size={18} className="animate-spin" />
                        Processing...
                      </>
                    ) : (
                      '🔍 Preview (Dry Run)'
                    )}
                  </button>

                  <button
                    onClick={() => handleAutoPromote(false)}
                    disabled={loading}
                    className="flex-1 p-3 bg-amber-600 text-white rounded-lg hover:bg-amber-700 font-bold disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {loading ? (
                      <>
                        <Loader size={18} className="animate-spin" />
                        Executing...
                      </>
                    ) : (
                      '✅ Execute Promotion'
                    )}
                  </button>
                </div>
              </>
            ) : (
              <>
                {/* Results */}
                <div className={`p-4 rounded-lg mb-4 flex items-start gap-3 border ${
                  result.success 
                    ? 'bg-green-50 border-green-200' 
                    : 'bg-red-50 border-red-200'
                }`}>
                  {result.success ? (
                    <Check className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
                  ) : (
                    <AlertCircle className="text-red-600 flex-shrink-0 mt-0.5" size={20} />
                  )}
                  <div>
                    <p className={`font-bold ${
                      result.success ? 'text-green-800' : 'text-red-800'
                    }`}>
                      {result.message}
                    </p>
                    {result.isDryRun && (
                      <p className="text-sm text-slate-600 mt-1">
                        This was a preview. Click "Execute Promotion" to make the changes permanent.
                      </p>
                    )}
                  </div>
                </div>

                {/* Promoted Students */}
                {result.promoted_count > 0 && (
                  <div className="mb-4">
                    <p className="font-bold text-green-700 mb-2">
                      ✅ {result.promoted_count} students to be promoted:
                    </p>
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3 max-h-32 overflow-y-auto">
                      {result.promoted_students.map((s, idx) => (
                        <div key={idx} className="text-sm text-green-800 py-1 border-b last:border-b-0">
                          {s.name} - {s.reason}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Not Promoted Students */}
                {result.not_promoted_count > 0 && (
                  <div className="mb-4">
                    <p className="font-bold text-orange-700 mb-2">
                      ⏳ {result.not_promoted_count} students NOT promoted:
                    </p>
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 max-h-32 overflow-y-auto">
                      {result.not_promoted_students.map((s, idx) => (
                        <div key={idx} className="text-sm text-orange-800 py-1 border-b last:border-b-0">
                          {s.name} - {s.reason}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-4 mt-6">
                  <button
                    onClick={() => {
                      setResult(null);
                      setDryRun(true);
                    }}
                    className="flex-1 p-3 bg-slate-200 text-slate-800 rounded-lg hover:bg-slate-300 font-bold"
                  >
                    ← Back
                  </button>

                  {result.isDryRun && (
                    <button
                      onClick={() => handleAutoPromote(false)}
                      disabled={loading}
                      className="flex-1 p-3 bg-amber-600 text-white rounded-lg hover:bg-amber-700 font-bold disabled:opacity-50"
                    >
                      {loading ? '...' : '✅ Execute Promotion'}
                    </button>
                  )}

                  {!result.isDryRun && (
                    <button
                      onClick={() => setShowModal(false)}
                      className="flex-1 p-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-bold"
                    >
                      ✓ Close
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AutoPromoteButton;
