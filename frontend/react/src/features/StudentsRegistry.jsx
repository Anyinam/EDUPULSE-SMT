import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import useSchoolClasses from '../hooks/useSchoolClasses';
import useSubscription from '../hooks/useSubscription';

const PROFILE_TABS = ['Profile', 'Academic', 'Guardian', 'Finance', 'Documents'];

const filterText = (value, query) => {
  if (!query) return true;
  if (value === null || value === undefined) return false;
  return String(value).toLowerCase().includes(query);
};

const toCsvValue = (value) => {
  const normalized = value === null || value === undefined ? '' : String(value);
  return `"${normalized.replace(/"/g, '""')}"`;
};

const formatCurrency = (value) => `GH₵ ${Number(value || 0).toLocaleString()}`;

const formatDate = (value) => {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
};

const getFeedingStatusLabel = (student) => {
  if (student?.feeding_pending_approval && !student?.feeding_paid) {
    return 'Awaiting approval';
  }
  if (!student?.feeding_paid) {
    return 'Outstanding';
  }
  if (student.feeding_frequency === 'Scholarship') {
    return 'Scholarship';
  }
  if (student.feeding_frequency) {
    return `${student.feeding_frequency} covered`;
  }
  return 'Paid up';
};

const getFeedingStatusMeta = (student) => {
  if (student?.feeding_pending_approval && !student?.feeding_paid) {
    return student.feeding_pending_amount
      ? `Recorded GH₵ ${Number(student.feeding_pending_amount).toLocaleString()} pending proprietor approval`
      : 'Recorded pending proprietor approval';
  }
  if (!student?.feeding_paid) {
    return null;
  }
  if (student.payment_method && student.payment_method !== 'Scholarship') {
    if (student.feeding_coverage_until) {
      return `${student.payment_method} until ${formatDate(student.feeding_coverage_until)}`;
    }
    return student.payment_method;
  }
  if (student.feeding_coverage_until) {
    return `Until ${formatDate(student.feeding_coverage_until)}`;
  }
  return null;
};

const getInitials = (name) => {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return 'ST';
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() || '').join('');
};

const buildTrendPolyline = (points) => {
  if (!points.length) return '';
  if (points.length === 1) return '8,42 112,42';

  const maxValue = Math.max(...points.map((point) => Number(point.term_average || 0)), 1);
  const minValue = Math.min(...points.map((point) => Number(point.term_average || 0)), 0);
  const range = Math.max(maxValue - minValue, 1);

  return points
    .map((point, index) => {
      const x = 8 + (index * 104) / Math.max(points.length - 1, 1);
      const normalized = (Number(point.term_average || 0) - minValue) / range;
      const y = 42 - (normalized * 32);
      return `${x},${y}`;
    })
    .join(' ');
};

