import React, { useEffect, useState } from 'react';
import axios from 'axios';
import BulkStatusUpdate from '../components/BulkStatusUpdate';
import PromotionThresholdManager from '../components/PromotionThresholdManager';
import useEffectiveSubscriptionPlan from '../hooks/useEffectiveSubscriptionPlan';

export default function AdmissionsPanel() {
  const { plan: subscriptionPlan } = useEffectiveSubscriptionPlan();
  const aiRegistrarIncluded = subscriptionPlan === 'Basic' || subscriptionPlan === 'Premium';
  const [formData, setFormData] = useState({
    first_name: '',
    surname: '',
    gender: 'Male',
    date_of_birth: '',
    student_code: '',
    guardian_name: '',
    parent_email: '',
    class_assigned: 'JHS 1',
    scholarship_type: 'none',
    scholarship_notes: '',
    score: 0 // Default for manual admission
  });
  const [csvFile, setCsvFile] = useState(null);
  const [applications, setApplications] = useState([]);
  const [applicationSummary, setApplicationSummary] = useState({});
  const [loadingApplications, setLoadingApplications] = useState(true);
  const [reviewNotes, setReviewNotes] = useState({});
  const [reviewClass, setReviewClass] = useState({});
  const [reviewFollowUp, setReviewFollowUp] = useState({});
  const [workflowDefaults, setWorkflowDefaults] = useState({
    visit_location: '',
    visit_contact_person: '',
    visit_contact_phone: ''
  });
  const [reviewingId, setReviewingId] = useState(null);

  // Promotion state
  const [promotionData, setPromotionData] = useState({
    student_id: '',
    new_class: 'JHS 2',
    remarks: ''
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  const validGrades = [
    "Nursery", "KG", 
    "Class 1", "Class 2", "Class 3", "Class 4", "Class 5", "Class 6",
    "JHS 1", "JHS 2", "JHS 3"
  ];

  const genderOptions = ['Male', 'Female', 'Other'];

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  useEffect(() => {
    fetchApplications();
  }, []);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const fetchApplications = async () => {
    try {
      setLoadingApplications(true);
      const res = await axios.get('/api/admissions/applications', { headers: getAuthHeaders() });
      setApplications(res.data.applications || []);
      setApplicationSummary(res.data.summary || {});
      setWorkflowDefaults(res.data.workflow_defaults || {
        visit_location: '',
        visit_contact_person: '',
        visit_contact_phone: ''
      });
    } catch (err) {
      console.error('Failed to fetch parent applications', err);
    } finally {
      setLoadingApplications(false);
    }
  };

  const handlePromotionChange = (e) => {
    setPromotionData({ ...promotionData, [e.target.name]: e.target.value });
  };

  const handleSearchStudent = async (query) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get(`/api/students/search?q=${encodeURIComponent(query)}`, { headers });
      setSearchResults(res.data.students || []);
    } catch (err) {
      console.error('Search error:', err);
    }
  };

  const selectStudent = (student) => {
    setPromotionData({
      ...promotionData,
      student_id: student.id
    });
    setSearchQuery(student.name);
    setSearchResults([]);
  };

  const openApplicationDocument = async (application, applicationDocument) => {
    if (!applicationDocument?.download_path) {
      alert('This document is not available to open.');
      return;
    }

    try {
      const res = await axios.get(applicationDocument.download_path, {
        headers: getAuthHeaders(),
        responseType: 'blob'
      });
      const contentType = res.headers['content-type'] || applicationDocument.content_type || 'application/octet-stream';
      const blob = new Blob([res.data], { type: contentType });
      const blobUrl = window.URL.createObjectURL(blob);
      const opened = window.open(blobUrl, '_blank', 'noopener,noreferrer');

      if (!opened) {
        const link = document.createElement('a');
        link.href = blobUrl;
        link.setAttribute('download', applicationDocument.original_filename || applicationDocument.filename || `${application.application_code}-document`);
        document.body.appendChild(link);
        link.click();
        link.remove();
      }

      window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to open the document.');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      await axios.post('/api/admissions/admit', formData, { headers });
      const fullName = `${formData.first_name} ${formData.surname}`;
      alert(`Student ${fullName} admitted successfully!`);
      setFormData({
        first_name: '',
        surname: '',
        gender: 'Male',
        date_of_birth: '',
        student_code: '',
        guardian_name: '',
        parent_email: '',
        class_assigned: 'JHS 1',
        scholarship_type: 'none',
        scholarship_notes: '',
        score: 0
      });
      fetchApplications();
    } catch (err) {
      alert(err.response?.data?.message || "Admission failed.");
    }
  };

  const handleBulkUpload = async () => {
    if (!csvFile) return alert("Please select a CSV file.");
    
    const uploadData = new FormData();
    uploadData.append('file', csvFile);

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id'),
        'Content-Type': 'multipart/form-data'
      };
      const res = await axios.post('/api/admissions/bulk-upload', uploadData, { headers });
      
      let msg = res.data.message;
      if (res.data.warnings && res.data.warnings.length > 0) {
        msg += "\n\n⚠️ WARNINGS:\n" + res.data.warnings.join("\n");
      }
      if (res.data.errors && res.data.errors.length > 0) {
        msg += "\n\n❌ ERRORS:\n" + res.data.errors.join("\n");
      }
      alert(msg);
      setCsvFile(null);
      fetchApplications();
    } catch (err) {
      alert(err.response?.data?.message || "Bulk upload failed.");
    }
  };

  const handleReviewApplication = async (application, action) => {
    try {
      setReviewingId(application.id);
      const payload = {
        action,
        notes: reviewNotes[application.id] || '',
      };
      if (action === 'approve') {
        payload.class_assigned = reviewClass[application.id] || application.preferred_class;
      }
      if (action === 'schedule_visit') {
        const followUp = reviewFollowUp[application.id] || {};
        payload.visit_date = followUp.visit_date || '';
        payload.visit_time = followUp.visit_time || '';
        payload.visit_location = followUp.visit_location || '';
        payload.visit_contact_person = followUp.visit_contact_person || '';
        payload.visit_contact_phone = followUp.visit_contact_phone || '';
      }
      const res = await axios.post(`/api/admissions/applications/${application.id}/review`, payload, {
        headers: getAuthHeaders()
      });
      alert(res.data.message);
      fetchApplications();
    } catch (err) {
      alert(err.response?.data?.message || 'Review action failed.');
    } finally {
      setReviewingId(null);
    }
  };

  const handlePromoteStudent = async (e) => {
    e.preventDefault();
    if (!promotionData.student_id) {
      alert("Please select a student");
      return;
    }

    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.post('/api/admissions/promote-student', promotionData, { headers });
      alert(res.data.message);
      setPromotionData({
        student_id: '',
        new_class: 'JHS 2',
        remarks: ''
      });
      setSearchQuery('');
    } catch (err) {
      alert(err.response?.data?.message || "Promotion failed.");
    }
  };

  return (
    <div className="space-y-8">
      {/* Bulk Status Update - End of Year Operations */}
      <div className="bg-linear-to-r from-blue-500 to-blue-600 p-6 rounded-3xl shadow-lg text-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-2xl font-black mb-2">⚡ Bulk Status Update</h3>
            <p className="text-blue-100">Update all students in a class (e.g., mark JHS 3 as Graduated after BECE)</p>
          </div>
          <BulkStatusUpdate trigger="modal" />
        </div>
      </div>

      {/* Promotion Configuration */}
      <div className="bg-linear-to-r from-indigo-500 to-purple-600 p-6 rounded-3xl shadow-lg text-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-2xl font-black mb-2">⚙️ Promotion Configuration</h3>
            <p className="text-indigo-100">Set performance requirements, then use manual override below when needed</p>
          </div>
          <PromotionThresholdManager />
        </div>
      </div>

      {/* Manual Admission Form */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <h2 className="text-2xl font-bold text-slate-800 mb-6">Manual Admission</h2>
        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">First Name</label>
            <input name="first_name" value={formData.first_name} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" required placeholder="e.g. Kofi" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Surname</label>
            <input name="surname" value={formData.surname} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" required placeholder="e.g. Mensah" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Gender</label>
            <select name="gender" value={formData.gender} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50">
              {genderOptions.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Date of Birth</label>
            <input name="date_of_birth" type="date" value={formData.date_of_birth} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Class Assigned</label>
            <select name="class_assigned" value={formData.class_assigned} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50">
              {validGrades.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Guardian Name</label>
            <input name="guardian_name" value={formData.guardian_name} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" placeholder="Parent/Guardian Name" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Parent Email</label>
            <input name="parent_email" type="email" value={formData.parent_email} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" placeholder="For notifications" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Scholarship</label>
            <select name="scholarship_type" value={formData.scholarship_type} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50">
              <option value="none">No Scholarship</option>
              <option value="tuition">Tuition Free</option>
              <option value="tuition_feeding">Tuition + Feeding Free</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-700 mb-2">Scholarship Notes</label>
            <input name="scholarship_notes" value={formData.scholarship_notes} onChange={handleChange} className="w-full p-3 border rounded-lg bg-slate-50" placeholder="Optional notes" />
          </div>
          <div className="md:col-span-2 pt-4">
              <button type="submit" className="bg-blue-900 text-white px-8 py-3 rounded-xl font-bold hover:bg-blue-800 w-full md:w-auto shadow-lg shadow-blue-200">Admit Student</button>
          </div>
        </form>
      </div>

      {/* AI Registrar Review Queue */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">AI Registrar Review Queue</h2>
            <p className="mt-1 text-sm text-slate-500">Review public parent applications, follow the AI recommendation, and convert approved applicants into students.</p>
          </div>
          <div className="flex flex-wrap gap-3 text-xs font-bold text-slate-600">
            {Object.entries(applicationSummary).map(([status, count]) => (
              <span key={status} className="rounded-full bg-slate-100 px-3 py-2">{status}: {count}</span>
            ))}
          </div>
        </div>

        {!aiRegistrarIncluded && (
          <div className="mt-4 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Approval decision PDFs are available on paid subscription plans where AI Registrar is included. Core admissions review still works.
          </div>
        )}

        {loadingApplications ? (
          <p className="mt-6 text-sm text-slate-500">Loading applications...</p>
        ) : applications.length === 0 ? (
          <p className="mt-6 text-sm text-slate-500">No parent applications submitted yet.</p>
        ) : (
          <div className="mt-6 space-y-4">
            {applications.map((application) => (
              <div key={application.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-black text-slate-900">{application.first_name} {application.surname}</h3>
                      <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-bold text-white">{application.status}</span>
                      <span className="rounded-full bg-cyan-100 px-3 py-1 text-xs font-bold text-cyan-700">Score {application.ai_readiness_score}</span>
                    </div>
                    <p className="mt-2 text-sm text-slate-500">{application.application_code} • Preferred Class: {application.preferred_class}</p>
                    <p className="mt-2 text-sm text-slate-700">{application.ai_summary}</p>
                    {(application.ai_missing_items || []).length > 0 && (
                      <p className="mt-2 text-xs font-semibold text-amber-700">Missing: {application.ai_missing_items.join(', ')}</p>
                    )}
                  </div>
                  <div className="rounded-2xl bg-white px-4 py-3 text-right">
                    <p className="text-xs font-bold uppercase text-slate-400">AI Recommendation</p>
                    <p className="mt-1 text-sm font-black text-slate-900">{application.ai_recommendation}</p>
                    <p className="mt-1 text-xs text-slate-500">{application.desired_test_mode} • {application.internet_quality}</p>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-xl bg-white p-4">
                    <p className="text-xs font-bold uppercase text-slate-400">Guardian Contact</p>
                    <p className="mt-2 text-sm text-slate-700">{application.guardian_name || 'Not recorded'}</p>
                    <p className="mt-1 text-sm text-slate-600">{application.parent_email || 'No email'} • {application.parent_phone || 'No phone'}</p>
                    <p className="mt-1 text-xs text-slate-500">Documents: {(application.document_manifest || []).length}</p>
                    {(application.document_manifest || []).length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(application.document_manifest || []).map((applicationDocument, index) => (
                          <button
                            key={applicationDocument.document_id || `${application.id}-${index}`}
                            type="button"
                            onClick={() => openApplicationDocument(application, applicationDocument)}
                            disabled={!applicationDocument.download_available}
                            className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {applicationDocument.category || 'document'}: {applicationDocument.original_filename || applicationDocument.filename || `Document ${index + 1}`}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="rounded-xl bg-white p-4">
                    <p className="text-xs font-bold uppercase text-slate-400">Reviewer Notes</p>
                    <p className="mt-1 text-xs text-slate-500">These notes appear on the parent's status page. Use them for visit instructions, test guidance, approval context, or rejection reasons.</p>
                    <textarea
                      value={reviewNotes[application.id] || ''}
                      onChange={(event) => setReviewNotes((current) => ({ ...current, [application.id]: event.target.value }))}
                      rows={3}
                      className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      placeholder="Add school review notes or parent follow-up guidance"
                    />
                    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <p className="text-xs font-bold uppercase text-slate-500">Visit Plan Details</p>
                      <p className="mt-1 text-xs text-slate-500">Used when you mark School Visit Required. Parents will see these details on their status page and in the review update.</p>
                      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                        <input
                          type="date"
                          value={reviewFollowUp[application.id]?.visit_date ?? application.follow_up_plan?.date ?? ''}
                          onChange={(event) => setReviewFollowUp((current) => ({
                            ...current,
                            [application.id]: {
                              ...(current[application.id] || {}),
                              visit_date: event.target.value,
                            },
                          }))}
                          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        />
                        <input
                          type="time"
                          value={reviewFollowUp[application.id]?.visit_time ?? application.follow_up_plan?.time ?? ''}
                          onChange={(event) => setReviewFollowUp((current) => ({
                            ...current,
                            [application.id]: {
                              ...(current[application.id] || {}),
                              visit_time: event.target.value,
                            },
                          }))}
                          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        />
                        <input
                          type="text"
                          value={reviewFollowUp[application.id]?.visit_location ?? application.follow_up_plan?.location ?? workflowDefaults.visit_location ?? ''}
                          onChange={(event) => setReviewFollowUp((current) => ({
                            ...current,
                            [application.id]: {
                              ...(current[application.id] || {}),
                              visit_location: event.target.value,
                            },
                          }))}
                          placeholder="Visit location"
                          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        />
                        <input
                          type="text"
                          value={reviewFollowUp[application.id]?.visit_contact_person ?? application.follow_up_plan?.contact_person ?? workflowDefaults.visit_contact_person ?? ''}
                          onChange={(event) => setReviewFollowUp((current) => ({
                            ...current,
                            [application.id]: {
                              ...(current[application.id] || {}),
                              visit_contact_person: event.target.value,
                            },
                          }))}
                          placeholder="Contact person"
                          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                        />
                        <input
                          type="text"
                          value={reviewFollowUp[application.id]?.visit_contact_phone ?? application.follow_up_plan?.contact_phone ?? workflowDefaults.visit_contact_phone ?? ''}
                          onChange={(event) => setReviewFollowUp((current) => ({
                            ...current,
                            [application.id]: {
                              ...(current[application.id] || {}),
                              visit_contact_phone: event.target.value,
                            },
                          }))}
                          placeholder="Contact phone"
                          className="rounded-lg border border-slate-300 px-3 py-2 text-sm md:col-span-2"
                        />
                      </div>
                    </div>
                    <select
                      value={reviewClass[application.id] || application.preferred_class}
                      onChange={(event) => setReviewClass((current) => ({ ...current, [application.id]: event.target.value }))}
                      className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    >
                      {validGrades.map((grade) => <option key={grade} value={grade}>{grade}</option>)}
                    </select>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button onClick={() => handleReviewApplication(application, 'approve')} disabled={reviewingId === application.id} className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-60">Approve & Admit</button>
                  <button onClick={() => handleReviewApplication(application, 'invite_test')} disabled={reviewingId === application.id} className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-60">Mark Online Test Path</button>
                  <button onClick={() => handleReviewApplication(application, 'schedule_visit')} disabled={reviewingId === application.id} className="rounded-xl bg-amber-500 px-4 py-2 text-xs font-bold text-white hover:bg-amber-600 disabled:opacity-60">Mark School Visit Required</button>
                  <button onClick={() => handleReviewApplication(application, 'request_correction')} disabled={reviewingId === application.id} className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-60">Request Correction</button>
                  <button onClick={() => handleReviewApplication(application, 'reject')} disabled={reviewingId === application.id} className="rounded-xl border border-red-300 px-4 py-2 text-xs font-bold text-red-700 hover:bg-red-50 disabled:opacity-60">Reject</button>
                  {application.decision_document?.available && (
                    <a
                      href={application.decision_document.download_url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-xl border border-cyan-300 bg-cyan-50 px-4 py-2 text-xs font-bold text-cyan-800 hover:bg-cyan-100"
                    >
                      Preview Approval PDF
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bulk Upload Section */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <h2 className="text-2xl font-bold text-slate-800 mb-6">Bulk Upload via CSV</h2>
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
          <input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files[0])} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
          <button onClick={handleBulkUpload} className="bg-green-600 text-white px-6 py-2 rounded-xl font-bold hover:bg-green-700 shadow-lg shadow-green-200 whitespace-nowrap">
            Upload CSV
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-4">
          <strong>Required Columns:</strong> first_name, surname, gender, class_assigned<br/>
          <strong>Optional:</strong> student_code (auto-generated if blank), guardian_name, parent_email
        </p>
      </div>

      {/* Class Promotion Override Section */}
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <h2 className="text-2xl font-bold text-slate-800 mb-2">📚 Promotion Override (Headmaster / Proprietor)</h2>
        <p className="text-sm text-slate-500 mb-6">Use this to override repetition and manually promote an individual student when necessary.</p>
        <form onSubmit={handlePromoteStudent} className="space-y-6">
          <div className="relative">
            <label className="block text-sm font-bold text-slate-700 mb-2">Search Student</label>
            <input 
              type="text"
              placeholder="Type student name to search..."
              value={searchQuery}
              onChange={(e) => handleSearchStudent(e.target.value)}
              className="w-full p-3 border rounded-lg bg-slate-50"
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
                {searchResults.map(student => (
                  <button
                    key={student.id}
                    type="button"
                    onClick={() => selectStudent(student)}
                    className="w-full text-left px-4 py-2 hover:bg-slate-100 border-b border-slate-100 last:border-b-0"
                  >
                    <div className="font-semibold text-slate-800">{student.name}</div>
                    <div className="text-xs text-slate-500">Current Class: {student.current_class} | ID: {student.student_code}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">New Class</label>
              <select name="new_class" value={promotionData.new_class} onChange={handlePromotionChange} className="w-full p-3 border rounded-lg bg-slate-50">
                {validGrades.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-bold text-slate-700 mb-2">Remarks (Optional)</label>
              <input 
                type="text"
                name="remarks"
                value={promotionData.remarks}
                onChange={handlePromotionChange}
                placeholder="e.g., Promoted based on Term 3 performance"
                className="w-full p-3 border rounded-lg bg-slate-50"
              />
            </div>
          </div>

          <button type="submit" className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-indigo-700 shadow-lg shadow-indigo-200 w-full md:w-auto">
            Promote Student
          </button>
        </form>
      </div>
    </div>
  );
}