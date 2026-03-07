import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useBranding } from '../hooks/useBranding';

const CLASS_OPTIONS = [
  'Nursery',
  'KG',
  'Class 1',
  'Class 2',
  'Class 3',
  'Class 4',
  'Class 5',
  'Class 6',
  'JHS 1',
  'JHS 2',
  'JHS 3'
];

const DEFAULT_SUBJECTS = [
  'Mathematics',
  'English Language',
  'Science',
  'Social Studies',
  'Religious and Moral Education',
  'Ghanaian Language',
  'French',
  'ICT',
  'Creative Arts',
  'Physical Education',
  'History',
  'Geography',
  'Economics',
  'Physics',
  'Chemistry',
  'Biology',
  'Elective Mathematics'
];

const DAY_OPTIONS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

export default function TimetableManager({
  title = 'School Timetable',
  scope = 'school',
  canManage = true,
  className = '',
  showClassFilter = false
}) {
  const [entries, setEntries] = useState([]);
  const [staff, setStaff] = useState([]);
  const [message, setMessage] = useState('');
  const [classFilter, setClassFilter] = useState(className || '');
  const { branding } = useBranding();
  const [availableSubjects, setAvailableSubjects] = useState(DEFAULT_SUBJECTS);
  const [customSubject, setCustomSubject] = useState('');
  const [showSubjectManager, setShowSubjectManager] = useState(false);
  const [form, setForm] = useState({
    class_name: 'JHS 1',
    subject_name: '',
    teacher_id: '',
    day_of_week: 'Monday',
    start_time: '08:00',
    end_time: '09:00',
    location: ''
  });

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const sortedEntries = useMemo(() => {
    return [...entries].sort((a, b) => {
      if (a.day_of_week === b.day_of_week) {
        return a.start_time.localeCompare(b.start_time);
      }
      return a.day_of_week.localeCompare(b.day_of_week);
    });
  }, [entries]);

  useEffect(() => {
    const fetchEntries = async () => {
      try {
        let endpoint = '/api/timetable';
        if (scope === 'mine') {
          endpoint = '/api/timetable/my';
        } else if (scope === 'class') {
          if (!classFilter) {
            setEntries([]);
            return;
          }
          endpoint = `/api/timetable/class/${encodeURIComponent(classFilter)}`;
        }

        const res = await axios.get(endpoint, getAuthHeaders());
        const data = Array.isArray(res.data) ? res.data : [];
        setEntries(data);
        
        // Extract subjects from timetable entries and merge with defaults
        const timetableSubjects = [...new Set(data.map(entry => entry.subject_name))].filter(Boolean);
        const mergedSubjects = [...new Set([...DEFAULT_SUBJECTS, ...timetableSubjects])].sort();
        setAvailableSubjects(mergedSubjects);
      } catch (err) {
        console.error('Failed to load timetable', err);
      }
    };

    const fetchStaff = async () => {
      if (!canManage) return;
      try {
        const res = await axios.get('/api/staff/list', getAuthHeaders());
        const staffList = Array.isArray(res.data) ? res.data : [];
        // Filter to only show teachers and homeroom teachers
        const teachers = staffList.filter(s => 
          s.roles?.includes('teacher') || 
          s.roles?.includes('homeroom') || 
          s.role === 'teacher' || 
          s.role === 'homeroom'
        );
        console.log('Loaded teachers:', teachers);
        setStaff(teachers.length > 0 ? teachers : staffList);
      } catch (err) {
        console.error('Failed to load staff list', err);
        setStaff([]);
      }
    };

    fetchEntries();
    fetchStaff();
  }, [scope, canManage, classFilter]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.subject_name.trim()) {
      setMessage('Subject is required.');
      return;
    }
    if (!form.teacher_id) {
      setMessage('Select a teacher for this slot.');
      return;
    }
    if (form.start_time >= form.end_time) {
      setMessage('End time must be after start time.');
      return;
    }

    try {
      const res = await axios.post('/api/timetable', {
        class_name: form.class_name,
        subject_name: form.subject_name.trim(),
        teacher_id: parseInt(form.teacher_id, 10),
        day_of_week: form.day_of_week,
        start_time: form.start_time,
        end_time: form.end_time,
        location: form.location.trim()
      }, getAuthHeaders());
      setEntries((prev) => [res.data, ...prev]);
      setMessage('Timetable entry saved.');
      
      // Add subject to available subjects if it's custom
      if (!availableSubjects.includes(form.subject_name.trim())) {
        setAvailableSubjects([...availableSubjects, form.subject_name.trim()].sort());
      }
      
      setForm((prev) => ({
        ...prev,
        subject_name: '',
        teacher_id: '',
        location: ''
      }));
      setTimeout(() => setMessage(''), 2500);
    } catch (err) {
      const errorMessage = err.response?.data?.message || 'Failed to save timetable entry.';
      setMessage(errorMessage);
    }
  };

  const handleDelete = async (entryId) => {
    if (!window.confirm('Remove this timetable entry?')) return;
    try {
      await axios.delete(`/api/timetable/${entryId}`, getAuthHeaders());
      setEntries((prev) => prev.filter((entry) => entry.id !== entryId));
    } catch (err) {
      alert('Failed to delete entry.');
    }
  };

  const handleExport = async () => {
    try {
      const params = new URLSearchParams();
      if (scope === 'class' && classFilter) {
        params.append('class_name', classFilter);
      }

      const endpoint = `/api/timetable/export${params.toString() ? `?${params.toString()}` : ''}`;
      const response = await axios.get(endpoint, {
        ...getAuthHeaders(),
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'timetable.csv';
      if (contentDisposition) {
        const matches = /filename="?([^"]+)"?/.exec(contentDisposition);
        if (matches && matches[1]) {
          filename = matches[1];
        }
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      setMessage('Timetable exported successfully!');
      setTimeout(() => setMessage(''), 2500);
    } catch (err) {
      console.error('Export error:', err);
      alert('Failed to export timetable.');
    }
  };

  const handlePrint = () => {
    const printWindow = window.open('', '_blank');
    const titleSuffix = scope === 'class' && classFilter ? ` - ${classFilter}` : '';
    
    const html = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>${title} - Print</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            h1 { text-align: center; color: #1e3a8a; margin-bottom: 5px; }
            h2 { text-align: center; color: #64748b; font-size: 18px; margin-top: 0; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th { background-color: #f1f5f9; padding: 12px; text-align: left; border: 1px solid #e2e8f0; font-weight: bold; }
            td { padding: 10px; border: 1px solid #e2e8f0; }
            tr:nth-child(even) { background-color: #f8fafc; }
            .footer { text-align: center; margin-top: 30px; color: #94a3b8; font-size: 12px; }
            @media print {
              button { display: none; }
            }
          </style>
        </head>
        <body>
          <h1>${branding.name || 'School Timetable'}</h1>
          <h2>${title}${titleSuffix}</h2>
          <table>
            <thead>
              <tr>
                <th>Day</th>
                <th>Time</th>
                <th>Class</th>
                <th>Subject</th>
                <th>Teacher</th>
                <th>Location</th>
              </tr>
            </thead>
            <tbody>
              ${sortedEntries.map(entry => `
                <tr>
                  <td>${entry.day_of_week}</td>
                  <td>${entry.start_time} - ${entry.end_time}</td>
                  <td>${entry.class_name}</td>
                  <td>${entry.subject_name}</td>
                  <td>${entry.teacher_name || 'Unassigned'}</td>
                  <td>${entry.location || '-'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          <div class="footer">
            <p>Generated on ${new Date().toLocaleDateString()} at ${new Date().toLocaleTimeString()}</p>
          </div>
          <script>
            window.onload = () => {
              window.print();
              setTimeout(() => window.close(), 500);
            };
          </script>
        </body>
      </html>
    `;
    
    printWindow.document.write(html);
    printWindow.document.close();
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-xl font-bold text-slate-800">🗓️ {title}</h3>
          <p className="text-sm text-slate-500">Classes, subjects, and teaching slots.</p>
        </div>
        <div className="flex items-center gap-2">
          {sortedEntries.length > 0 && (
            <>
              <button
                onClick={handleExport}
                className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
              >
                📥 Export CSV
              </button>
              <button
                onClick={handlePrint}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2"
              >
                🖨️ Print PDF
              </button>
            </>
          )}
          {message && <span className="text-xs font-bold text-emerald-600">{message}</span>}
        </div>
      </div>

      {canManage && showSubjectManager && (
        <div className="bg-linear-to-r from-purple-50 to-blue-50 p-6 rounded-2xl shadow-sm border-2 border-purple-200 mb-6">
          <h3 className="text-lg font-bold text-purple-900 mb-4">📚 Subject Management</h3>
          <div className="bg-white p-4 rounded-lg mb-4">
            <label className="block text-sm font-bold text-slate-700 mb-2">Add Custom Subject</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Enter subject name (e.g., Computer Science)"
                value={customSubject}
                onChange={(e) => setCustomSubject(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && customSubject.trim()) {
                    e.preventDefault();
                    const newSubject = customSubject.trim();
                    if (!availableSubjects.includes(newSubject)) {
                      setAvailableSubjects([...availableSubjects, newSubject].sort());
                      setMessage(`Subject "${newSubject}" added successfully!`);
                      setTimeout(() => setMessage(''), 3000);
                    } else {
                      setMessage(`Subject "${newSubject}" already exists.`);
                      setTimeout(() => setMessage(''), 3000);
                    }
                    setCustomSubject('');
                  }
                }}
                className="flex-1 p-3 border rounded-lg"
              />
              <button
                type="button"
                onClick={() => {
                  const newSubject = customSubject.trim();
                  if (newSubject) {
                    if (!availableSubjects.includes(newSubject)) {
                      setAvailableSubjects([...availableSubjects, newSubject].sort());
                      setMessage(`Subject "${newSubject}" added successfully!`);
                      setTimeout(() => setMessage(''), 3000);
                    } else {
                      setMessage(`Subject "${newSubject}" already exists.`);
                      setTimeout(() => setMessage(''), 3000);
                    }
                    setCustomSubject('');
                  }
                }}
                className="px-6 py-3 bg-purple-600 text-white rounded-lg font-bold hover:bg-purple-700"
              >
                Add Subject
              </button>
            </div>
            <p className="text-xs text-slate-500 mt-2">Added subjects will be available in timetable, teacher assignments, and terminal reports.</p>
          </div>
          <div className="bg-white p-4 rounded-lg">
            <label className="block text-sm font-bold text-slate-700 mb-2">Available Subjects ({availableSubjects.length})</label>
            <div className="flex flex-wrap gap-2 max-h-60 overflow-y-auto">
              {availableSubjects.map((subj, idx) => (
                <div
                  key={idx}
                  className="inline-flex items-center gap-2 px-3 py-1 bg-purple-100 text-purple-800 rounded-lg text-sm"
                >
                  <span>{subj}</span>
                  {!DEFAULT_SUBJECTS.includes(subj) && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`Remove "${subj}" from available subjects?`)) {
                          setAvailableSubjects(availableSubjects.filter(s => s !== subj));
                          setMessage(`Subject "${subj}" removed.`);
                          setTimeout(() => setMessage(''), 3000);
                        }
                      }}
                      className="text-purple-600 hover:text-purple-900 font-bold text-lg leading-none"
                      title="Remove subject"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-2">* Default subjects cannot be removed. Custom subjects can be deleted with × button.</p>
          </div>
        </div>
      )}

      {canManage && (
        <form onSubmit={handleCreate} className="grid grid-cols-1 lg:grid-cols-7 gap-3 mb-6">
          <select
            name="class_name"
            value={form.class_name}
            onChange={handleChange}
            className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700"
          >
            {CLASS_OPTIONS.map((cls) => (
              <option key={cls} value={cls}>{cls}</option>
            ))}
          </select>
          <div className="relative">
            <select
              name="subject_name"
              value={form.subject_name}
              onChange={handleChange}
              className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700 w-full"
              required
            >
              <option value="">Select subject</option>
              {availableSubjects.map((subj) => (
                <option key={subj} value={subj}>{subj}</option>
              ))}
            </select>
          </div>
          <select
            name="teacher_id"
            value={form.teacher_id}
            onChange={handleChange}
            className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700"
            required
          >
            <option value="">Select teacher ({staff.length} available)</option>
            {staff.length === 0 && (
              <option value="" disabled>Loading teachers...</option>
            )}
            {staff.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {teacher.username} {teacher.roles ? `(${teacher.roles.join(', ')})` : ''}
              </option>
            ))}
          </select>
          <select
            name="day_of_week"
            value={form.day_of_week}
            onChange={handleChange}
            className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700"
          >
            {DAY_OPTIONS.map((day) => (
              <option key={day} value={day}>{day}</option>
            ))}
          </select>
          <input
            type="time"
            name="start_time"
            value={form.start_time}
            onChange={handleChange}
            className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700"
          />
          <input
            type="time"
            name="end_time"
            value={form.end_time}
            onChange={handleChange}
            className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700"
          />
          <input
            type="text"
            name="location"
            value={form.location}
            onChange={handleChange}
            placeholder="Room (optional)"
            className="p-2 border rounded-lg bg-slate-50 font-semibold text-slate-700"
          />
          <button type="submit" className="lg:col-span-7 bg-blue-700 text-white py-2 rounded-lg font-bold hover:bg-blue-600">
            Add Timetable Slot
          </button>
        </form>
      )}

      {sortedEntries.length === 0 ? (
        <div className="text-sm text-slate-400">No timetable entries yet.</div>
      ) : (
        <div className="space-y-3">
          {sortedEntries.map((entry) => (
            <div key={entry.id} className="flex flex-wrap items-center justify-between gap-3 p-3 border rounded-lg bg-slate-50">
              <div>
                <p className="font-bold text-slate-800">{entry.class_name} • {entry.subject_name}</p>
                <p className="text-xs text-slate-500">{entry.day_of_week} • {entry.start_time} - {entry.end_time}</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-semibold text-slate-600">{entry.teacher_name || 'Unassigned'}</p>
                {entry.location && <p className="text-xs text-slate-400">Room: {entry.location}</p>}
              </div>
              {canManage && (
                <button
                  onClick={() => handleDelete(entry.id)}
                  className="text-xs font-bold text-red-600 hover:text-red-700"
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
