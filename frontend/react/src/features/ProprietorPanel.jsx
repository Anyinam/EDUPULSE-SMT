import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import AIInsights from '../components/AIInsights'; 
import RemoteOversight from '../components/RemoteOversight';
import BillingVisibility from '../components/BillingVisibility';
import { useBranding } from '../hooks/useBranding';
import SettingsPanel from '../components/SettingsPanel';
import PaymentEntry from './PaymentEntry';
import TransactionHistory from './TransactionHistory';
import StaffManagement from './StaffManagement';
import InventoryManager from './InventoryManager';
import AdmissionsPanel from './AdmissionsPanel';
import SubscriptionManager from './SubscriptionManager';
import ProfileSettings from './ProfileSettings';
import StudentsRegistry from './StudentsRegistry';
import StudentPaymentTracker from '../components/StudentPaymentTracker';
import TerminalReportPrinter from '../components/TerminalReportPrinter';
import HolidayCalendar from '../components/HolidayCalendar';
import AuditReport from '../components/AuditReport';
import PerformanceAnalytics from '../components/PerformanceAnalytics';
import ExamIntelligencePanel from '../components/ExamIntelligencePanel';
import AcademicGuidancePanel from '../components/AcademicGuidancePanel';
import BulkStatusUpdate from '../components/BulkStatusUpdate';
import ExamInboxPanel from '../components/ExamInboxPanel';
import RescueActivityCenter from './RescueActivityCenter';

