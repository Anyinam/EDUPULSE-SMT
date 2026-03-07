import React, { useState, useEffect } from 'react';
import { Users, Filter, Download, Eye, Edit2, Check, X, AlertCircle } from 'lucide-react';
import axios from 'axios';

const EnrollmentManager = () => {
  const [students, setStudents] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('Active');
  const [classFilter, setClassFilter] = useState('');
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [updateMode, setUpdateMode] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [statusReason, setStatusReason] = useState('');
  const [classes, setClasses] = useState([]);

  const validStatuses = ['Active', 'Graduated', 'Withdrawn', 'Transferred', 'Suspended', 'Inactive'];
  const statusColors = {
    'Active': 'bg-green-100 text-green-800',
    'Graduated': 'bg-blue-100 text-blue-800',
    'Withdrawn': 'bg-red-100 text-red-800',
    'Transferred': 'bg-yellow-100 text-yellow-800',
    'Suspended': 'bg-orange-100 text-orange-800',
    'Inactive': 'bg-gray-100 text-gray-800',
  };

  useEffect(() => {
    fetchData();
  }, [filter, classFilter]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      
      // Fetch students
      const params = new URLSearchParams();
      if (filter) params.append('status', filter);
      if (classFilter) params.append('class', classFilter);

      const [studentsRes, statsRes] = await Promise.all([
        axios.get(`/api/admissions/students?${params.toString()}`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get('/api/admissions/statistics', {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      setStudents(studentsRes.data.students || []);
      setStatistics(statsRes.data);

      // Extract unique classes
      const uniqueClasses = [...new Set(studentsRes.data.students?.map(s => s.current_class).filter(Boolean))];
      setClasses(uniqueClasses);
    } catch (error) {
      console.error('Error fetching data:', error);
      alert('Failed to load students');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async () => {
    if (!selectedStudent || !newStatus) {
      alert('Please select a status');
      return;
    }

    try {
      const token = localStorage.getItem('token');
      await axios.put(
        `/api/admissions/students/${selectedStudent.id}/status`,
        {
          status: newStatus,
          reason: statusReason
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      alert(`Student status updated to ${newStatus}`);
      setUpdateMode(false);
      setSelectedStudent(null);
      setNewStatus('');
      setStatusReason('');
      fetchData();
    } catch (error) {
      console.error('Update error:', error);
      alert('Failed to update student status');
    }
  };

  const exportToCSV = () => {
    const csv = [
      ['Name', 'Student Code', 'Class', 'Status', 'Parent Name', 'Parent Phone'],
      ...students.map(s => [
        s.name,
        s.student_code,
        s.current_class,
        s.status,
        s.parent_name || '',
        s.parent_phone || ''
      ])
    ];

    const csvContent = csv.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `enrollment_${filter}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  if (loading) {
    return <div className="flex justify-center items-center h-64"><div className="animate-spin text-blue-600 text-4xl">⟳</div></div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2 mb-2">
            <Users className="w-8 h-8 text-blue-600" />
            Enrollment Management
          </h1>
          <p className="text-gray-600">Manage student enrollment status and admission records</p>
        </div>

        {/* Statistics Cards */}
        {statistics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            {Object.entries(statistics.status_summary).map(([status, count]) => (
              status !== 'total' && (
                <div key={status} className="bg-white rounded-lg shadow p-4">
                  <div className="text-2xl font-bold text-gray-900">{count}</div>
                  <div className="text-sm text-gray-600 capitalize">{status} Students</div>
                </div>
              )
            ))}
            <div className="bg-blue-50 rounded-lg shadow p-4 border-2 border-blue-200">
              <div className="text-2xl font-bold text-blue-900">{statistics.status_summary.total}</div>
              <div className="text-sm text-blue-600 font-semibold">Total Enrollment</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white rounded-lg shadow mb-6 p-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-gray-600" />
              <label className="text-sm font-medium text-gray-700">Status:</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {validStatuses.map(status => (
                  <option key={status} value={status}>{status}</option>
                ))}
                <option value="">All Statuses</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label className="text-sm font-medium text-gray-700">Class:</label>
              <select
                value={classFilter}
                onChange={(e) => setClassFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">All Classes</option>
                {classes.map(cls => (
                  <option key={cls} value={cls}>{cls}</option>
                ))}
              </select>
            </div>

            <button
              onClick={exportToCSV}
              className="ml-auto flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition text-sm"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </div>
        </div>

        {/* Student Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Name</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Code</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Class</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Status</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Parent</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Contact</th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-gray-700">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {students.length === 0 ? (
                <tr>
                  <td colSpan="7" className="px-6 py-8 text-center text-gray-500">
                    No students found
                  </td>
                </tr>
              ) : (
                students.map(student => (
                  <tr key={student.id} className="hover:bg-gray-50 transition">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{student.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{student.student_code}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{student.current_class}</td>
                    <td className="px-6 py-4">
                      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${statusColors[student.status] || statusColors['Inactive']}`}>
                        {student.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{student.parent_name || '-'}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{student.parent_phone || '-'}</td>
                    <td className="px-6 py-4 text-sm">
                      <button
                        onClick={() => {
                          setSelectedStudent(student);
                          setNewStatus(student.status);
                          setStatusReason('');
                          setUpdateMode(true);
                        }}
                        className="text-blue-600 hover:text-blue-900 font-medium flex items-center gap-1"
                      >
                        <Edit2 className="w-4 h-4" />
                        Edit
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Update Modal */}
        {updateMode && selectedStudent && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-lg max-w-md w-full p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">Update Student Status</h3>
              
              <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm font-medium text-gray-700">Student: <span className="text-blue-600">{selectedStudent.name}</span></p>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">New Status</label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Select Status</option>
                  {validStatuses.map(status => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </div>

              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">Reason (Optional)</label>
                <textarea
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  placeholder="e.g., Graduated from JHS 3, Transferred to another school"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  rows="3"
                />
              </div>

              <div className="flex gap-3">
                <button
                  onClick={() => setUpdateMode(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleStatusUpdate}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium flex items-center justify-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  Update
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EnrollmentManager;
