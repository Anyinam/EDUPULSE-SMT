import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import StudentPaymentTracker from '../components/StudentPaymentTracker';
import PaymentEntry from './PaymentEntry';
import { useBranding } from '../hooks/useBranding';
import FeatureLock from '../components/FeatureLock';

function formatMoney(value) {
  return `GH₵ ${Number(value || 0).toFixed(2)}`;
}

function getTrackedTransferDetails(payment) {
  const category = payment.payment_category && typeof payment.payment_category === 'object'
    ? payment.payment_category
    : {};

  const hasTrackedTransfer = Boolean(
    category.collection_channel === 'dedicated_virtual_account'
    || category.payment_collection_intent_id
    || category.split_code
    || category.transfer_total_amount
  );

  if (!hasTrackedTransfer) {
    return null;
  }

  return {
    referenceCode: category.reference_code || null,
    transferTotalAmount: Number(category.transfer_total_amount || payment.display_amount || payment.amount || 0),
    appliedSchoolFeeAmount: Number(category.applied_school_fee_amount || payment.applied_amount || payment.amount || 0),
    convenienceFeeAmount: Number(category.collected_convenience_fee_amount || category.convenience_fee_amount || 0),
    providerFeeAmount: Number(category.actual_provider_fee_amount || category.estimated_provider_fee_amount || 0),
  };
}

/**
 * Finance Dashboard - Handles fee collection, payment records, and financial reports
 */
export default function FinanceDashboard() {
  return <FeatureLock feature="payment_tracking" requiredPlan="Basic"><FinanceDashboardContent /></FeatureLock>;
}