export default function ProprietorPanel() {
  // Use React Router's useSearchParams hook to properly handle query parameters
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'dashboard';

  const [pendingPayments, setPendingPayments] = useState([]);
  const [allStudents, setAllStudents] = useState([]);
  const [stats, setStats] = useState({ today_revenue: 0, canteen_count: 0 });
  const [reportApprovals, setReportApprovals] = useState([]);
  const [viewingReport, setViewingReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [attendanceStats, setAttendanceStats] = useState(null);
  const [pendingExamCount, setPendingExamCount] = useState(0);
  const [billingNotice, setBillingNotice] = useState(null);
  const [lastDashboardRefresh, setLastDashboardRefresh] = useState(null);
  const { branding } = useBranding();
  const plan = localStorage.getItem('subscription_plan') || 'Free Tier';

  const fetchRiskData = async () => {
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.get('/api/proprietor/live-feed', { headers });
      
      setPendingPayments(res.data.pending_payments || []);
      setStats(res.data.stats || { today_revenue: 0, canteen_count: 0 });
      setBillingNotice(res.data.billing_notice || null);
      
      // Fetch all students for payment dropdown (simplified for demo)
      const studentsRes = await axios.get('/api/proprietor/students', { headers });
      setAllStudents(studentsRes.data);
    } catch (err) {
      console.error('Failed to fetch proprietor dashboard live data', err);
    }
  };

  // Fetch AI-flagged students for the Intervention List
  useEffect(() => {
    if (activeTab !== 'dashboard') return;

    const refreshDashboardData = async () => {
      await Promise.allSettled([
        fetchRiskData(),
        fetchReportApprovals(),
        fetchAttendance()
      ]);
      setLastDashboardRefresh(new Date());
    };

    refreshDashboardData();
    const refreshTimer = setInterval(refreshDashboardData, 30000);
    return () => clearInterval(refreshTimer);
  }, [activeTab]);

  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  const fetchReportApprovals = async () => {
    try {
      const res = await axios.get('/api/proprietor/report-builder/pending', { headers: getAuthHeaders() });
      setReportApprovals(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to fetch report approvals', err);
      setReportApprovals([]);
    }
  };

  const fetchAttendance = async () => {
    try {
      const res = await axios.get('/api/headmaster/attendance-summary', { headers: getAuthHeaders() });
      setAttendanceStats(res.data);
    } catch (err) {
      console.error('Failed to fetch attendance stats', err);
    }
  };

  const fetchReportDetails = async (report) => {
    setLoadingReport(true);
    try {
      const res = await axios.get(
        `/api/homeroom/report-builder/report/${report.student_id}?academic_term=${report.academic_term}&academic_year=${report.academic_year}`, 
        { headers: getAuthHeaders() }
      );
      setViewingReport({ ...res.data, id: report.id });
    } catch (err) {
      console.error('Failed to fetch report details', err);
      alert('Failed to load report details');
    } finally {
      setLoadingReport(false);
    }
  };

  const handleReportAction = async (id, status) => {
    const feedback = prompt(`${status === 'Approved' ? 'Approve' : 'Reject'} this report. Add remarks (optional):`);
    if (feedback === null) return;
    try {
      await axios.post('/api/proprietor/report-builder/approve', {
        report_id: id, status, proprietor_remarks: feedback
      }, { headers: getAuthHeaders() });
      alert(`Report ${status}`);
      fetchReportApprovals();
    } catch (err) { alert("Action failed."); }
  };

  const confirmCash = async (id) => {
    const headers = { 
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id') 
    };
    try {
      await axios.post(`/api/finance/confirm-payment/${id}`, {}, { headers });
      alert("Payment confirmed and added to immutable audit ledger!");
      await fetchRiskData();
    } catch (err) {
      alert("Failed to confirm payment.");
    }
  };

  const rejectPayment = async (id) => {
    const headers = { 
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id') 
    };
    if (!confirm('Are you sure you want to reject this payment? This action cannot be undone.')) {
      return;
    }
    try {
      await axios.post(`/api/finance/reject-payment/${id}`, {}, { headers });
      alert("Payment rejected and removed.");
      await fetchRiskData();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to reject payment.");
    }
  };

  return (
    <div className="flex-1 bg-gray-100 font-sans">
      {/* MAIN CONTENT - Full Width (no internal sidebar) */}
      <main className="w-full p-8 overflow-y-auto">
        <header className="flex justify-between items-end mb-8">
          <div>
            <h1 className="text-4xl font-black text-slate-800">Proprietor Command</h1>
            <p className={`text-xs mt-1 ${(lastDashboardRefresh && (Date.now() - lastDashboardRefresh.getTime() > 60000)) ? 'text-red-500' : 'text-slate-500'}`}>
              {lastDashboardRefresh
                ? `Dashboard updated ${lastDashboardRefresh.toLocaleTimeString()}`
                : 'Dashboard loading...'}
            </p>
          </div>
          <div className="bg-white px-4 py-2 rounded-lg shadow-sm border border-indigo-200">
            <span className="text-xs font-bold text-indigo-500 uppercase">Pending Exams</span>
            <p className="text-2xl font-black text-indigo-700">{pendingExamCount}</p>
          </div>
        </header>

        {activeTab === 'dashboard' ? (
          <div className="space-y-8">
            {billingNotice && (
              <div className={`rounded-xl border px-4 py-3 ${billingNotice.level === 'error' ? 'border-red-200 bg-red-50' : 'border-amber-200 bg-amber-50'}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className={`text-sm font-bold ${billingNotice.level === 'error' ? 'text-red-900' : 'text-amber-900'}`}>{billingNotice.title || 'Billing Notice'}</p>
                    <p className={`mt-1 text-xs ${billingNotice.level === 'error' ? 'text-red-800' : 'text-amber-800'}`}>{billingNotice.message}</p>
                  </div>
                  <button
                    onClick={() => { window.location.href = billingNotice.redirect_to || '/proprietor?tab=subscription'; }}
                    className={`${billingNotice.level === 'error' ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-600 hover:bg-amber-700'} text-white text-sm font-bold px-4 py-2 rounded-lg`}
                  >
                    Resolve Now
                  </button>
                </div>
              </div>
            )}

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

            {/* Billing Visibility Section */}
            <div className="mb-8">
              <BillingVisibility />
            </div>

            <div className="mb-8">
              <PerformanceAnalytics
                title="Class Performance (Proprietor View)"
                defaultView="visualization"
              />
            </div>

            {/* Report Card Approvals Section */}
            {reportApprovals.length > 0 && (
              <div className="mb-8 bg-white p-6 rounded-2xl shadow-sm border border-purple-100">
                <h3 className="font-bold text-purple-900 mb-4 flex items-center gap-2">📄 Final Report Approvals</h3>
                <p className="text-sm text-slate-500 mb-4">Reports awaiting your review and final approval</p>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {reportApprovals.map(r => (
                    <div key={r.id} className="border rounded-xl p-4 bg-linear-to-br from-purple-50 to-blue-50 hover:shadow-md transition-shadow">
                      <div className="flex items-center justify-between mb-2">
                        <p className="font-bold text-slate-800 text-sm">{r.student_name}</p>
                        <span className="px-2 py-1 text-xs font-bold rounded-full bg-yellow-100 text-yellow-800">Pending</span>
                      </div>
                      <p className="text-xs text-slate-500 mb-1">{r.class_name}</p>
                      <p className="text-xs font-semibold text-slate-600 mb-2">{r.academic_term} • {r.academic_year}</p>
                      {r.term_average && (
                        <div className="mb-2 text-xs text-slate-600">
                          <span className="font-semibold">Average: {r.term_average.toFixed(1)}%</span>
                          {r.overall_position && <span className="ml-2">Position: {r.overall_position}</span>}
                        </div>
                      )}
                      <p className="text-xs text-slate-400 mb-3">
                        {r.status === 'HeadmasterApproved' 
                          ? `Approved by Headmaster: ${r.headmaster_approved_at ? new Date(r.headmaster_approved_at).toLocaleString() : 'N/A'}`
                          : `Submitted by Teacher: ${r.submitted_at ? new Date(r.submitted_at).toLocaleString() : 'N/A'}`
                        }
                      </p>
                      <div className="flex gap-2">
                        <button 
                          onClick={() => fetchReportDetails(r)} 
                          className="flex-1 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs font-bold"
                        >
                          View Report
                        </button>
                        {(r.status === 'HeadmasterApproved' || (r.status === 'Submitted' && r.submit_to === 'proprietor')) && (
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
            )}

            <div className="mb-8">
              <ExamInboxPanel
                title="Exam Papers Waiting for Proprietor Review"
                onInboxChange={setPendingExamCount}
              />
            </div>

            {/* AI Insights Section */}
            <div className="mb-8">
              <AIInsights showPremiumOnly={plan === 'Free Tier'} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <RemoteOversight />
              <div className="space-y-6">
                
                {/* PAYMENT ENTRY & CONFIRMATION */}
                <PaymentEntry students={allStudents} />
                
                {pendingPayments.length > 0 && (
                  <div className="bg-yellow-50 p-6 rounded-3xl border border-yellow-200">
                    <h3 className="font-bold text-yellow-800 mb-2">⏳ Pending Manual Payments (Requires Your Approval)</h3>
                    <p className="text-xs text-yellow-700 mb-3">These payments were recorded by staff and need your confirmation before being added to the immutable audit ledger.</p>
                    {pendingPayments.map(p => (
                      <div key={p.id} className="flex justify-between items-center bg-white p-3 rounded-lg mb-2 shadow-sm">
                        <span className="text-sm text-gray-600">{p.student} paid <b>GH₵{p.amount}</b> ({p.type})</span>
                        <div className="flex gap-2">
                          <button onClick={() => confirmCash(p.id)} className="text-xs bg-green-600 text-white px-3 py-1 rounded-full font-bold hover:bg-green-700">
                            ✓ Approve & Hash
                          </button>
                          <button onClick={() => rejectPayment(p.id)} className="text-xs bg-red-100 text-red-700 px-3 py-1 rounded-full font-bold hover:bg-red-200">
                            ✗ Reject
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="bg-white p-8 rounded-3xl shadow-sm border-b-8 border-green-500">
                    <p className="text-slate-400 font-bold uppercase text-xs mb-2">Confirmed Revenue (Today)</p>
                    <h3 className="text-4xl font-black text-green-600">GH₵ {Number(stats.today_revenue || 0).toLocaleString()}</h3>
                  </div>
                  <div className="bg-white p-8 rounded-3xl shadow-sm border-b-8 border-blue-500">
                    <p className="text-slate-400 font-bold uppercase text-xs mb-2">Confirmed Revenue (Last 30 Days)</p>
                    <h3 className="text-4xl font-black text-blue-700">GH₵ {Number(stats.monthly_revenue || 0).toLocaleString()}</h3>
                  </div>
                  <div className="bg-white p-8 rounded-3xl shadow-sm border-b-8 border-indigo-500">
                    <p className="text-slate-400 font-bold uppercase text-xs mb-2">Confirmed Revenue (Last 365 Days)</p>
                    <h3 className="text-4xl font-black text-indigo-700">GH₵ {Number(stats.yearly_revenue || 0).toLocaleString()}</h3>
                  </div>
                </div>

                <div className="bg-white p-8 rounded-3xl shadow-sm border-b-8 border-orange-500">
                  <p className="text-slate-400 font-bold uppercase text-xs mb-2">Kitchen Manifest (9:00 AM)</p>
                  <h3 className="text-5xl font-black text-orange-600">{stats.canteen_count} <span className="text-lg text-slate-400 font-medium">Meals</span></h3>
                </div>
              </div>
            </div>
          </div>
        ) : activeTab === 'finance' ? (
          <TransactionHistory />
        ) : activeTab === 'payment-tracker' ? (
          <StudentPaymentTracker />
        ) : activeTab === 'exam-intelligence' ? (
          <div className="space-y-8">
            <AcademicGuidancePanel title="Strategic Academic Guidance Overview" />
            <ExamIntelligencePanel />
          </div>
        ) : activeTab === 'rescue-activity' ? (
          <RescueActivityCenter />
        ) : activeTab === 'terminal-reports' ? (
          <TerminalReportPrinter />
        ) : activeTab === 'staff' ? (
          <StaffManagement />
        ) : activeTab === 'inventory' ? (
          <InventoryManager />
        ) : activeTab === 'admissions' ? (
          <AdmissionsPanel />
        ) : activeTab === 'students' ? (
          <StudentsRegistry />
        ) : activeTab === 'subscription' ? (
          <SubscriptionManager />
        ) : activeTab === 'profile' ? (
          <ProfileSettings />
        ) : activeTab === 'calendar' ? (
          <HolidayCalendar />
        ) : activeTab === 'audit' ? (
          <AuditReport />
        ) : (
          <SettingsPanel /> 
        )}

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
                  <button 
                    onClick={() => setViewingReport(null)}
                    className="text-white hover:bg-white hover:bg-opacity-20 rounded-full w-8 h-8 flex items-center justify-center font-bold"
                  >
                    ✕
                  </button>
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

                    {/* Headmaster Remarks */}
                    {viewingReport.headmaster_remarks && (
                      <div className="bg-green-50 p-4 rounded-xl border border-green-200">
                        <p className="text-xs font-bold text-green-600 uppercase mb-2">✅ Headmaster Remarks</p>
                        <p className="text-sm text-green-900">{viewingReport.headmaster_remarks}</p>
                      </div>
                    )}

                    {/* AI Analysis */}
                    {viewingReport.ai_performance_analysis && (
                      <div className="bg-purple-50 p-4 rounded-xl border border-purple-200">
                        <p className="text-xs font-bold text-purple-600 uppercase mb-2">🤖 AI Performance Analysis</p>
                        <p className="text-sm text-purple-900 italic">{viewingReport.ai_performance_analysis}</p>
                      </div>
                    )}

                    {viewingReport.academic_guidance?.printable_card?.headline && (
                      <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-200">
                        <p className="text-xs font-bold text-emerald-600 uppercase mb-2">🎯 SHS Pathway Card</p>
                        <p className="text-sm font-bold text-emerald-900">{viewingReport.academic_guidance.printable_card.headline}</p>
                        {viewingReport.academic_guidance.printable_card.focus_note && (
                          <p className="mt-2 text-sm text-emerald-900">{viewingReport.academic_guidance.printable_card.focus_note}</p>
                        )}
                      </div>
                    )}

                    {/* Proprietor Remarks (if already reviewed) */}
                    {viewingReport.proprietor_remarks && (
                      <div className="bg-orange-50 p-4 rounded-xl border border-orange-200">
                        <p className="text-xs font-bold text-orange-600 uppercase mb-2">🏢 Proprietor Remarks</p>
                        <p className="text-sm text-orange-900">{viewingReport.proprietor_remarks}</p>
                      </div>
                    )}

                    {/* Approval Workflow Info */}
                    {viewingReport.status === 'Submitted' && viewingReport.submit_to === 'proprietor' && (
                      <div className="bg-blue-50 p-4 rounded-xl border border-blue-200">
                        <p className="text-xs font-bold text-blue-600 uppercase mb-2">ℹ️ Direct Submission</p>
                        <p className="text-sm text-blue-900">This report was submitted directly to you (no headmaster approval required).</p>
                      </div>
                    )}

                    {/* Action Buttons */}
                    {(viewingReport.status === 'HeadmasterApproved' || (viewingReport.status === 'Submitted' && viewingReport.submit_to === 'proprietor')) && (
                      <div className="border-t pt-6">
                        <div className="flex gap-4">
                          <button 
                            onClick={() => {
                              handleReportAction(viewingReport.id, 'Approved');
                              setViewingReport(null);
                            }}
                            className="flex-1 bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 shadow-lg"
                          >
                            ✅ Approve for Printing
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
      </main>
    </div>
  );
}