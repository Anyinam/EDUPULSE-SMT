import React, { useEffect, useState } from 'react';
import { AlertCircle, Check, Loader } from 'lucide-react';
import axios from 'axios';
import useSchoolClasses from '../hooks/useSchoolClasses';

const BulkStatusUpdate = ({ trigger = 'button' }) => {
  const [showModal, setShowModal] = useState(false);
  const [selectedClass, setSelectedClass] = useState('');
  const [newStatus, setNewStatus] = useState('Graduated');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [students, setStudents] = useState([]);
  const [selectedStudentIds, setSelectedStudentIds] = useState([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const { classes } = useSchoolClasses();

  useEffect(() => {
    if (classes.length === 0) {
      return;
    }

    if (!classes.includes(selectedClass)) {
      setSelectedClass(classes[0]);
    }
  }, [classes, selectedClass]);

  useEffect(() => {
    if (!showModal) {
      return;
    }

    const fetchStudents = async () => {
      try {
        setLoadingStudents(true);
        const token = localStorage.getItem('token');
        const schoolId = localStorage.getItem('school_id');
        const response = await axios.get('/api/students?include_inactive=true', {
          headers: {
            Authorization: `Bearer ${token}`,
            'X-School-ID': schoolId,
          },
        });
        setStudents(Array.isArray(response.data) ? response.data : []);
      } catch (error) {
        setStudents([]);
      } finally {
        setLoadingStudents(false);
      }
    };

    fetchStudents();
  }, [showModal]);

  useEffect(() => {
    setSelectedStudentIds([]);
  }, [selectedClass, newStatus]);

  const visibleStudents = students.filter((student) => (
    student.current_class === selectedClass && (student.status || 'Active') === 'Active'
  ));
  const allVisibleSelected = visibleStudents.length > 0 && visibleStudents.every((student) => selectedStudentIds.includes(student.id));

  const validStatuses = ['Graduated', 'Withdrawn', 'Transferred', 'Suspended', 'Inactive'];

  const handleBulkUpdate = async () => {
    if (!selectedClass || !newStatus) {
      alert('Please select a class and status');
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const schoolId = localStorage.getItem('school_id');
      const selectAllClass = selectedStudentIds.length === 0 || allVisibleSelected;
      
      const response = await axios.post(
        '/api/admissions/students/bulk-update-status',
        {
          class: selectedClass,
          status: newStatus,
          current_status: 'Active',
          reason: reason,
          select_all_class: selectAllClass,
          student_ids: selectAllClass ? [] : selectedStudentIds,
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
        message: response.data.message,
        count: response.data.updated_count,
        students: response.data.updated_students
      });

    } catch (error) {
      setResult({
        success: false,
        message: error.response?.data?.message || 'Bulk update failed',
        error: error.response?.data?.error
      });
    } finally {
      setLoading(false);
    }
  };

  const toggleStudentSelection = (studentId) => {
    setSelectedStudentIds((current) => (
      current.includes(studentId)
        ? current.filter((id) => id !== studentId)
        : [...current, studentId]
    ));
  };

  const toggleAllVisibleStudents = () => {
    if (allVisibleSelected) {
      setSelectedStudentIds([]);
      return;
    }
    setSelectedStudentIds(visibleStudents.map((student) => student.id));
  };

  if (trigger === 'modal') {
    return (
      <>
        <button
          onClick={() => setShowModal(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition flex items-center gap-2"
        >
          ⚡ Bulk Update Status
        </button>

        {showModal && (
          <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <div className="flex items-center gap-2 mb-4">
                <AlertCircle className="w-6 h-6 text-blue-600" />
                <h3 className="text-xl font-bold text-gray-900">Bulk Status Update</h3>
              </div>

              {!result ? (
                <>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-800">
                    ⚡ Update all <strong>Active</strong> students in a class to a new status at once
                  </div>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Select Class
                      </label>
                      <select
                        value={selectedClass}
                        onChange={(e) => setSelectedClass(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-medium"
                        disabled={classes.length === 0}
                      >
                        {classes.length === 0 && <option value="">No school classes configured</option>}
                        {classes.map(cls => (
                          <option key={cls} value={cls}>{cls}</option>
                        ))}
                      </select>
                      <p className="text-xs text-gray-500 mt-1">Only Active students will be updated</p>
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-800">Student selection</p>
                          <p className="text-xs text-slate-500">Leave all selected to update the whole class, or pick specific students below.</p>
                        </div>
                        <button
                          type="button"
                          onClick={toggleAllVisibleStudents}
                          disabled={visibleStudents.length === 0}
                          className={`rounded-lg px-3 py-2 text-xs font-bold transition ${allVisibleSelected ? 'bg-slate-900 text-white' : 'bg-white text-slate-700 border border-slate-300'}`}
                        >
                          {allVisibleSelected ? 'Selected Entire Class' : 'Select Entire Class'}
                        </button>
                      </div>

                      <div className="mt-3 max-h-48 space-y-2 overflow-y-auto">
                        {loadingStudents ? <p className="text-xs text-slate-500">Loading students...</p> : null}
                        {!loadingStudents && visibleStudents.length === 0 ? <p className="text-xs text-slate-500">No active students found in this class.</p> : null}
                        {visibleStudents.map((student) => {
                          const checked = selectedStudentIds.includes(student.id);
                          return (
                            <label
                              key={student.id}
                              className={`flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 text-sm transition ${checked ? 'border-blue-500 bg-blue-50 text-blue-900' : 'border-slate-200 bg-white text-slate-700'}`}
                            >
                              <span>
                                <span className="font-semibold">{student.name}</span>
                                <span className="ml-2 text-xs text-slate-500">{student.student_code} • {student.current_class}</span>
                              </span>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleStudentSelection(student.id)}
                                className="h-4 w-4"
                              />
                            </label>
                          );
                        })}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        New Status
                      </label>
                      <select
                        value={newStatus}
                        onChange={(e) => setNewStatus(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-medium"
                      >
                        {validStatuses.map(status => (
                          <option key={status} value={status}>{status}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Reason (Optional)
                      </label>
                      <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder={
                          newStatus === 'Graduated' ? 'e.g., Completed school year, passed BECE' :
                          newStatus === 'Withdrawn' ? 'e.g., Parents withdrew students' :
                          'Reason for bulk update'
                        }
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                        rows="2"
                      />
                    </div>

                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
                      ⚠️ This will update <strong>{selectedStudentIds.length > 0 && !allVisibleSelected ? `${selectedStudentIds.length} selected` : 'all active'}</strong> students in {selectedClass} to <strong>{newStatus}</strong>
                    </div>

                    <div className="flex gap-3 pt-4">
                      <button
                        onClick={() => setShowModal(false)}
                        className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleBulkUpdate}
                        disabled={loading}
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium flex items-center justify-center gap-2 disabled:bg-gray-400"
                      >
                        {loading ? (
                          <>
                            <Loader className="w-4 h-4 animate-spin" />
                            Updating...
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4" />
                            Update {selectedStudentIds.length > 0 && !allVisibleSelected ? 'Selected Students' : selectedClass}
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className={`p-4 rounded-lg ${result.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                  <div className={`flex items-center gap-2 mb-2 ${result.success ? 'text-green-800' : 'text-red-800'}`}>
                    {result.success ? (
                      <Check className="w-5 h-5" />
                    ) : (
                      <AlertCircle className="w-5 h-5" />
                    )}
                    <h4 className="font-bold">{result.success ? 'Success!' : 'Error'}</h4>
                  </div>
                  <p className={`text-sm mb-3 ${result.success ? 'text-green-700' : 'text-red-700'}`}>
                    {result.message}
                  </p>
                  {result.success && result.count > 0 && (
                    <div className="text-sm mb-3">
                      <div className="font-semibold text-green-800 mb-1">Updated {result.count} students:</div>
                      <div className="text-green-700 text-xs space-y-1">
                        {result.students?.map((name, i) => (
                          <div key={i}>• {name}</div>
                        ))}
                        {result.count > 10 && <div className="italic">+ {result.count - 10} more...</div>}
                      </div>
                    </div>
                  )}
                  <div className="flex gap-2 pt-4">
                    <button
                      onClick={() => {
                        setResult(null);
                        setShowModal(false);
                      }}
                      className="flex-1 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition font-medium"
                    >
                      Close
                    </button>
                    {result.success && (
                      <button
                        onClick={() => {
                          setResult(null);
                          setReason('');
                        }}
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium"
                      >
                        Update Another Class
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </>
    );
  }

  // Return as utility component that can be placed inline
  return null;
};

export default BulkStatusUpdate;