function FinanceDashboardContent() {
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'dashboard';
  const [stats, setStats] = useState(null);
  const [payments, setPayments] = useState([]);
  const [pendingPayments, setPendingPayments] = useState([]);
  const [pendingPaymentGroups, setPendingPaymentGroups] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPaymentClass, setSelectedPaymentClass] = useState('all');
  const [selectedPaymentRecorderRole, setSelectedPaymentRecorderRole] = useState('all');
  const { branding } = useBranding();

  const getAuthHeaders = () => ({
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  useEffect(() => {
    const fetchFinanceData = async () => {
      try {
        setLoading(true);
        const res = await axios.get('/api/finance/dashboard', getAuthHeaders());
        setStats(res.data);
        setPendingPayments(res.data?.pending_payments || []);
        setPendingPaymentGroups(res.data?.pending_payments_by_class || []);
        
        // Fetch students for payment entry
        const studentsRes = await axios.get('/api/students', getAuthHeaders());
        setStudents(studentsRes.data || []);
      } catch (err) {
        console.error("Failed to load finance data:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchFinanceData();
    const interval = setInterval(fetchFinanceData, 300000);
    return () => clearInterval(interval);
  }, []);

  const refreshData = async () => {
    try {
      const res = await axios.get('/api/finance/dashboard', getAuthHeaders());
      setStats(res.data);
      setPendingPayments(res.data?.pending_payments || []);
      setPendingPaymentGroups(res.data?.pending_payments_by_class || []);
    } catch (err) {
      console.error("Failed to refresh data:", err);
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

    const paymentsForGroup = (group.payments || []).filter(payment => (
      selectedPaymentRecorderRole === 'all'
      || (payment.recorded_by_role || 'unknown') === selectedPaymentRecorderRole
    ));

    if (!paymentsForGroup.length) {
      return groups;
    }

    groups.push({
      ...group,
      payments: paymentsForGroup,
      count: paymentsForGroup.length,
      total_amount: paymentsForGroup.reduce((sum, payment) => sum + Number(payment.amount || 0), 0),
    });
    return groups;
  }, []);

  // Default: Finance Dashboard view
  if (activeTab === 'payment-tracker') {
    return <StudentPaymentTracker />;
  }

  if (loading || !stats) {
    return <div className="p-8 text-center text-gray-600">Loading Finance Dashboard...</div>;
  }

  return (
    <div className="p-8 bg-linear-to-br from-emerald-50 to-blue-50 min-h-screen font-sans">
      <header className="mb-8 border-b border-emerald-200 pb-4">
        <h1 className="text-4xl font-black text-emerald-900">💰 Finance Dashboard</h1>
        <p className="text-emerald-700 font-medium">Payment & Financial Records</p>
      </header>

      {/* Manual Payment Recording Section */}
      <div className="mb-8">
        <PaymentEntry students={students} onSuccess={refreshData} />
      </div>

      {/* Revenue Snapshot */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-emerald-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Daily Revenue</p>
          <p className="text-3xl font-black text-emerald-700">₵{Number(stats.daily_revenue || 0).toFixed(2)}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-blue-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Revenue (Last 30 Days)</p>
          <p className="text-3xl font-black text-blue-700">₵{Number(stats.monthly_revenue || 0).toFixed(2)}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-indigo-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Revenue (Last 365 Days)</p>
          <p className="text-3xl font-black text-indigo-700">₵{Number(stats.yearly_revenue || 0).toFixed(2)}</p>
        </div>
      </div>

      {/* Finance Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-blue-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Total Collected</p>
          <p className="text-3xl font-black text-blue-600">₵{stats.total_collected?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-yellow-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Outstanding</p>
          <p className="text-3xl font-black text-yellow-600">₵{stats.outstanding_balance?.toFixed(2) || '0.00'}</p>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-2xl shadow-sm overflow-hidden border border-emerald-100">
        <table className="w-full text-left">
          <thead className="bg-emerald-100 text-emerald-900">
            <tr>
              <th className="p-4 font-bold">Date</th>
              <th className="p-4 font-bold">Student</th>
              <th className="p-4 font-bold">Amount</th>
              <th className="p-4 font-bold">Transfer Detail</th>
              <th className="p-4 font-bold">Payment Type</th>
              <th className="p-4 font-bold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-emerald-50">
            {stats.recent_transactions?.length > 0 ? (
              stats.recent_transactions.map((payment, idx) => {
                const trackedTransfer = getTrackedTransferDetails(payment);
                return (
                <tr key={idx} className="hover:bg-emerald-50/50 align-top">
                  <td className="p-4 text-gray-700">{new Date(payment.date).toLocaleDateString()}</td>
                  <td className="p-4 font-semibold text-gray-800">{payment.student_name}</td>
                  <td className="p-4 text-green-600 font-bold">
                    {formatMoney(payment.display_amount ?? payment.amount)}
                    {payment.display_amount !== undefined && payment.applied_amount !== undefined && Number(payment.display_amount) !== Number(payment.applied_amount) ? (
                      <p className="mt-1 text-[11px] font-medium text-slate-500">Applied to {payment.type}: {formatMoney(payment.applied_amount)}</p>
                    ) : null}
                  </td>
                  <td className="p-4 text-xs text-slate-600">
                    {trackedTransfer ? (
                      <div className="space-y-1">
                        {trackedTransfer.referenceCode ? <p>Ref: <span className="font-semibold text-slate-800">{trackedTransfer.referenceCode}</span></p> : null}
                        <p>Gross paid: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.transferTotalAmount)}</span></p>
                        <p>Convenience deducted: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.convenienceFeeAmount)}</span></p>
                        <p>Paystack fee deducted: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.providerFeeAmount)}</span></p>
                        <p>Applied to school fee: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.appliedSchoolFeeAmount)}</span></p>
                      </div>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="p-4 text-gray-600">{payment.type || 'Tuition'}</td>
                  <td className="p-4">
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-green-100 text-green-700">
                      {payment.status || 'Recorded'}
                    </span>
                  </td>
                </tr>
              )})
            ) : (
              <tr>
                <td colSpan="6" className="p-4 text-center text-gray-500">No recent transactions</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pending Cash from Teachers */}
      <div className="mt-8 bg-white p-6 rounded-2xl shadow-sm border border-emerald-100">
        <h3 className="font-bold text-emerald-900 mb-4">⏳ Pending Payments (Awaiting Proprietor Approval)</h3>
        <p className="text-xs text-gray-600 mb-3">Manual payments require proprietor approval before being added to the immutable audit ledger.</p>
        {pendingPayments.length > 0 ? (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wide text-emerald-800 mb-1">Class Queue</label>
                <select
                  value={selectedPaymentClass}
                  onChange={(event) => setSelectedPaymentClass(event.target.value)}
                  className="w-full rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-slate-700"
                >
                  <option value="all">All Classes</option>
                  {pendingPaymentGroups.map(group => (
                    <option key={group.class_name} value={group.class_name}>{group.class_name} ({group.count})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wide text-emerald-800 mb-1">Recorded By</label>
                <select
                  value={selectedPaymentRecorderRole}
                  onChange={(event) => setSelectedPaymentRecorderRole(event.target.value)}
                  className="w-full rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-slate-700"
                >
                  <option value="all">All Staff Roles</option>
                  {paymentRoleOptions.map(option => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {visiblePaymentGroups.map(group => (
              <div key={group.class_name} className="rounded-2xl border border-yellow-200 bg-yellow-50 p-4">
                <div className="border-b border-yellow-200 pb-3">
                  <p className="text-sm font-black text-slate-800">{group.class_name}</p>
                  <p className="text-xs text-slate-500">{group.count} pending payment{group.count === 1 ? '' : 's'} • GH₵{Number(group.total_amount || 0).toFixed(2)}</p>
                </div>
                <div className="mt-3 space-y-2">
                  {group.payments.map(p => (
                    <div key={p.id} className="flex flex-col gap-2 rounded-xl border border-yellow-200 bg-white p-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <span className="text-sm text-gray-900">{p.student} paid <b>GH₵{Number(p.amount).toFixed(2)}</b> ({p.type})</span>
                        <p className="mt-1 text-xs text-slate-500">{p.recorded_by_label || 'Unknown Staff'}{p.recorded_by_name ? ` • ${p.recorded_by_name}` : ''}</p>
                        <p className="mt-1 text-xs text-slate-400">{p.method || 'Cash'}{p.reference_id ? ` • Ref: ${p.reference_id}` : ''}</p>
                      </div>
                      <span className="text-xs px-3 py-1 rounded-full bg-yellow-100 text-yellow-800 font-bold">
                        Awaiting Approval
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-emerald-700">No pending payments.</p>
        )}
      </div>
    </div>
  );
}
