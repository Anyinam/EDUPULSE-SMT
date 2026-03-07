import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const filterText = (value, query) => {
  if (!query) return true;
  if (value === null || value === undefined) return false;
  return String(value).toLowerCase().includes(query);
};

const toCsvValue = (value) => {
  const normalized = value === null || value === undefined ? '' : String(value);
  return `"${normalized.replace(/"/g, '""')}"`;
};

export default function StudentsRegistry() {
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [classFilter, setClassFilter] = useState('All');
  const [editingStudent, setEditingStudent] = useState(null);
  const [editData, setEditData] = useState({});

  useEffect(() => {
    const fetchStudents = async () => {
      setLoading(true);
      try {
        const headers = {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id')
        };
        const res = await axios.get('/api/students', { headers });
        setStudents(res.data || []);
      } catch (err) {
        console.error('Failed to load students registry', err);
        setStudents([]);
      } finally {
        setLoading(false);
      }
    };

    fetchStudents();
  }, []);

  const normalizedQuery = query.trim().toLowerCase();

  const classOptions = useMemo(() => {
    const uniqueClasses = Array.from(new Set(
      students.map(s => s.current_class).filter(Boolean)
    )).sort();
    return ['All', ...uniqueClasses];
  }, [students]);

  const filteredStudents = useMemo(() => {
    return students.filter((student) => {
      const matchesClass = classFilter === 'All' || student.current_class === classFilter;
      if (!matchesClass) return false;

      return (
        filterText(student.name, normalizedQuery) ||
        filterText(student.student_code, normalizedQuery) ||
        filterText(student.current_class, normalizedQuery) ||
        filterText(student.is_on_scholarship ? (student.scholarship_covers_feeding ? 'tuition feeding scholarship' : 'tuition scholarship') : 'none', normalizedQuery) ||
        filterText(student.guardian_name, normalizedQuery) ||
        filterText(student.parent_email, normalizedQuery) ||
        filterText(student.parent_phone, normalizedQuery)
      );
    });
  }, [students, classFilter, normalizedQuery]);

  const handleDelete = async (student) => {
    if (!window.confirm(`Are you sure you want to delete ${student.name} (${student.student_code})? This cannot be undone.`)) {
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      await axios.delete(`/api/admissions/students/${student.id}`, { headers });
      alert(`${student.name} has been deleted successfully.`);
      // Refresh the list
      setStudents(students.filter(s => s.id !== student.id));
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to delete student.');
      console.error('Delete error:', err);
    }
  };

  const handleEditClick = (student) => {
    setEditingStudent(student);
    setEditData({
      name: student.name || '',
      student_code: student.student_code || '',
      current_class: student.current_class || '',
      guardian_name: student.guardian_name || '',
      parent_email: student.parent_email || '',
      parent_phone: student.parent_phone || '',
      date_of_birth: student.date_of_birth || '',
      gender: student.gender || '',
    });
  };

  const handleSaveEdit = async () => {
    if (!editData.name || !editData.student_code || !editData.current_class) {
      alert('Please fill in Name, Student Code, and Class.');
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      await axios.put(`/api/students/${editingStudent.id}`, editData, { headers });
      alert('Student information updated successfully.');
      
      // Update local state
      setStudents(students.map(s => s.id === editingStudent.id ? { ...s, ...editData } : s));
      setEditingStudent(null);
      setEditData({});
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to update student.');
      console.error('Update error:', err);
    }
  };

  const handleExport = () => {
    if (!filteredStudents.length) {
      alert('No students to export.');
      return;
    }

    const headers = [
      'Name',
      'Student Code',
      'Class',
      'Date of Birth',
      'Age',
      'Gender',
      'Scholarship',
      'Guardian',
      'Parent Email',
      'Parent Phone',
      'Feeding Paid',
      'Present'
    ];

    const rows = filteredStudents.map((student) => [
      student.name,
      student.student_code,
      student.current_class,
      student.date_of_birth || '',
      student.age ?? '',
      student.gender || '',
      student.is_on_scholarship
        ? (student.scholarship_covers_feeding ? 'Tuition + Feeding' : 'Tuition')
        : 'None',
      student.guardian_name,
      student.parent_email,
      student.parent_phone,
      student.feeding_paid ? 'Yes' : 'No',
      student.is_present ? 'Yes' : 'No'
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map(toCsvValue).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.setAttribute('download', `students_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <>
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">All Students</h2>
          <p className="text-sm text-slate-500">Search, filter, and export your full registry.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, ID, class, guardian"
            className="w-full sm:w-72 p-3 border rounded-xl bg-slate-50"
          />
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="w-full sm:w-40 p-3 border rounded-xl bg-slate-50"
          >
            {classOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
          <button
            onClick={handleExport}
            className="bg-emerald-600 text-white px-5 py-3 rounded-xl font-bold hover:bg-emerald-700 shadow-lg shadow-emerald-200"
          >
            📥 Export CSV
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
        <span>Showing {filteredStudents.length} of {students.length} students</span>
        {loading && <span>Loading registry...</span>}
      </div>

      <div className="border border-slate-200 rounded-2xl overflow-hidden">
        <div className="overflow-auto max-h-[60vh]">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 sticky top-0 z-10">
              <tr className="text-left text-slate-600">
                <th className="p-3 font-semibold">Name</th>
                <th className="p-3 font-semibold">Student Code</th>
                <th className="p-3 font-semibold">Class</th>
                <th className="p-3 font-semibold">DOB</th>
                <th className="p-3 font-semibold">Age</th>
                <th className="p-3 font-semibold">Gender</th>
                <th className="p-3 font-semibold">Scholarship</th>
                <th className="p-3 font-semibold">Guardian</th>
                <th className="p-3 font-semibold">Parent Email</th>
                <th className="p-3 font-semibold">Parent Phone</th>
                <th className="p-3 font-semibold">Feeding Paid</th>
                <th className="p-3 font-semibold">Present</th>
                <th className="p-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {!loading && filteredStudents.length === 0 && (
                <tr>
                  <td colSpan={13} className="p-6 text-center text-slate-400">No students found.</td>
                </tr>
              )}
              {filteredStudents.map((student, index) => (
                <tr
                  key={student.id}
                  className={index % 2 === 0 ? 'bg-white' : 'bg-slate-50'}
                >
                  <td className="p-3 font-medium text-slate-800">{student.name}</td>
                  <td className="p-3 text-slate-600">{student.student_code}</td>
                  <td className="p-3 text-slate-600">{student.current_class}</td>
                  <td className="p-3 text-slate-600">{student.date_of_birth || '-'}</td>
                  <td className="p-3 text-slate-600">{student.age ?? '-'}</td>
                  <td className="p-3 text-slate-600">{student.gender || '-'}</td>
                  <td className="p-3 text-slate-600">
                    {student.is_on_scholarship
                      ? (student.scholarship_covers_feeding ? 'Tuition + Feeding' : 'Tuition')
                      : '-'}
                  </td>
                  <td className="p-3 text-slate-600">{student.guardian_name || '-'}</td>
                  <td className="p-3 text-slate-600">{student.parent_email || '-'}</td>
                  <td className="p-3 text-slate-600">{student.parent_phone || '-'}</td>
                  <td className="p-3">
                    <span className={student.feeding_paid ? 'text-emerald-600 font-semibold' : 'text-rose-500 font-semibold'}>
                      {student.feeding_paid ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td className="p-3">
                    <span className={student.is_present ? 'text-emerald-600 font-semibold' : 'text-slate-400 font-semibold'}>
                      {student.is_present ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEditClick(student)}
                        className="bg-blue-100 text-blue-600 px-3 py-1 rounded-lg text-sm font-semibold hover:bg-blue-200 transition"
                        title="Edit student information"
                      >
                        ✎️ Edit
                      </button>
                      <button
                        onClick={() => handleDelete(student)}
                        className="bg-red-100 text-red-600 px-3 py-1 rounded-lg text-sm font-semibold hover:bg-red-200 transition"
                        title="Delete this student record"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    {/* Edit Student Modal */}
    {editingStudent && (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
          <div className="sticky top-0 bg-linear-to-r from-blue-600 to-blue-700 text-white p-6 rounded-t-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold">✎️ Edit Student Information</h2>
              <button
                onClick={() => setEditingStudent(null)}
                className="text-white hover:bg-white hover:bg-opacity-20 rounded-full w-8 h-8 flex items-center justify-center text-xl font-bold"
              >
                ✕
              </button>
            </div>
            <p className="text-blue-100 text-sm mt-2">{editingStudent.name} ({editingStudent.student_code})</p>
          </div>

          <div className="p-6 space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Name *</label>
              <input
                type="text"
                value={editData.name}
                onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Student name"
              />
            </div>

            {/* Student Code */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Student Code *</label>
              <input
                type="text"
                value={editData.student_code}
                onChange={(e) => setEditData({ ...editData, student_code: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Student code"
              />
            </div>

            {/* Current Class */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Current Class *</label>
              <select
                value={editData.current_class}
                onChange={(e) => setEditData({ ...editData, current_class: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select class</option>
                <option value="Nursery">Nursery</option>
                <option value="KG">KG</option>
                <option value="Class 1">Class 1</option>
                <option value="Class 2">Class 2</option>
                <option value="Class 3">Class 3</option>
                <option value="Class 4">Class 4</option>
                <option value="Class 5">Class 5</option>
                <option value="Class 6">Class 6</option>
                <option value="JHS 1">JHS 1</option>
                <option value="JHS 2">JHS 2</option>
                <option value="JHS 3">JHS 3</option>
              </select>
            </div>

            {/* Gender */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Gender</label>
              <select
                value={editData.gender}
                onChange={(e) => setEditData({ ...editData, gender: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select gender</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>

            {/* Date of Birth */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Date of Birth</label>
              <input
                type="date"
                value={editData.date_of_birth}
                onChange={(e) => setEditData({ ...editData, date_of_birth: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Guardian Name */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Guardian Name</label>
              <input
                type="text"
                value={editData.guardian_name}
                onChange={(e) => setEditData({ ...editData, guardian_name: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Guardian name"
              />
            </div>

            {/* Parent Email */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Parent Email</label>
              <input
                type="email"
                value={editData.parent_email}
                onChange={(e) => setEditData({ ...editData, parent_email: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="parent@example.com"
              />
            </div>

            {/* Parent Phone */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">Parent Phone</label>
              <input
                type="tel"
                value={editData.parent_phone}
                onChange={(e) => setEditData({ ...editData, parent_phone: e.target.value })}
                className="w-full p-3 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="+233 XXX XXX XXXX"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-6 border-t">
              <button
                onClick={handleSaveEdit}
                className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-blue-700 transition-colors"
              >
                💾 Save Changes
              </button>
              <button
                onClick={() => setEditingStudent(null)}
                className="flex-1 bg-slate-200 text-slate-700 px-6 py-3 rounded-lg font-bold hover:bg-slate-300 transition-colors"
              >
                ✕ Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
