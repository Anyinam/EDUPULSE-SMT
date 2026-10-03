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
import RescueActivityCenter from './RescueActivityCenter';
import SchoolCompliancePanel from '../components/SchoolCompliancePanel';
import useEffectiveSubscriptionPlan from '../hooks/useEffectiveSubscriptionPlan';
import useSubscription from '../hooks/useSubscription';
import FeatureLock from '../components/FeatureLock';

const PLAN_DISPLAY_NAMES = {
  'Free Tier': 'Free',
  Basic: 'School OS',
  Premium: 'School OS Plus'
};

export default function ProprietorPanel() {
  // Use React Router's useSearchParams hook to properly handle query parameters
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'dashboard';
  const { hasFeature } = useSubscription();
  const canTrackPayments = hasFeature('payment_tracking');

  const [pendingPayments, setPendingPayments] = useState([]);
  const [pendingPaymentGroups, setPendingPaymentGroups] = useState([]);
  const [allStudents, setAllStudents] = useState([]);
  const [stats, setStats] = useState({ today_revenue: 0, canteen_count: 0 });
  const [reportApprovals, setReportApprovals] = useState([]);
  const [viewingReport, setViewingReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [attendanceStats, setAttendanceStats] = useState(null);
  const [billingNotice, setBillingNotice] = useState(null);
  const [ledgerIntegrity, setLedgerIntegrity] = useState(null);
  const [lastDashboardRefresh, setLastDashboardRefresh] = useState(null);
  const [selectedPaymentClass, setSelectedPaymentClass] = useState('all');
  const [selectedPaymentRecorderRole, setSelectedPaymentRecorderRole] = useState('all');
  const [processingPaymentId, setProcessingPaymentId] = useState(null);
  const [bulkApprovingClass, setBulkApprovingClass] = useState('');
  const { branding } = useBranding();
  const {
    plan: effectivePlan,
    planDisplayName: effectivePlanDisplayName,
    basePlan,
    basePlanDisplayName,
    loading: loadingPlan,
    trial,
  } = useEffectiveSubscriptionPlan();
  const plan = effectivePlan || 'Free Tier';
  const planDisplayName = effectivePlanDisplayName || PLAN_DISPLAY_NAMES[plan] || plan;
  const resolvedBasePlan = basePlan || plan;
  const resolvedBasePlanDisplayName = basePlanDisplayName || PLAN_DISPLAY_NAMES[resolvedBasePlan] || resolvedBasePlan;
  const showingTrialAccess = Boolean(trial?.active && resolvedBasePlan !== plan);

  const fetchRiskData = async () => {
    if (!canTrackPayments) return;
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.get('/api/proprietor/live-feed', { headers });
      
      setPendingPayments(res.data.pending_payments || []);
      setPendingPaymentGroups(res.data.pending_payments_by_class || []);
      setStats(res.data.stats || { today_revenue: 0, canteen_count: 0 });
      setBillingNotice(res.data.billing_notice || null);
      setLedgerIntegrity(res.data.ledger_integrity || null);
      
      // Fetch all students for payment dropdown (simplified for demo)
      const studentsRes = await axios.get('/api/proprietor/students', { headers });
      setAllStudents(studentsRes.data);
    } catch (err) {
      console.error('Failed to fetch proprietor dashboard live data', err);
    }
  };

  useEffect(() => {
    if (selectedPaymentClass === 'all') return;
    if (!pendingPaymentGroups.some(group => group.class_name === selectedPaymentClass)) {
      setSelectedPaymentClass('all');
    }
  }, [pendingPaymentGroups, selectedPaymentClass]);

  useEffect(() => {
    if (selectedPaymentRecorderRole === 'all') return;
    if (!pendingPayments.some(payment => (payment.recorded_by_role || 'unknown') === selectedPaymentRecorderRole)) {
      setSelectedPaymentRecorderRole('all');
    }
  }, [pendingPayments, selectedPaymentRecorderRole]);

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
  }, [activeTab, canTrackPayments]);

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
    if (!canTrackPayments) return;
    const headers = { 
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id') 
    };
    try {
      setProcessingPaymentId(id);
      await axios.post(`/api/finance/confirm-payment/${id}`, {}, { headers });
      alert("Payment confirmed and added to immutable audit ledger!");
      await Promise.all([fetchRiskData(), fetchAttendance()]);
    } catch (err) {
      alert("Failed to confirm payment.");
    } finally {
      setProcessingPaymentId(null);
    }
  };

  const rejectPayment = async (id) => {
    if (!canTrackPayments) return;
    const headers = { 
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id') 
    };
    if (!confirm('Are you sure you want to reject this payment? This action cannot be undone.')) {
      return;
    }
    try {
      setProcessingPaymentId(id);
      await axios.post(`/api/finance/reject-payment/${id}`, {}, { headers });
      alert("Payment rejected and removed.");
      await fetchRiskData();
    } catch (err) {
      alert(err.response?.data?.message || "Failed to reject payment.");
    } finally {
      setProcessingPaymentId(null);
    }
  };

  const approveClassPayments = async (group) => {
    if (!canTrackPayments || !hasFeature('bulk_operations')) return;
    if (!group?.payments?.length) return;

    const confirmed = window.confirm(
      `Approve all ${group.count} pending payment${group.count === 1 ? '' : 's'} for ${group.class_name}?`
    );
    if (!confirmed) return;

    const headers = {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    };

    try {
      setBulkApprovingClass(group.class_name);
      const res = await axios.post(
        '/api/finance/confirm-payments/bulk',
        {
          class_name: group.class_name,
          payment_ids: group.payments.map(payment => payment.id)
        },
        { headers }
      );
      alert(res.data?.message || 'Class payments approved.');
      await Promise.all([fetchRiskData(), fetchAttendance()]);
    } catch (err) {
      alert(err.response?.data?.message || 'Failed to approve class payments.');
    } finally {
      setBulkApprovingClass('');
    }
  };

  const paymentRoleOptions = Array.from(
    new Map(
      pendingPayments.map(payment => [
        payment.recorded_by_role || 'unknown',
        payment.recorded_by_label || 'Unknown Staff'
      ])
    ).entries()
  ).map(([value, label]) => ({ value, label }));

  const visiblePaymentGroups = pendingPaymentGroups.reduce((groups, group) => {
    if (selectedPaymentClass !== 'all' && group.class_name !== selectedPaymentClass) {
      return groups;
    }

    const payments = (group.payments || []).filter(payment => (
      selectedPaymentRecorderRole === 'all'
      || (payment.recorded_by_role || 'unknown') === selectedPaymentRecorderRole
    ));

    if (!payments.length) {
      return groups;
    }

    groups.push({
      ...group,
      payments,
      count: payments.length,
      total_amount: payments.reduce((sum, payment) => sum + Number(payment.amount || 0), 0),
    });
    return groups;
  }, []);

  const attendancePending = attendanceStats?.attendance_taken_today === false;
  const attendanceInProgress = Boolean(attendanceStats?.attendance_partial);

  return (
    <div className="flex-1 bg-gray-100 font-sans">
      {/* MAIN CONTENT - Full Width (no internal sidebar) */}
      <main className="w-full p-4 md:p-8 overflow-y-auto">
        <header className="flex flex-wrap gap-4 justify-between items-end mb-8">
          <div>
            <h1 className="text-2xl md:text-4xl font-black text-slate-800">Proprietor Command</h1>
            <p className={`text-xs mt-1 ${(lastDashboardRefresh && (Date.now() - lastDashboardRefresh.getTime() > 60000)) ? 'text-red-500' : 'text-slate-500'}`}>
              {lastDashboardRefresh
                ? `Dashboard updated ${lastDashboardRefresh.toLocaleTimeString()}`
                : 'Dashboard loading...'}
            </p>
          </div>
          <div className="bg-white px-4 py-2 rounded-lg shadow-sm border border-indigo-200 min-w-44">
            <span className="text-xs font-bold text-indigo-500 uppercase">{showingTrialAccess ? 'Active Access' : 'Plan'}</span>
            <p className="text-lg font-black text-indigo-700">{loadingPlan ? 'Loading...' : showingTrialAccess ? `${planDisplayName} Trial` : planDisplayName}</p>
            {!loadingPlan && showingTrialAccess && (
              <p className="text-[11px] font-medium text-slate-500">Base subscription: {resolvedBasePlanDisplayName}</p>
            )}
          </div>
        </header>

        {activeTab === 'dashboard' ? (
          <div className="space-y-8">
            {canTrackPayments && ledgerIntegrity?.alert && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3" role="alert">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-red-900">{ledgerIntegrity.alert.title}</p>
                    <p className="mt-1 text-xs text-red-800">{ledgerIntegrity.alert.message}</p>
                    <p className="mt-2 text-xs font-semibold text-red-900">
                      {ledgerIntegrity.verified_entries} verified entries | {ledgerIntegrity.broken_entries} ledger broken
                    </p>
                  </div>
                  <button
                    onClick={() => { window.location.href = ledgerIntegrity.alert.redirect_to || '/proprietor?tab=audit'; }}
                    className="rounded-lg bg-red-700 px-4 py-2 text-sm font-bold text-white hover:bg-red-800"
                  >
                    Review Audit
                  </button>
                </div>
              </div>
            )}
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
                  <p className="text-3xl font-black text-green-600">{attendancePending ? (attendanceInProgress ? attendanceStats.present_students : 'Pending') : attendanceStats.present_students}</p>
                  <p className="mt-1 text-xs text-slate-500">{attendanceInProgress ? 'Partial class submissions received' : 'Confirmed present count'}</p>
                </div>
                <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-red-500">
                  <p className="text-gray-500 text-xs font-bold uppercase">Absent Today</p>
                  <p className="text-3xl font-black text-red-600">{attendancePending ? 'Pending' : attendanceStats.absent_students}</p>
                  <p className="mt-1 text-xs text-slate-500">School-wide absence locks when all classes submit</p>
                </div>
                <div className="bg-blue-900 text-white p-6 rounded-2xl shadow-lg">
                  <p className="text-blue-200 text-xs font-bold uppercase">Attendance Status</p>
                  <p className="text-4xl font-black">{attendancePending ? (attendanceInProgress ? `${attendanceStats.submitted_classes_count}/${attendanceStats.active_classes_count}` : 'Pending') : `${attendanceStats.attendance_percentage}%`}</p>
                  <p className="mt-2 text-xs text-blue-200">{attendancePending ? (attendanceStats.status_message || 'Attendance has not been submitted yet.') : "Today's submitted attendance"}</p>
                </div>
              </div>
            )}

            {/* Billing Visibility Section */}
            <div className="mb-8">
              <BillingVisibility />
            </div>

            <div className="mb-8">
              <FeatureLock feature="advanced_analytics"><PerformanceAnalytics
                title="Class Performance (Proprietor View)"
                defaultView="visualization"
              /></FeatureLock>
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

            {/* AI Insights Section */}
            <div className="mb-8">
              <AIInsights showPremiumOnly={plan === 'Free Tier'} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              <RemoteOversight />
              <div className="space-y-6">
                
                {/* PAYMENT ENTRY & CONFIRMATION */}
                <PaymentEntry students={allStudents} onSuccess={() => Promise.all([fetchRiskData(), fetchAttendance()])} />
                
                {canTrackPayments && pendingPayments.length > 0 && (
                  <div className="bg-yellow-50 p-6 rounded-3xl border border-yellow-200">
                    <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-4">
                      <div>
                        <h3 className="font-bold text-yellow-800 mb-2">⏳ Pending Manual Payments (Requires Your Approval)</h3>
                        <p className="text-xs text-yellow-700">These payments were recorded by staff and need your confirmation before being added to the immutable audit ledger.</p>
                      </div>
                      <div className="grid min-w-56 gap-3 md:grid-cols-2">
                        <div>
                          <label className="block text-[11px] font-bold uppercase tracking-wide text-yellow-800 mb-1">Class Queue</label>
                          <select
                            value={selectedPaymentClass}
                            onChange={(event) => setSelectedPaymentClass(event.target.value)}
                            className="w-full rounded-xl border border-yellow-300 bg-white px-3 py-2 text-sm text-slate-700"
                          >
                            <option value="all">All Classes</option>
                            {pendingPaymentGroups.map(group => (
                              <option key={group.class_name} value={group.class_name}>
                                {group.class_name} ({group.count})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-[11px] font-bold uppercase tracking-wide text-yellow-800 mb-1">Recorded By</label>
                          <select
                            value={selectedPaymentRecorderRole}
                            onChange={(event) => setSelectedPaymentRecorderRole(event.target.value)}
                            className="w-full rounded-xl border border-yellow-300 bg-white px-3 py-2 text-sm text-slate-700"
                          >
                            <option value="all">All Staff Roles</option>
                            {paymentRoleOptions.map(option => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      {visiblePaymentGroups.map(group => (
                        <div key={group.class_name} className="rounded-2xl border border-yellow-200 bg-white/80 p-4 shadow-sm">
                          <div className="flex flex-col gap-3 border-b border-yellow-100 pb-3 md:flex-row md:items-center md:justify-between">
                            <div>
                              <p className="text-sm font-black text-slate-800">{group.class_name}</p>
                              <p className="text-xs text-slate-500">{group.count} pending payment{group.count === 1 ? '' : 's'} • GH₵{Number(group.total_amount || 0).toFixed(2)}</p>
                            </div>
                            <button
                              onClick={() => approveClassPayments(group)}
                              disabled={!hasFeature('bulk_operations') || bulkApprovingClass === group.class_name}
                              className="rounded-full bg-green-600 px-4 py-2 text-xs font-bold text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-300"
                            >
                              {bulkApprovingClass === group.class_name ? 'Approving...' : 'Approve All In Class'}
                            </button>
                          </div>

                          <div className="mt-3 space-y-2">
                            {group.payments.map(p => (
                              <div key={p.id} className="flex flex-col gap-3 rounded-xl border border-slate-100 bg-white p-3 md:flex-row md:items-center md:justify-between">
                                <div>
                                  <span className="text-sm text-gray-600">{p.student} paid <b>GH₵{Number(p.amount).toFixed(2)}</b> ({p.type})</span>
                                  <p className="mt-1 text-xs text-slate-500">{p.recorded_by_label || 'Unknown Staff'}{p.recorded_by_name ? ` • ${p.recorded_by_name}` : ''}</p>
                                  <p className="mt-1 text-xs text-slate-400">{p.method || 'Cash'}{p.reference_id ? ` • Ref: ${p.reference_id}` : ''}</p>
                                </div>
                                <div className="flex gap-2">
                                  <button
                                    onClick={() => confirmCash(p.id)}
                                    disabled={processingPaymentId === p.id || bulkApprovingClass === group.class_name}
                                    className="text-xs bg-green-600 text-white px-3 py-1 rounded-full font-bold hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-green-300"
                                  >
                                    {processingPaymentId === p.id ? 'Approving...' : '✓ Approve & Hash'}
                                  </button>
                                  <button
                                    onClick={() => rejectPayment(p.id)}
                                    disabled={processingPaymentId === p.id || bulkApprovingClass === group.class_name}
                                    className="text-xs bg-red-100 text-red-700 px-3 py-1 rounded-full font-bold hover:bg-red-200 disabled:cursor-not-allowed disabled:bg-red-50 disabled:text-red-300"
                                  >
                                    ✗ Reject
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {canTrackPayments && <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
                </div>}

                {canTrackPayments && <div className="bg-white p-8 rounded-3xl shadow-sm border-b-8 border-orange-500">
                  <p className="text-slate-400 font-bold uppercase text-xs mb-2">Student Meals Today</p>
                  <h3 className="text-5xl font-black text-orange-600">{stats.student_meals || 0} <span className="text-lg text-slate-400 font-medium">Meals</span></h3>
                  <p className="mt-2 text-xs text-slate-500">Kitchen prep total: {stats.canteen_count || 0} including staff meals.</p>
                </div>}
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
        ) : activeTab === 'verification' ? (
          <SchoolCompliancePanel />
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

                    {viewingReport.subject_grades?.some((grade) => Array.isArray(grade?.diagnostic_topics) && grade.diagnostic_topics.length > 0) && (
                      <div className="bg-blue-50 p-4 rounded-xl border border-blue-200">
                        <p className="text-xs font-bold text-blue-700 uppercase mb-3">🧭 Diagnostic Strand Insights</p>
                        <div className="space-y-3">
                          {viewingReport.subject_grades
                            .filter((grade) => Array.isArray(grade?.diagnostic_topics) && grade.diagnostic_topics.length > 0)
                            .map((grade, index) => {
                              const sortedTopics = [...grade.diagnostic_topics].sort((left, right) => {
                                const leftRatio = Number(left.max_score || 0) > 0 ? Number(left.score || 0) / Number(left.max_score || 0) : 0;
                                const rightRatio = Number(right.max_score || 0) > 0 ? Number(right.score || 0) / Number(right.max_score || 0) : 0;
                                const leftWeak = leftRatio <= 0.55 ? 1 : 0;
                                const rightWeak = rightRatio <= 0.55 ? 1 : 0;
                                if (leftWeak !== rightWeak) {
                                  return rightWeak - leftWeak;
                                }
                                return leftRatio - rightRatio;
                              });
                              const weakTopics = sortedTopics.filter((topic) => (Number(topic.max_score || 0) > 0 ? Number(topic.score || 0) / Number(topic.max_score || 0) : 0) <= 0.55);
                              const strongTopics = sortedTopics.filter((topic) => (Number(topic.max_score || 0) > 0 ? Number(topic.score || 0) / Number(topic.max_score || 0) : 0) > 0.55);

                              return (
                                <div key={`${grade.subject || 'subject'}-${index}`} className="rounded-lg border border-blue-100 bg-white p-3">
                                  <p className="text-sm font-bold text-blue-900 mb-2">{grade.subject || 'Subject'}</p>
                                  {weakTopics.length > 0 ? (
                                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">Weak strands shown by default</p>
                                  ) : (
                                    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-blue-700">No weak strands flagged</p>
                                  )}
                                  {weakTopics.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                      {weakTopics.map((topic, topicIndex) => (
                                        <span
                                          key={`${topic.topic || 'weak-topic'}-${topicIndex}`}
                                          className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-300"
                                        >
                                          Needs attention: {topic.topic}: {Number(topic.score || 0)}/{Number(topic.max_score || 0)}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                  {strongTopics.length > 0 && (
                                    <details className="mt-3 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2">
                                      <summary className="cursor-pointer text-xs font-semibold text-blue-800">
                                        Show all assessed strands ({strongTopics.length} more)
                                      </summary>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        {strongTopics.map((topic, topicIndex) => (
                                          <span
                                            key={`${topic.topic || 'strong-topic'}-${topicIndex}`}
                                            className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-900"
                                          >
                                            {topic.topic}: {Number(topic.score || 0)}/{Number(topic.max_score || 0)}
                                          </span>
                                        ))}
                                      </div>
                                    </details>
                                  )}
                                </div>
                              );
                            })}
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