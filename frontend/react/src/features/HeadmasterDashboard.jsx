import React, { useState, useEffect } from 'react';
import axios from 'axios';
import TimetableManager from '../components/TimetableManager';
import PerformanceAnalytics from '../components/PerformanceAnalytics';
import BulkStatusUpdate from '../components/BulkStatusUpdate';
import TeacherAlerts from '../components/TeacherAlerts';
import PromotionHistoryModal from '../components/PromotionHistoryModal';
import ExamInboxPanel from '../components/ExamInboxPanel';
import StudentsRegistry from './StudentsRegistry';

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

export default function HeadmasterDashboard() {
  const [notes, setNotes] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);
  const [reviewComment, setReviewComment] = useState("");
  const [reportApprovals, setReportApprovals] = useState([]);
  const [attendanceStats, setAttendanceStats] = useState(null);
  const [viewingReport, setViewingReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [showPromotionModal, setShowPromotionModal] = useState(false);
  const [selectedStudentForPromotion, setSelectedStudentForPromotion] = useState(null);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [pendingExamCount, setPendingExamCount] = useState(0);

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    fetchNotes();
    fetchAttendance();
    fetchReportApprovals();
  }, []);

  const fetchNotes = async () => {
    try {
      const res = await axios.get('/api/headmaster/lesson-notes', getAuthHeaders());
      setNotes(res.data);
    } catch (err) {
      console.error("Failed to fetch notes", err);
    }
  };

  const fetchAttendance = async () => {
    try {
      const res = await axios.get('/api/headmaster/attendance-summary', getAuthHeaders());
      setAttendanceStats(res.data);
    } catch (err) {
      console.error("Failed to fetch attendance stats");
    }
  };

  const fetchReportApprovals = async () => {
    try {
      const res = await axios.get('/api/headmaster/report-approvals', getAuthHeaders());
      setReportApprovals(res.data);
    } catch (err) {
      console.error("Failed to fetch report approvals");
    }
  };

  const fetchReportDetails = async (report) => {
    setLoadingReport(true);
    try {
      const res = await axios.get(
        `/api/homeroom/report-builder/report/${report.student_id}?academic_term=${report.academic_term}&academic_year=${report.academic_year}`, 
        getAuthHeaders()
      );
      setViewingReport({ ...res.data, id: report.id }); // Include the report ID for actions
    } catch (err) {
      console.error('Failed to fetch report details', err);
      alert('Failed to load report details');
    } finally {
      setLoadingReport(false);
    }
  };

  const handleReview = async (status) => {
    if (!selectedNote) return;
    try {
      await axios.post(`/api/headmaster/lesson-note/${selectedNote.id}/review`, {
        status: status,
        feedback: reviewComment || selectedNote.ai_feedback // Keep AI feedback if no manual comment
      }, getAuthHeaders());
      
      alert(`Note marked as ${status}`);
      setSelectedNote(null);
      setReviewComment("");
      fetchNotes(); // Refresh list
    } catch (err) {
      alert("Failed to update status.");
    }
  };

  const handleRescore = async () => {
    if (!selectedNote) return;
    if (!confirm('Regenerate AI analysis for this lesson note?')) return;
    
    try {
      const res = await axios.post(
        `/api/headmaster/lesson-note/${selectedNote.id}/rescore`,
        {},
        getAuthHeaders()
      );
      
      // Update the selected note with new scores
      setSelectedNote({
        ...selectedNote,
        ai_score: res.data.ai_score,
        ai_feedback: res.data.ai_feedback
      });
      
      // Refresh the notes list
      fetchNotes();
      
      alert('AI analysis regenerated successfully!');
    } catch (err) {
      console.error('Failed to rescore:', err);
      alert('Failed to regenerate AI analysis.');
    }
  };

  const handleReportAction = async (id, status) => {
    const feedback = prompt(`Enter feedback for ${status} (Optional):`);
    try {
      await axios.post('/api/headmaster/approve-report', {
        report_id: id, status, feedback
      }, getAuthHeaders());
      alert(`Report ${status}`);
      fetchReportApprovals();
    } catch (err) { alert("Action failed."); }
  };

  return (
    <div className="p-8 bg-slate-50 min-h-screen font-sans">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-800">🎓 Headmaster's Desk</h1>
          <p className="text-slate-500">Lesson Note Supervision & AI Review</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="bg-white px-4 py-2 rounded-lg shadow-sm border border-indigo-200">
            <span className="text-xs font-bold text-indigo-500 uppercase">Pending Exams</span>
            <p className="text-2xl font-black text-indigo-700">{pendingExamCount}</p>
          </div>
          <div className="bg-white px-4 py-2 rounded-lg shadow-sm border">
            <span className="text-xs font-bold text-gray-400 uppercase">Pending Review</span>
            <p className="text-2xl font-black text-orange-600">
              {notes.filter(n => n.status === 'Pending').length}
            </p>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <div className="flex gap-3 mb-8 border-b border-slate-300">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`px-6 py-3 font-bold rounded-t-lg transition-colors ${
            activeTab === 'dashboard'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-slate-700 hover:bg-slate-100'
          }`}
        >
          📊 Dashboard
        </button>
        <button
          onClick={() => setActiveTab('students')}
          className={`px-6 py-3 font-bold rounded-t-lg transition-colors ${
            activeTab === 'students'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-slate-700 hover:bg-slate-100'
          }`}
        >
          👥 Manage Students
        </button>
      </div>

      {/* Content Based on Active Tab */}
      {activeTab === 'students' ? (
        <StudentsRegistry />
      ) : (
        <>
          {/* Default Dashboard Content */}
      <div className="mb-8">
        <TeacherAlerts />
      </div>

      {/* Bulk Status Update - End of Year Operations */}
      <div className="bg-linear-to-r from-emerald-500 to-emerald-600 p-6 rounded-2xl shadow-lg text-white mb-8">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-black mb-1">⚡ End of Year: Bulk Status Update</h3>
            <p className="text-emerald-100 text-sm">Mark all JHS 3 students as Graduated after BECE exams</p>
          </div>
          <BulkStatusUpdate trigger="modal" />
        </div>
      </div>

      {/* Attendance Summary Section */}
      {attendanceStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-blue-500">
            <p className="text-gray-500 text-xs font-bold uppercase">Total Enrollment</p>
            <p className="text-3xl font-black text-gray-800">{attendanceStats.total_students}</p>
          </div>
          <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-green-500">
            <p className="text-gray-500 text-xs font-bold uppercase">Present Today</p>
            <p className="text-3xl font-black text-green-600">{attendanceStats.present_students}</p>
          </div>
          <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-red-500">
            <p className="text-gray-500 text-xs font-bold uppercase">Absent</p>
            <p className="text-3xl font-black text-red-600">{attendanceStats.absent_students}</p>
          </div>
          <div className="bg-blue-900 text-white p-6 rounded-2xl shadow-lg">
            <p className="text-blue-200 text-xs font-bold uppercase">Attendance Rate</p>
            <p className="text-4xl font-black">{attendanceStats.attendance_percentage}%</p>
          </div>
        </div>
      )}

      <div className="mb-8">
        <PerformanceAnalytics
          title="Class Performance (Headmaster View)"
          defaultView="visualization"
        />
      </div>

      {/* Report Card Approvals Section */}
      <div className="mb-8 bg-white p-6 rounded-2xl shadow-sm border border-purple-100">
        <h3 className="font-bold text-purple-900 mb-4 flex items-center gap-2">📄 Terminal Report Approvals</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reportApprovals.length === 0 && <p className="text-slate-400 text-sm">No pending reports.</p>}
          {reportApprovals.map(r => (
            <div key={r.id} className="p-4 border rounded-xl bg-purple-50">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <p className="font-bold text-slate-800">{r.student_name || 'Unknown Student'}</p>
                  <p className="text-xs text-slate-500">{r.class_name} • {r.academic_term}</p>
                  <p className="text-xs text-slate-400">{r.academic_year}</p>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded whitespace-nowrap ${
                  r.status === 'Approved' || r.status === 'HeadmasterApproved' ? 'bg-green-200 text-green-800' : 
                  r.status === 'Submitted' ? 'bg-yellow-200 text-yellow-800' : 
                  'bg-red-200 text-red-800'
                }`}>
                  {r.status === 'Submitted' ? 'Pending' : r.status}
                </span>
              </div>
              {r.term_average && (
                <div className="mb-2 text-xs text-slate-600">
                  <span className="font-semibold">Average: {r.term_average.toFixed(1)}%</span>
                  {r.overall_position && <span className="ml-2">Position: {r.overall_position}</span>}
                </div>
              )}
              <p className="text-xs text-slate-400 mb-3">Submitted: {r.submitted_at ? new Date(r.submitted_at).toLocaleString() : 'N/A'}</p>
              <div className="flex gap-2">
                <button 
                  onClick={() => fetchReportDetails(r)} 
                  className="flex-1 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs font-bold"
                >
                  View Report
                </button>
                {r.status === 'Submitted' && (
                  <>
                    <button onClick={() => handleReportAction(r.id, 'Approved')} className="flex-1 p-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-xs font-bold">Approve</button>
                    <button onClick={() => handleReportAction(r.id, 'Rejected')} className="flex-1 p-2 bg-red-500 text-white rounded-lg hover:bg-red-600 text-xs font-bold">Reject</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mb-8">
        <ExamInboxPanel
          title="Exam Papers Waiting for Headmaster Review"
          onInboxChange={setPendingExamCount}
        />
      </div>

      <div className="mb-8">
        <TimetableManager title="Timetable Management" scope="school" canManage />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* LEFT: List of Notes */}
        <div className="lg:col-span-1 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-4 border-b bg-slate-50 font-bold text-slate-700">Submitted Notes</div>
          <div className="divide-y divide-slate-100 max-h-150 overflow-y-auto">
            {notes.map(note => (
              <div 
                key={note.id} 
                onClick={() => setSelectedNote(note)}
                className={`p-4 cursor-pointer hover:bg-blue-50 transition-colors ${selectedNote?.id === note.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''}`}
              >
                <div className="flex justify-between mb-1">
                  <span className="font-bold text-slate-800">{note.subject} • {note.class_name || 'Class'}</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    note.status === 'Approved' ? 'bg-green-100 text-green-700' : 
                    note.status === 'Rejected' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'
                  }`}>{note.status}</span>
                </div>
                <p className="text-sm text-slate-500">{note.teacher_name} • Week {note.week}</p>
                <p className="text-xs text-slate-400 mt-2">{note.submitted_at}</p>
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT: Review Panel */}
        <div className="lg:col-span-2">
          {selectedNote ? (
            <div className="bg-white rounded-2xl shadow-lg border border-slate-200 p-8">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-slate-800">{selectedNote.subject} - Week {selectedNote.week}</h2>
                  <p className="text-slate-500">Submitted by <span className="font-bold">{selectedNote.teacher_name}</span></p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-bold text-slate-400 uppercase">AI Quality Score</p>
                  <p className={`text-3xl font-black ${selectedNote.ai_score >= 70 ? 'text-green-600' : 'text-orange-500'}`}>
                    {selectedNote.ai_score}/100
                  </p>
                  <button
                    onClick={handleRescore}
                    className="mt-2 px-3 py-1 bg-purple-600 text-white text-xs rounded-lg font-bold hover:bg-purple-700 transition-colors"
                  >
                    🔄 Re-score
                  </button>
                </div>
              </div>

              <div className="space-y-4 mb-6">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase">Class</p>
                      <p className="font-semibold text-slate-700">{selectedNote.class_name || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase">Class Size</p>
                      <p className="font-semibold text-slate-700">{selectedNote.class_size || 'N/A'}</p>
                    </div>
                    <div className="md:col-span-2">
                      <p className="text-xs font-bold text-slate-400 uppercase">Lesson Dates</p>
                      <p className="font-semibold text-slate-700">
                        {Array.isArray(selectedNote.lesson_dates) && selectedNote.lesson_dates.length > 0
                          ? selectedNote.lesson_dates.join(', ')
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase">Indicator Code</p>
                      <p className="font-semibold text-slate-700">{selectedNote.indicator_code || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase">Content Standard Code</p>
                      <p className="font-semibold text-slate-700">{selectedNote.content_standard_code || 'N/A'}</p>
                    </div>
                  </div>
                </div>

                {selectedNote.performance_indicator && (
                  <div className="bg-white p-4 rounded-xl border">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-2">Performance Indicator</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedNote.performance_indicator}</p>
                  </div>
                )}

                {selectedNote.core_competencies && (
                  <div className="bg-white p-4 rounded-xl border">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-2">Core Competencies</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedNote.core_competencies}</p>
                  </div>
                )}

                {selectedNote.key_words && (
                  <div className="bg-white p-4 rounded-xl border">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-2">Key Words</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedNote.key_words}</p>
                  </div>
                )}

                {selectedNote.teaching_learning_resources && (
                  <div className="bg-white p-4 rounded-xl border">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-2">T.L.R(s)</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedNote.teaching_learning_resources}</p>
                  </div>
                )}

                {selectedNote.references && (
                  <div className="bg-white p-4 rounded-xl border">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-2">References</p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{selectedNote.references}</p>
                  </div>
                )}

                {Array.isArray(selectedNote.daily_phases) && selectedNote.daily_phases.length > 0 && (
                  <div className="bg-white p-4 rounded-xl border">
                    <p className="text-xs font-bold text-slate-400 uppercase mb-2">Daily Phases</p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead className="bg-slate-50">
                          <tr className="text-slate-500 uppercase">
                            <th className="p-2 text-left">Day</th>
                            <th className="p-2 text-left">Phase 1</th>
                            <th className="p-2 text-left">Phase 2</th>
                            <th className="p-2 text-left">Phase 3</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedNote.daily_phases.map((phase, index) => (
                            <tr key={`phase-${index}`} className="border-t">
                              <td className="p-2 font-semibold text-slate-700">{phase.day || '-'}</td>
                              <td className="p-2 text-slate-700 whitespace-pre-wrap">{phase.phase_1_starter || '-'}</td>
                              <td className="p-2 text-slate-700 whitespace-pre-wrap">{phase.phase_2_main || '-'}</td>
                              <td className="p-2 text-slate-700 whitespace-pre-wrap">{phase.phase_3_plenary || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {!selectedNote.performance_indicator && selectedNote.content && (
                  <div className="bg-slate-50 p-6 rounded-xl border border-slate-200 font-mono text-sm whitespace-pre-wrap text-slate-700">
                    {selectedNote.content}
                  </div>
                )}
              </div>

              <div className="bg-blue-50 p-4 rounded-xl border border-blue-100 mb-6">
                <div className="flex justify-between items-start mb-2">
                  <p className="text-blue-900 font-bold text-sm">🤖 AI Feedback:</p>
                  <button
                    onClick={handleRescore}
                    className="px-3 py-1 bg-blue-600 text-white text-xs rounded-lg font-bold hover:bg-blue-700 transition-colors"
                  >
                    🔄 Regenerate Analysis
                  </button>
                </div>
                <div className="bg-white p-3 rounded-lg border border-blue-100">
                  <pre className="text-blue-800 text-sm whitespace-pre-wrap font-sans">
                    {selectedNote.ai_feedback}
                  </pre>
                </div>
              </div>

              <div className="border-t pt-6">
                <label className="block text-sm font-bold text-slate-700 mb-2">Headmaster's Remarks (Optional)</label>
                <textarea 
                  className="w-full p-3 border rounded-lg mb-4 focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Add comments for the teacher..."
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                />
                <div className="flex gap-4">
                  <button onClick={() => handleReview('Approved')} className="flex-1 bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 shadow-lg shadow-green-200">✅ Approve Note</button>
                  <button onClick={() => handleReview('Rejected')} className="flex-1 bg-red-500 text-white py-3 rounded-xl font-bold hover:bg-red-600 shadow-lg shadow-red-200">❌ Reject & Return</button>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 font-medium bg-slate-100 rounded-2xl border-2 border-dashed border-slate-200">
              Select a lesson note to review
            </div>
          )}
        </div>
      </div>

      {/* Report Card Viewing Modal */}
      {viewingReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50" onClick={() => setViewingReport(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-linear-to-r from-purple-600 to-blue-600 text-white p-6 rounded-t-2xl">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-2xl font-black mb-1">📄 Student Report Card</h2>
                  <p className="text-purple-100 text-sm">{viewingReport.student_name} - {viewingReport.class_name}</p>
                  <p className="text-purple-100 text-xs">{viewingReport.academic_term} | {viewingReport.academic_year}</p>
                </div>
                <div className="flex gap-2 items-start">
                  <button 
                    onClick={() => {
                      setSelectedStudentForPromotion({
                        id: viewingReport.student_id,
                        name: viewingReport.student_name
                      });
                      setShowPromotionModal(true);
                    }}
                    className="text-white hover:bg-white hover:bg-opacity-20 rounded-lg px-3 py-2 font-bold text-sm"
                  >
                    👁️ Promotion History
                  </button>
                  <button 
                    onClick={() => setViewingReport(null)}
                    className="text-white hover:bg-white hover:bg-opacity-20 rounded-full w-8 h-8 flex items-center justify-center font-bold"
                  >
                    ✕
                  </button>
                </div>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {loadingReport ? (
                <p className="text-center text-slate-400">Loading report details...</p>
              ) : (
                <>
                  {/* Overall Statistics */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-blue-50 p-4 rounded-xl border border-blue-200">
                      <p className="text-xs font-bold text-blue-600 uppercase">Term Average</p>
                      <p className="text-2xl font-black text-blue-800">{viewingReport.term_average}%</p>
                    </div>
                    <div className="bg-green-50 p-4 rounded-xl border border-green-200">
                      <p className="text-xs font-bold text-green-600 uppercase">Overall Position</p>
                      <p className="text-2xl font-black text-green-800">{viewingReport.overall_position} / {viewingReport.out_of_students}</p>
                    </div>
                    <div className="bg-purple-50 p-4 rounded-xl border border-purple-200">
                      <p className="text-xs font-bold text-purple-600 uppercase">Attendance</p>
                      <p className="text-2xl font-black text-purple-800">{viewingReport.attendance_percentage}%</p>
                    </div>
                  </div>

                  {/* Promotion Status */}
                  {viewingReport.promotion_status && (
                    <div className={`p-4 rounded-xl border ${
                      viewingReport.promotion_status.includes('PROMOTED') 
                        ? 'bg-green-50 border-green-200' 
                        : 'bg-orange-50 border-orange-200'
                    }`}>
                      <p className={`text-xs font-bold uppercase ${
                        viewingReport.promotion_status.includes('PROMOTED')
                          ? 'text-green-600'
                          : 'text-orange-600'
                      }`}>
                        🎓 Promotion Status
                      </p>
                      <p className={`text-lg font-black mt-2 ${
                        viewingReport.promotion_status.includes('PROMOTED')
                          ? 'text-green-800'
                          : 'text-orange-800'
                      }`}>
                        {viewingReport.promotion_status}
                      </p>
                      {viewingReport.promotion_details && typeof viewingReport.promotion_details === 'object' && (
                        <div className="mt-2 text-xs text-slate-600">
                          {viewingReport.promotion_details.promoted_to_class && (
                            <p>Next Class: <span className="font-bold">{viewingReport.promotion_details.promoted_to_class}</span></p>
                          )}
                          {viewingReport.promotion_details.promoted_by_user && (
                            <p>Promoted by: <span className="font-bold">{viewingReport.promotion_details.promoted_by_user}</span></p>
                          )}
                          {viewingReport.promotion_details.promotion_date && (
                            <p>Date: <span className="font-bold">{new Date(viewingReport.promotion_details.promotion_date).toLocaleDateString()}</span></p>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Subject Grades */}
                  {viewingReport.subject_grades && viewingReport.subject_grades.length > 0 && (
                    <div className="bg-white border rounded-xl overflow-hidden">
                      <div className="bg-slate-100 p-3 border-b">
                        <h3 className="font-bold text-slate-800">📚 Subject Performance</h3>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 border-b">
                            <tr className="text-slate-600 text-xs uppercase">
                              <th className="p-3 text-left font-bold">Subject</th>
                              <th className="p-3 text-center font-bold">Class Score</th>
                              <th className="p-3 text-center font-bold">Exam Score</th>
                              <th className="p-3 text-center font-bold">Total</th>
                              <th className="p-3 text-center font-bold">Position</th>
                              <th className="p-3 text-center font-bold">Grade</th>
                              <th className="p-3 text-left font-bold">Remarks</th>
                            </tr>
                          </thead>
                          <tbody>
                            {viewingReport.subject_grades.map((grade, index) => (
                              <tr key={index} className="border-b hover:bg-slate-50">
                                <td className="p-3 font-semibold text-slate-700">{grade.subject}</td>
                                <td className="p-3 text-center text-slate-600">{grade.class_score}</td>
                                <td className="p-3 text-center text-slate-600">{grade.exam_score}</td>
                                <td className="p-3 text-center font-bold text-slate-800">{grade.total}</td>
                                <td className="p-3 text-center text-slate-600">{grade.position}</td>
                                <td className="p-3 text-center">
                                  <span className={`px-2 py-1 rounded-full text-xs font-bold ${
                                    grade.grade === 'A' ? 'bg-green-100 text-green-800' :
                                    grade.grade === 'B' ? 'bg-blue-100 text-blue-800' :
                                    grade.grade === 'C' ? 'bg-yellow-100 text-yellow-800' :
                                    grade.grade === 'D' ? 'bg-orange-100 text-orange-800' :
                                    'bg-red-100 text-red-800'
                                  }`}>
                                    {grade.grade}
                                  </span>
                                </td>
                                <td className="p-3 text-xs text-slate-600">{grade.remarks || '-'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Teacher Remarks */}
                  {viewingReport.homeroom_teacher_remarks && (
                    <div className="bg-blue-50 p-4 rounded-xl border border-blue-200">
                      <p className="text-xs font-bold text-blue-600 uppercase mb-2">👨‍🏫 Homeroom Teacher Remarks</p>
                      <p className="text-sm text-blue-900">{viewingReport.homeroom_teacher_remarks}</p>
                    </div>
                  )}

                  {/* AI Analysis */}
                  {viewingReport.ai_performance_analysis && (
                    <div className="bg-purple-50 p-4 rounded-xl border border-purple-200">
                      <p className="text-xs font-bold text-purple-600 uppercase mb-2">🤖 AI Performance Analysis</p>
                      <p className="text-sm text-purple-900 italic">{viewingReport.ai_performance_analysis}</p>
                    </div>
                  )}

                  {/* Headmaster Remarks (if already reviewed) */}
                  {viewingReport.headmaster_remarks && (
                    <div className="bg-green-50 p-4 rounded-xl border border-green-200">
                      <p className="text-xs font-bold text-green-600 uppercase mb-2">✅ Headmaster Remarks</p>
                      <p className="text-sm text-green-900">{viewingReport.headmaster_remarks}</p>
                    </div>
                  )}

                  {/* Action Buttons */}
                  {viewingReport.status === 'Submitted' && (
                    <div className="border-t pt-6">
                      <div className="flex gap-4">
                        <button 
                          onClick={() => {
                            handleReportAction(viewingReport.id, 'Approved');
                            setViewingReport(null);
                          }}
                          className="flex-1 bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 shadow-lg"
                        >
                          ✅ Approve Report
                        </button>
                        <button 
                          onClick={() => {
                            handleReportAction(viewingReport.id, 'Rejected');
                            setViewingReport(null);
                          }}
                          className="flex-1 bg-red-500 text-white py-3 rounded-xl font-bold hover:bg-red-600 shadow-lg"
                        >
                          ❌ Reject Report
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Promotion History Modal */}
      {showPromotionModal && selectedStudentForPromotion && (
        <PromotionHistoryModal
          studentId={selectedStudentForPromotion.id}
          studentName={selectedStudentForPromotion.name}
          onClose={() => {
            setShowPromotionModal(false);
            setSelectedStudentForPromotion(null);
          }}
        />
      )}
        </>
      )}
    </div>
  );
}