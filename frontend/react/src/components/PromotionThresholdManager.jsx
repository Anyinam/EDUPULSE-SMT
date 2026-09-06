import React, { useState, useEffect } from 'react';
import { AlertCircle, Check, Loader, Settings, Trash2 } from 'lucide-react';
import axios from 'axios';
import useSchoolClasses from '../hooks/useSchoolClasses';

const PromotionThresholdManager = () => {
  const [showModal, setShowModal] = useState(false);
  const [selectedClass, setSelectedClass] = useState('All Classes');
  const [thresholdPercentage, setThresholdPercentage] = useState('');
  const [minCourses, setMinCourses] = useState('1');
  const [thresholds, setThresholds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const { classes: schoolClasses } = useSchoolClasses();
  const classOptions = ['All Classes', ...schoolClasses];

  useEffect(() => {
    fetchThresholds();
  }, []);

  useEffect(() => {
    if (selectedClass === 'All Classes') {
      return;
    }
    if (schoolClasses.length === 0 || schoolClasses.includes(selectedClass)) {
      return;
    }
    setSelectedClass('All Classes');
  }, [schoolClasses, selectedClass]);

  const fetchThresholds = async () => {
    try {
      const token = localStorage.getItem('token');
      const schoolId = localStorage.getItem('school_id');
      const response = await axios.get(
        '/api/admissions/promotion-threshold',
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-School-ID': schoolId
          }
        }
      );
      setThresholds(response.data.thresholds || []);
    } catch (err) {
      console.error('Failed to fetch thresholds', err);
    }
  };

  const handleSaveThreshold = async () => {
    if (!selectedClass) {
      alert('Please select a class');
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const schoolId = localStorage.getItem('school_id');
      
      const response = await axios.post(
        '/api/admissions/promotion-threshold',
        {
          class_name: selectedClass === 'All Classes' ? null : selectedClass,
          threshold_percentage: thresholdPercentage ? parseFloat(thresholdPercentage) : null,
          min_courses_required: parseInt(minCourses) || 1
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-School-ID': schoolId
          }
        }
      );

      setResult({
        success: true,
        message: response.data.message
      });

      // Reset form
      setSelectedClass('All Classes');
      setThresholdPercentage('');
      setMinCourses('1');
      
      // Refresh thresholds
      fetchThresholds();
      
      // Close modal after 2 seconds
      setTimeout(() => setShowModal(false), 2000);

    } catch (error) {
      setResult({
        success: false,
        message: error.response?.data?.message || 'Failed to save threshold'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* Main Button */}
      <button
        onClick={() => setShowModal(true)}
        className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-bold flex items-center gap-2"
      >
        <Settings size={18} />
        Configure Promotion Thresholds
      </button>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 text-slate-900">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-bold text-slate-800">Configure Promotion Thresholds</h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            {result ? (
              <div className={`p-4 rounded-lg mb-4 flex items-start gap-3 ${
                result.success 
                  ? 'bg-green-50 border border-green-200' 
                  : 'bg-red-50 border border-red-200'
              }`}>
                {result.success ? (
                  <Check className="text-green-600 shrink-0 mt-0.5" size={20} />
                ) : (
                  <AlertCircle className="text-red-600 shrink-0 mt-0.5" size={20} />
                )}
                <p className={`text-sm font-medium ${
                  result.success ? 'text-green-800' : 'text-red-800'
                }`}>
                  {result.message}
                </p>
              </div>
            ) : (
              <>
                <div className="space-y-4 mb-6">
                  {/* Class Selection */}
                  <div>
                    <label className="block text-sm font-bold text-slate-700 mb-2">
                      Class
                    </label>
                    <select
                      value={selectedClass}
                      onChange={(e) => setSelectedClass(e.target.value)}
                      className="w-full p-3 border rounded-lg bg-slate-50 font-medium text-slate-900"
                    >
                      {classOptions.map(cls => (
                        <option key={cls} value={cls}>{cls}</option>
                      ))}
                    </select>
                    <p className="text-xs text-slate-500 mt-1">
                      Select "All Classes" to set a default threshold for any class without specific rules
                    </p>
                  </div>

                  {/* Threshold Percentage */}
                  <div>
                    <label className="block text-sm font-bold text-slate-700 mb-2">
                      Performance Threshold (%) - Leave blank for auto-promote all
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      placeholder="e.g., 55.5"
                      value={thresholdPercentage}
                      onChange={(e) => setThresholdPercentage(e.target.value)}
                      className="w-full p-3 border rounded-lg bg-slate-50 text-slate-900 placeholder:text-slate-400"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Example: If 9 courses taught each worth 100 marks = 900 total, entering 55.5 means students need 500 marks (55.5%)
                    </p>
                  </div>

                  {/* Minimum Courses */}
                  <div>
                    <label className="block text-sm font-bold text-slate-700 mb-2">
                      Minimum Courses Required
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={minCourses}
                      onChange={(e) => setMinCourses(e.target.value)}
                      className="w-full p-3 border rounded-lg bg-slate-50 text-slate-900"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Student must have grades in at least this many courses to be considered for promotion
                    </p>
                  </div>
                </div>

                <button
                  onClick={handleSaveThreshold}
                  disabled={loading}
                  className="w-full p-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-bold disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader size={18} className="animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Threshold'
                  )}
                </button>
              </>
            )}

            {/* Current Thresholds List */}
            {thresholds.length > 0 && (
              <div className="mt-6 pt-6 border-t">
                <h4 className="font-bold text-slate-700 mb-3 text-sm">Current Thresholds</h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {thresholds.map((t, idx) => (
                    <div key={idx} className="p-3 bg-slate-50 rounded-lg border text-sm">
                      <p className="font-semibold text-slate-800">{t.class_name}</p>
                      <p className="text-slate-600">
                        Threshold: {t.threshold_percentage ? `${t.threshold_percentage}%` : 'Auto-promote all'}
                      </p>
                      <p className="text-slate-600 text-xs">
                        Min Courses: {t.min_courses_required}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PromotionThresholdManager;
