import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import StudentPaymentTracker from '../components/StudentPaymentTracker';
import PaymentEntry from './PaymentEntry';
import { useBranding } from '../hooks/useBranding';

/**
 * Finance Dashboard - Handles fee collection, payment records, and financial reports
 */
export default function FinanceDashboard() {
  // Use React Router's useSearchParams hook to properly handle query parameters
  const [searchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab') || 'dashboard';
  
  const [activeTab, setActiveTab] = useState(tabFromUrl);
  const [stats, setStats] = useState(null);
  const [payments, setPayments] = useState([]);
  const [pendingPayments, setPendingPayments] = useState([]);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const { branding } = useBranding();

  // Update activeTab whenever URL search params change
  useEffect(() => {
    setActiveTab(searchParams.get('tab') || 'dashboard');
  }, [searchParams]);

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

  // Render different content based on activeTab
  if (activeTab === 'payment-tracker') {
    return <StudentPaymentTracker />;
  }

  const refreshData = async () => {
    try {
      const res = await axios.get('/api/finance/dashboard', getAuthHeaders());
      setStats(res.data);
      setPendingPayments(res.data?.pending_payments || []);
    } catch (err) {
      console.error("Failed to refresh data:", err);
    }
  };

  // Default: Finance Dashboard view
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

      {/* Finance Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-blue-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Total Collected</p>
          <p className="text-3xl font-black text-blue-600">₵{stats.total_collected?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-yellow-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Outstanding</p>
          <p className="text-3xl font-black text-yellow-600">₵{stats.outstanding_balance?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-green-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Paid Students</p>
          <p className="text-3xl font-black text-green-600">{stats.paid_count || 0}</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-sm border-l-4 border-red-500">
          <p className="text-gray-500 text-xs font-bold uppercase">Unpaid Students</p>
          <p className="text-3xl font-black text-red-600">{stats.unpaid_count || 0}</p>
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
              <th className="p-4 font-bold">Payment Type</th>
              <th className="p-4 font-bold">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-emerald-50">
            {stats.recent_transactions?.length > 0 ? (
              stats.recent_transactions.map((payment, idx) => (
                <tr key={idx} className="hover:bg-emerald-50/50">
                  <td className="p-4 text-gray-700">{new Date(payment.date).toLocaleDateString()}</td>
                  <td className="p-4 font-semibold text-gray-800">{payment.student_name}</td>
                  <td className="p-4 text-green-600 font-bold">₵{payment.amount?.toFixed(2)}</td>
                  <td className="p-4 text-gray-600">{payment.type || 'Tuition'}</td>
                  <td className="p-4">
                    <span className="px-3 py-1 rounded-full text-xs font-bold bg-green-100 text-green-700">
                      Recorded
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="p-4 text-center text-gray-500">No recent transactions</td>
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
          <div className="space-y-3">
            {pendingPayments.map(p => (
              <div key={p.id} className="flex items-center justify-between bg-yellow-50 p-3 rounded-lg border border-yellow-200">
                <span className="text-sm text-gray-900">
                  {p.student} paid <b>GH₵{Number(p.amount).toFixed(2)}</b> ({p.type})
                </span>
                <span className="text-xs px-3 py-1 rounded-full bg-yellow-100 text-yellow-800 font-bold">
                  Awaiting Approval
                </span>
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