export default function StudentsRegistry() {
  const { hasFeature } = useSubscription();
  const canTrackPayments = hasFeature('payment_tracking');
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [classFilter, setClassFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [editingStudent, setEditingStudent] = useState(null);
  const [editData, setEditData] = useState({});
  const [profileStudent, setProfileStudent] = useState(null);
  const [profileTab, setProfileTab] = useState('Profile');
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [profileReports, setProfileReports] = useState([]);
  const [profilePayments, setProfilePayments] = useState([]);
  const [profilePromotions, setProfilePromotions] = useState([]);
  const [profileDocuments, setProfileDocuments] = useState([]);
  const [studentOwnedDocuments, setStudentOwnedDocuments] = useState([]);
  const [admissionLinkedDocuments, setAdmissionLinkedDocuments] = useState([]);
  const [documentUploadFiles, setDocumentUploadFiles] = useState([]);
  const [documentUploadCategory, setDocumentUploadCategory] = useState('document');
  const [documentUploadNote, setDocumentUploadNote] = useState('');
  const [documentUploadBusy, setDocumentUploadBusy] = useState(false);
  const { classes: schoolClasses } = useSchoolClasses();

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  useEffect(() => {
    const fetchStudents = async () => {
      setLoading(true);
      try {
        const headers = getAuthHeaders();
        const res = await axios.get('/api/students?include_inactive=true', { headers });
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
    const uniqueClasses = Array.from(new Set([
      ...schoolClasses,
      ...students.map((student) => student.current_class).filter(Boolean),
    ])).sort();
    return ['All', ...uniqueClasses];
  }, [schoolClasses, students]);

  const editableClassOptions = useMemo(() => (
    Array.from(new Set([
      ...schoolClasses,
      ...students.map((student) => student.current_class).filter(Boolean),
      editData.current_class,
    ].filter(Boolean))).sort()
  ), [schoolClasses, students, editData.current_class]);

  const studentStatusCounts = useMemo(() => {
    return students.reduce((summary, student) => {
      const status = student.status || 'Active';
      summary.all += 1;
      if (status === 'Graduated') {
        summary.graduated += 1;
      } else if (status === 'Active') {
        summary.active += 1;
      } else {
        summary.archive += 1;
      }
      return summary;
    }, {
      all: 0,
      active: 0,
      graduated: 0,
      archive: 0,
    });
  }, [students]);

  const filteredStudents = useMemo(() => {
    return students.filter((student) => {
      const matchesClass = classFilter === 'All' || student.current_class === classFilter;
      if (!matchesClass) return false;

      const studentStatus = student.status || 'Active';
      const matchesStatus = statusFilter === 'All'
        || (statusFilter === 'Active' && studentStatus === 'Active')
        || (statusFilter === 'Graduated' && studentStatus === 'Graduated')
        || (statusFilter === 'Archive' && !['Active', 'Graduated'].includes(studentStatus));
      if (!matchesStatus) return false;

      return (
        filterText(student.name, normalizedQuery) ||
        filterText(student.student_code, normalizedQuery) ||
        filterText(student.current_class, normalizedQuery) ||
        filterText(student.is_on_scholarship ? (student.scholarship_covers_feeding ? 'tuition feeding scholarship' : 'tuition scholarship') : 'none', normalizedQuery) ||
        filterText(student.guardian_name, normalizedQuery) ||
        filterText(student.parent_email, normalizedQuery) ||
        filterText(student.parent_phone, normalizedQuery) ||
        filterText(student.status, normalizedQuery)
      );
    });
  }, [students, classFilter, normalizedQuery, statusFilter]);

  const handleDelete = async (student) => {
    if (!window.confirm(`Are you sure you want to delete ${student.name} (${student.student_code})? This cannot be undone.`)) {
      return;
    }

    try {
      const headers = getAuthHeaders();
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
      const headers = getAuthHeaders();
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

  const openStudentProfile = async (student) => {
    setProfileStudent(student);
    setProfileTab('Profile');
    setProfileLoading(true);
    setProfileError('');
    setProfileReports([]);
    setProfilePayments([]);
    setProfilePromotions([]);
    setProfileDocuments([]);
    setStudentOwnedDocuments([]);
    setAdmissionLinkedDocuments([]);
    setDocumentUploadFiles([]);
    setDocumentUploadCategory('document');
    setDocumentUploadNote('');

    try {
      const headers = getAuthHeaders();
      const [reportsRes, paymentsRes, promotionsRes, documentsRes] = await Promise.all([
        axios.get(`/api/students/${student.id}/reports`, { headers }),
        canTrackPayments ? axios.get(`/api/students/${student.id}/payments`, { headers }) : Promise.resolve({ data: [] }),
        axios.get(`/api/students/${student.id}/promotions`, { headers }),
        axios.get(`/api/students/${student.id}/documents`, { headers }),
      ]);

      setProfileReports(reportsRes.data || []);
      setProfilePayments(paymentsRes.data || []);
      setProfilePromotions(promotionsRes.data?.promotions || []);
      setProfileDocuments(documentsRes.data?.documents || []);
      setStudentOwnedDocuments(documentsRes.data?.student_documents || []);
      setAdmissionLinkedDocuments(documentsRes.data?.admission_documents || []);
    } catch (err) {
      setProfileError(err.response?.data?.message || 'Failed to load student profile details.');
    } finally {
      setProfileLoading(false);
    }
  };

  const openProfileDocument = async (documentItem) => {
    if (!documentItem?.download_path) {
      alert('This document is not available to open.');
      return;
    }

    try {
      const res = await axios.get(documentItem.download_path, {
        headers: getAuthHeaders(),
        responseType: 'blob'
      });
      const contentType = res.headers['content-type'] || documentItem.content_type || 'application/octet-stream';
      const blob = new Blob([res.data], { type: contentType });
      const blobUrl = window.URL.createObjectURL(blob);
      const opened = window.open(blobUrl, '_blank', 'noopener,noreferrer');

      if (!opened) {
        const link = document.createElement('a');
        link.href = blobUrl;
        link.setAttribute('download', documentItem.original_filename || documentItem.filename || 'student-document');
        document.body.appendChild(link);
        link.click();
        link.remove();
      }

      window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to open document.');
    }
  };

  const handleUploadStudentDocuments = async () => {
    if (!profileStudent || documentUploadFiles.length === 0) {
      alert('Select at least one document to upload.');
      return;
    }

    setDocumentUploadBusy(true);
    try {
      const payload = new FormData();
      documentUploadFiles.forEach((file) => payload.append('documents', file));
      payload.append('category', documentUploadCategory);
      payload.append('note', documentUploadNote);

      const res = await axios.post(`/api/students/${profileStudent.id}/documents`, payload, {
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'multipart/form-data'
        }
      });

      setStudentOwnedDocuments(res.data?.documents || []);
      setProfileDocuments([...(res.data?.documents || []), ...admissionLinkedDocuments]);
      setDocumentUploadFiles([]);
      setDocumentUploadCategory('document');
      setDocumentUploadNote('');

      if (res.data?.profile_picture) {
        setProfileStudent((current) => current ? { ...current, profile_picture: res.data.profile_picture } : current);
        setStudents((current) => current.map((student) => (
          student.id === profileStudent.id ? { ...student, profile_picture: res.data.profile_picture } : student
        )));
      }
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to upload student documents.');
    } finally {
      setDocumentUploadBusy(false);
    }
  };

  const trendSummary = useMemo(() => {
    if (profileReports.length < 2) return null;
    const latest = Number(profileReports[profileReports.length - 1]?.term_average || 0);
    const previous = Number(profileReports[profileReports.length - 2]?.term_average || 0);
    const delta = Number((latest - previous).toFixed(1));
    return {
      delta,
      direction: delta > 0 ? 'Improving' : delta < 0 ? 'Declining' : 'Stable',
    };
  }, [profileReports]);

  const latestReport = profileReports[profileReports.length - 1] || null;
  const outstandingPayments = profilePayments.filter((payment) => payment.status === 'Pending');
  const totalConfirmedPayments = profilePayments
    .filter((payment) => payment.status === 'Confirmed')
    .reduce((sum, payment) => sum + Number(payment.amount || 0), 0);
  const profileTrendLine = buildTrendPolyline(profileReports);
  const profileDocumentCards = profileStudent ? [
    {
      title: 'Identity Record',
      status: profileStudent.name && profileStudent.student_code ? 'Ready' : 'Incomplete',
      description: 'Core student identity details used across attendance, reports, and billing.',
      detail: `${profileStudent.name || 'Name missing'} • ${profileStudent.student_code || 'Code missing'}`,
    },
    {
      title: 'Academic Evidence',
      status: profileReports.length > 0 ? 'Available' : 'Awaiting records',
      description: 'Published report-card history and trend evidence for progression reviews.',
      detail: profileReports.length > 0
        ? `${profileReports.length} term record${profileReports.length === 1 ? '' : 's'} captured`
        : 'No report-card entries have been published yet.',
    },
    {
      title: 'Guardian Authorization Pack',
      status: profileStudent.guardian_name && (profileStudent.parent_phone || profileStudent.parent_email) ? 'Reachable' : 'Needs update',
      description: 'Guardian contact channels needed for notices, approvals, and escalation.',
      detail: `${profileStudent.guardian_name || 'Guardian missing'} • ${profileStudent.parent_phone || profileStudent.parent_email || 'No contact channel'}`,
    },
    {
      title: 'Finance Standing',
      status: Number(profileStudent.total_tuition_owed || 0) > 0 ? 'Attention needed' : 'Clear',
      description: 'Current tuition standing and payment activity summary for administrative review.',
      detail: `${formatCurrency(profileStudent.total_tuition_owed)} outstanding • ${profilePayments.length} payment entr${profilePayments.length === 1 ? 'y' : 'ies'}`,
    },
    {
      title: 'Document Vault',
      status: profileDocuments.length > 0 ? 'Available' : 'Awaiting records',
      description: 'Birth certificates, admissions evidence, consent records, and scanned attachments linked to the learner.',
      detail: profileDocuments.length > 0
        ? `${profileDocuments.length} linked document${profileDocuments.length === 1 ? '' : 's'} available`
        : 'No stored student or admissions documents yet.',
    },
  ].filter((item) => canTrackPayments || item.title !== 'Finance Standing') : [];

  const handleExport = () => {
    if (!filteredStudents.length) {
      alert('No students to export.');
      return;
    }

    const headers = [
      'Name',
      'Student Code',
      'Class',
      'Class Status',
      'Enrollment Status',
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
      student.class_status || student.current_class || '',
      student.status || 'Active',
      student.date_of_birth || '',
      student.age ?? '',
      student.gender || '',
      student.is_on_scholarship
        ? (student.scholarship_covers_feeding ? 'Tuition + Feeding' : 'Tuition')
        : 'None',
      student.guardian_name,
      student.parent_email,
      student.parent_phone,
      getFeedingStatusLabel(student),
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

      <div className="mb-6 grid gap-3 md:grid-cols-4">
        <button
          type="button"
          onClick={() => setStatusFilter('All')}
          className={`rounded-2xl border px-4 py-3 text-left transition ${statusFilter === 'All' ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300'}`}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-70">Full Registry</p>
          <p className="mt-2 text-2xl font-black">{studentStatusCounts.all}</p>
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('Active')}
          className={`rounded-2xl border px-4 py-3 text-left transition ${statusFilter === 'Active' ? 'border-emerald-600 bg-emerald-600 text-white' : 'border-emerald-200 bg-emerald-50 text-emerald-900 hover:border-emerald-300'}`}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-70">Active</p>
          <p className="mt-2 text-2xl font-black">{studentStatusCounts.active}</p>
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('Graduated')}
          className={`rounded-2xl border px-4 py-3 text-left transition ${statusFilter === 'Graduated' ? 'border-blue-600 bg-blue-600 text-white' : 'border-blue-200 bg-blue-50 text-blue-900 hover:border-blue-300'}`}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-70">Graduates</p>
          <p className="mt-2 text-2xl font-black">{studentStatusCounts.graduated}</p>
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter('Archive')}
          className={`rounded-2xl border px-4 py-3 text-left transition ${statusFilter === 'Archive' ? 'border-amber-600 bg-amber-600 text-white' : 'border-amber-200 bg-amber-50 text-amber-900 hover:border-amber-300'}`}
        >
          <p className="text-xs font-bold uppercase tracking-[0.2em] opacity-70">Other Inactive</p>
          <p className="mt-2 text-2xl font-black">{studentStatusCounts.archive}</p>
        </button>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
        <span>Showing {filteredStudents.length} of {students.length} students{statusFilter === 'Graduated' ? ' in Graduates' : statusFilter === 'Archive' ? ' in Other Inactive' : statusFilter === 'Active' ? ' in Active' : ''}</span>
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
                <th className="p-3 font-semibold">Class Status</th>
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
                  <td colSpan={14} className="p-6 text-center text-slate-400">No students found.</td>
                </tr>
              )}
              {filteredStudents.map((student, index) => (
                <tr
                  key={student.id}
                  onClick={() => openStudentProfile(student)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      openStudentProfile(student);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  className={index % 2 === 0 ? 'bg-white' : 'bg-slate-50'}
                >
                  <td className="p-3 font-medium text-slate-800">{student.name}</td>
                  <td className="p-3 text-slate-600">{student.student_code}</td>
                  <td className="p-3 text-slate-600">{student.current_class}</td>
                  <td className="p-3 text-slate-600">{student.class_status || student.status || student.current_class || '-'}</td>
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
                    <div>
                      <span className={student.feeding_paid ? 'text-emerald-600 font-semibold' : 'text-rose-500 font-semibold'}>
                        {getFeedingStatusLabel(student)}
                      </span>
                      {getFeedingStatusMeta(student) ? (
                        <p className="mt-1 text-xs text-slate-500">{getFeedingStatusMeta(student)}</p>
                      ) : null}
                    </div>
                  </td>
                  <td className="p-3">
                    <span className={student.is_present ? 'text-emerald-600 font-semibold' : 'text-slate-400 font-semibold'}>
                      {student.is_present ? 'Yes' : 'No'}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          openStudentProfile(student);
                        }}
                        className="bg-slate-900 text-white px-3 py-1 rounded-lg text-sm font-semibold hover:bg-slate-800 transition"
                        title="Open full student profile"
                      >
                        View
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          handleEditClick(student);
                        }}
                        className="bg-blue-100 text-blue-600 px-3 py-1 rounded-lg text-sm font-semibold hover:bg-blue-200 transition"
                        title="Edit student information"
                      >
                        ✎️ Edit
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          handleDelete(student);
                        }}
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
                <option value="">{editableClassOptions.length > 0 ? 'Select class' : 'No school classes configured'}</option>
                {editableClassOptions.map((className) => (
                  <option key={className} value={className}>{className}</option>
                ))}
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

    {profileStudent && (
      <div className="fixed inset-0 z-50 bg-slate-950/60 p-4">
        <div className="mx-auto flex h-full max-w-6xl items-center justify-center">
          <div className="max-h-[92vh] w-full overflow-hidden rounded-4xl bg-white shadow-2xl">
            <div className="border-b border-slate-200 bg-linear-to-r from-slate-900 via-slate-800 to-blue-900 px-8 py-7 text-white">
              <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-5">
                  {profileStudent.profile_picture ? (
                    <img
                      src={profileStudent.profile_picture}
                      alt={`${profileStudent.name} profile`}
                      className="h-24 w-24 rounded-[1.75rem] object-cover ring-2 ring-white/20"
                    />
                  ) : (
                    <div className="flex h-24 w-24 items-center justify-center rounded-[1.75rem] bg-white/10 text-3xl font-black tracking-wide text-white">
                      {getInitials(profileStudent.name)}
                    </div>
                  )}
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.3em] text-blue-200">Student Profile</p>
                    <h2 className="mt-2 text-3xl font-black">{profileStudent.name}</h2>
                    <div className="mt-3 flex flex-wrap gap-2 text-sm text-slate-100">
                      <span className="rounded-full bg-white/10 px-3 py-1">ID: {profileStudent.student_code || 'Not assigned'}</span>
                      <span className="rounded-full bg-white/10 px-3 py-1">Class: {profileStudent.current_class || 'Not assigned'}</span>
                      <span className="rounded-full bg-white/10 px-3 py-1">Gender: {profileStudent.gender || 'Not recorded'}</span>
                      <span className="rounded-full bg-white/10 px-3 py-1">Age: {profileStudent.age ?? 'N/A'}</span>
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 lg:w-[24rem]">
                  <div className="rounded-2xl bg-white/10 p-4">
                    <p className="text-xs uppercase tracking-wide text-blue-100">Latest Average</p>
                    <p className="mt-2 text-3xl font-black">{latestReport ? `${latestReport.term_average}%` : 'N/A'}</p>
                  </div>
                  {canTrackPayments && <div className="rounded-2xl bg-white/10 p-4">
                    <p className="text-xs uppercase tracking-wide text-blue-100">Outstanding Tuition</p>
                    <p className="mt-2 text-3xl font-black">{formatCurrency(profileStudent.total_tuition_owed)}</p>
                  </div>}
                </div>
              </div>
            </div>

            <div className="border-b border-slate-200 bg-slate-50 px-8 py-4">
              <div className="flex flex-wrap items-center gap-3">
                {PROFILE_TABS.filter((tab) => canTrackPayments || tab !== 'Finance').map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setProfileTab(tab)}
                    className={`rounded-full px-4 py-2 text-sm font-bold transition ${profileTab === tab ? 'bg-slate-900 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'}`}
                  >
                    {tab}
                  </button>
                ))}
                <button
                  onClick={() => setProfileStudent(null)}
                  className="ml-auto rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-100"
                >
                  Close
                </button>
              </div>
            </div>

            <div className="max-h-[64vh] overflow-y-auto px-8 py-6">
              {profileLoading && <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">Loading student profile...</div>}
              {!profileLoading && profileError && <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{profileError}</div>}

              {!profileLoading && !profileError && profileTab === 'Profile' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Attendance Flag</p>
                      <p className="mt-2 text-lg font-black text-slate-900">{profileStudent.is_present ? 'Present today' : 'Not marked present'}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Feeding Status</p>
                      <p className="mt-2 text-lg font-black text-slate-900">{getFeedingStatusLabel(profileStudent)}</p>
                      {getFeedingStatusMeta(profileStudent) ? (
                        <p className="mt-1 text-sm text-slate-500">{getFeedingStatusMeta(profileStudent)}</p>
                      ) : null}
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Scholarship</p>
                      <p className="mt-2 text-lg font-black text-slate-900">{profileStudent.is_on_scholarship ? 'Active' : 'None'}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Profile Completeness</p>
                      <p className="mt-2 text-lg font-black text-slate-900">{[profileStudent.date_of_birth, profileStudent.gender, profileStudent.guardian_name, profileStudent.parent_phone].filter(Boolean).length}/4</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                    <div className="rounded-3xl border border-slate-200 p-6">
                      <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Identity</p>
                      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Full Name</p>
                          <p className="mt-2 text-lg font-bold text-slate-900">{profileStudent.name}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Student Code</p>
                          <p className="mt-2 text-lg font-bold text-slate-900">{profileStudent.student_code || 'Not assigned'}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Date of Birth</p>
                          <p className="mt-2 text-lg font-bold text-slate-900">{formatDate(profileStudent.date_of_birth)}</p>
                        </div>
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Current Class</p>
                          <p className="mt-2 text-lg font-bold text-slate-900">{profileStudent.current_class || 'Not assigned'}</p>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6">
                      <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Current Snapshot</p>
                      <div className="mt-4 space-y-4">
                        <div className="rounded-2xl bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Academic Trend</p>
                          <p className="mt-2 text-lg font-black text-slate-900">{trendSummary ? `${trendSummary.direction} ${trendSummary.delta > 0 ? '+' : ''}${trendSummary.delta}` : 'Awaiting multiple term records'}</p>
                        </div>
                        <div className="rounded-2xl bg-white p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Recent Promotion</p>
                          <p className="mt-2 text-lg font-black text-slate-900">{profilePromotions[0] ? `${profilePromotions[0].from_class} -> ${profilePromotions[0].to_class}` : 'No promotion history yet'}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {!profileLoading && !profileError && profileTab === 'Academic' && (
                <div className="space-y-6">
                  <div className="rounded-3xl border border-slate-200 p-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Performance Trend</p>
                        <h3 className="mt-2 text-2xl font-black text-slate-900">Term Average Journey</h3>
                      </div>
                      <div className="rounded-2xl bg-slate-900 px-4 py-3 text-sm font-bold text-white">
                        {trendSummary ? `${trendSummary.direction} ${trendSummary.delta > 0 ? '+' : ''}${trendSummary.delta} pts` : 'Need 2+ reports'}
                      </div>
                    </div>

                    {profileReports.length > 0 ? (
                      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_0.9fr]">
                        <div className="rounded-2xl bg-slate-50 p-5">
                          <svg viewBox="0 0 120 48" className="h-52 w-full overflow-visible">
                            <path d="M8 42 H112" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4" fill="none" />
                            <polyline points={profileTrendLine} fill="none" stroke="#0f172a" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
                            {profileReports.map((point, index) => {
                              const coords = profileTrendLine.split(' ')[index]?.split(',') || [];
                              return (
                                <g key={`${point.academic_year}-${point.academic_term}`}>
                                  <circle cx={coords[0]} cy={coords[1]} r="2.8" fill="#2563eb" />
                                  <text x={coords[0]} y="46" textAnchor="middle" fontSize="4" fill="#475569">{point.academic_term.replace('Term ', 'T')}</text>
                                </g>
                              );
                            })}
                          </svg>
                        </div>

                        <div className="space-y-3">
                          {profileReports.slice().reverse().map((report) => (
                            <div key={`${report.academic_year}-${report.academic_term}`} className="rounded-2xl border border-slate-200 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <p className="text-sm font-bold text-slate-900">{report.academic_term}</p>
                                  <p className="text-xs text-slate-500">{report.academic_year}</p>
                                </div>
                                <div className="text-right">
                                  <p className="text-2xl font-black text-slate-900">{report.term_average}%</p>
                                  <p className="text-xs text-slate-500">{report.overall_position || 'No rank'}{report.out_of_students ? ` / ${report.out_of_students}` : ''}</p>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className="mt-6 text-sm text-slate-500">No report-card history has been published for this student yet.</p>
                    )}
                  </div>

                  <div className="rounded-3xl border border-slate-200 p-6">
                    <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Past Academic Records</p>
                    <div className="mt-4 overflow-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-left text-slate-500">
                          <tr>
                            <th className="px-4 py-3 font-semibold">Academic Year</th>
                            <th className="px-4 py-3 font-semibold">Term</th>
                            <th className="px-4 py-3 font-semibold">Average</th>
                            <th className="px-4 py-3 font-semibold">Position</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profileReports.length === 0 && (
                            <tr>
                              <td colSpan={4} className="px-4 py-6 text-center text-slate-400">No academic records yet.</td>
                            </tr>
                          )}
                          {profileReports.map((report) => (
                            <tr key={`${report.academic_year}-${report.academic_term}`} className="border-t border-slate-100">
                              <td className="px-4 py-3">{report.academic_year}</td>
                              <td className="px-4 py-3">{report.academic_term}</td>
                              <td className="px-4 py-3 font-bold text-slate-900">{report.term_average}%</td>
                              <td className="px-4 py-3 text-slate-600">{report.overall_position || '-'}{report.out_of_students ? ` of ${report.out_of_students}` : ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-slate-200 p-6">
                    <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Promotion History</p>
                    <div className="mt-4 space-y-3">
                      {profilePromotions.length === 0 && <p className="text-sm text-slate-500">No promotion history recorded yet.</p>}
                      {profilePromotions.map((promotion) => (
                        <div key={promotion.id} className="rounded-2xl bg-slate-50 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-sm font-bold text-slate-900">{promotion.from_class} {'->'} {promotion.to_class}</p>
                            <p className="text-xs text-slate-500">{formatDate(promotion.date)}</p>
                          </div>
                          <p className="mt-2 text-xs text-slate-600">Promoted by {promotion.promoted_by || 'System'}</p>
                          {promotion.remarks && <p className="mt-2 text-sm text-slate-700">{promotion.remarks}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {!profileLoading && !profileError && profileTab === 'Guardian' && (
                <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1fr]">
                  <div className="rounded-3xl border border-slate-200 p-6">
                    <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Guardian Contact</p>
                    <div className="mt-5 space-y-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Guardian</p>
                        <p className="mt-1 text-lg font-bold text-slate-900">{profileStudent.guardian_name || profileStudent.parent_name || 'Not recorded'}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Phone</p>
                        <p className="mt-1 text-lg font-bold text-slate-900">{profileStudent.parent_phone || 'Not recorded'}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Email</p>
                        <p className="mt-1 text-lg font-bold text-slate-900">{profileStudent.parent_email || 'Not recorded'}</p>
                      </div>
                    </div>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6">
                    <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Support Notes</p>
                    <div className="mt-5 space-y-4">
                      <div className="rounded-2xl bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Scholarship Coverage</p>
                        <p className="mt-2 text-lg font-black text-slate-900">
                          {profileStudent.is_on_scholarship
                            ? (profileStudent.scholarship_covers_feeding ? 'Tuition and feeding covered' : 'Tuition covered')
                            : 'No scholarship recorded'}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-white p-4">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Scholarship Notes</p>
                        <p className="mt-2 text-sm text-slate-700">{profileStudent.scholarship_notes || 'No scholarship notes recorded.'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {canTrackPayments && !profileLoading && !profileError && profileTab === 'Finance' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Outstanding Tuition</p>
                      <p className="mt-2 text-3xl font-black text-slate-900">{formatCurrency(profileStudent.total_tuition_owed)}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Confirmed Collections</p>
                      <p className="mt-2 text-3xl font-black text-slate-900">{formatCurrency(totalConfirmedPayments)}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Pending Entries</p>
                      <p className="mt-2 text-3xl font-black text-slate-900">{outstandingPayments.length}</p>
                    </div>
                  </div>

                  <div className="rounded-3xl border border-slate-200 p-6">
                    <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Payment Timeline</p>
                    <div className="mt-4 overflow-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50 text-left text-slate-500">
                          <tr>
                            <th className="px-4 py-3 font-semibold">Date</th>
                            <th className="px-4 py-3 font-semibold">Type</th>
                            <th className="px-4 py-3 font-semibold">Method</th>
                            <th className="px-4 py-3 font-semibold">Amount</th>
                            <th className="px-4 py-3 font-semibold">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {profilePayments.length === 0 && (
                            <tr>
                              <td colSpan={5} className="px-4 py-6 text-center text-slate-400">No payment history recorded yet.</td>
                            </tr>
                          )}
                          {profilePayments.map((payment) => (
                            <tr key={payment.id} className="border-t border-slate-100">
                              <td className="px-4 py-3 text-slate-600">{payment.date_paid}</td>
                              <td className="px-4 py-3 font-medium text-slate-900">{payment.payment_type}</td>
                              <td className="px-4 py-3 text-slate-600">{payment.method}</td>
                              <td className="px-4 py-3 font-bold text-slate-900">{formatCurrency(payment.amount)}</td>
                              <td className="px-4 py-3">
                                <span className={`rounded-full px-3 py-1 text-xs font-bold ${payment.status === 'Confirmed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                                  {payment.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {!profileLoading && !profileError && profileTab === 'Documents' && (
                <div className="space-y-6">
                  <div className="rounded-3xl border border-slate-200 p-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Student Dossier</p>
                        <h3 className="mt-2 text-2xl font-black text-slate-900">Administrative and academic packet</h3>
                      </div>
                      <div className="rounded-2xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
                        Upload new learner files here, and keep parent-admissions attachments linked for later staff review.
                      </div>
                    </div>

                    <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
                      {profileDocumentCards.map((card) => (
                        <div key={card.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="text-lg font-black text-slate-900">{card.title}</p>
                              <p className="mt-2 text-sm text-slate-600">{card.description}</p>
                            </div>
                            <span className={`rounded-full px-3 py-1 text-xs font-bold ${card.status === 'Ready' || card.status === 'Available' || card.status === 'Reachable' || card.status === 'Clear' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                              {card.status}
                            </span>
                          </div>
                          <p className="mt-4 text-sm font-medium text-slate-800">{card.detail}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-3xl border border-slate-200 p-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Upload Records</p>
                        <h3 className="mt-2 text-2xl font-black text-slate-900">Add documents to this learner profile</h3>
                      </div>
                      <button
                        onClick={handleUploadStudentDocuments}
                        disabled={documentUploadBusy || documentUploadFiles.length === 0}
                        className="rounded-2xl bg-slate-900 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {documentUploadBusy ? 'Uploading...' : 'Upload Documents'}
                      </button>
                    </div>

                    <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-[0.8fr_1.2fr]">
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Category</label>
                        <select
                          value={documentUploadCategory}
                          onChange={(event) => setDocumentUploadCategory(event.target.value)}
                          className="mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900"
                        >
                          <option value="document">General Document</option>
                          <option value="birth_certificate">Birth Certificate</option>
                          <option value="admission_form">Admission Form</option>
                          <option value="consent_letter">Consent Letter</option>
                          <option value="previous_report">Scanned Report</option>
                          <option value="identity_document">Identity Document</option>
                          <option value="medical_record">Medical Record</option>
                          <option value="passport_photo">Passport Photo</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Staff Note</label>
                        <input
                          value={documentUploadNote}
                          onChange={(event) => setDocumentUploadNote(event.target.value)}
                          placeholder="Optional note about what this document is for"
                          className="mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900"
                        />
                      </div>
                    </div>

                    <div className="mt-4 rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-5">
                      <input
                        type="file"
                        multiple
                        onChange={(event) => setDocumentUploadFiles(Array.from(event.target.files || []))}
                        className="w-full text-sm text-slate-700 file:mr-4 file:rounded-full file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-bold file:text-white hover:file:bg-slate-800"
                      />
                      <p className="mt-3 text-xs text-slate-500">Upload birth certificates, admission forms, consent letters, scanned report cards, or other learner records.</p>
                      {documentUploadFiles.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {documentUploadFiles.map((file) => (
                            <span key={`${file.name}-${file.size}-${file.lastModified}`} className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
                              {file.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1fr]">
                    <div className="rounded-3xl border border-slate-200 p-6">
                      <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Stored Learner Documents</p>
                      <div className="mt-4 space-y-3">
                        {profileDocuments.length === 0 && (
                          <p className="text-sm text-slate-500">No student-owned or linked admissions documents are stored yet.</p>
                        )}
                        {profileDocuments.map((documentItem) => (
                          <button
                            key={`${documentItem.source || 'student'}-${documentItem.document_id}`}
                            type="button"
                            onClick={() => openProfileDocument(documentItem)}
                            className="flex w-full items-center justify-between rounded-2xl bg-slate-50 px-4 py-3 text-left transition hover:bg-slate-100"
                          >
                            <div>
                              <p className="text-sm font-medium text-slate-800">{documentItem.original_filename || documentItem.filename || 'Document'}</p>
                              <p className="mt-1 text-xs text-slate-500">
                                {(documentItem.category || 'document').replaceAll('_', ' ')} • {documentItem.source === 'parent_admission' ? (documentItem.source_label || 'Parent admission') : 'Student profile upload'}
                              </p>
                              {documentItem.note ? <p className="mt-1 text-xs text-slate-600">{documentItem.note}</p> : null}
                            </div>
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-700 ring-1 ring-slate-200">Open</span>
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6">
                      <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">Profile Completion Signal</p>
                      <div className="mt-5 rounded-3xl bg-white p-5">
                        <div className="flex items-center justify-between text-sm font-semibold text-slate-600">
                          <span>Operational completeness</span>
                          <span>{Math.round((profileDocumentCards.filter((card) => ['Ready', 'Available', 'Reachable', 'Clear'].includes(card.status)).length / Math.max(profileDocumentCards.length, 1)) * 100)}%</span>
                        </div>
                        <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-slate-900"
                            style={{ width: `${Math.round((profileDocumentCards.filter((card) => ['Ready', 'Available', 'Reachable', 'Clear'].includes(card.status)).length / Math.max(profileDocumentCards.length, 1)) * 100)}%` }}
                          />
                        </div>
                        <p className="mt-4 text-sm text-slate-600">
                          This gives staff a quick sense of whether the learner's identity, academic, guardian, and finance records are complete enough for confident follow-up.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
