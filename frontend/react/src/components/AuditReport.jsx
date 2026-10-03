import React, { useState, useEffect } from 'react';
import axios from 'axios';

function formatMoney(value) {
  return `GH₵ ${Number(value || 0).toFixed(2)}`;
}

function getTrackedTransferDetails(transaction) {
  const category = transaction.payment_category && typeof transaction.payment_category === 'object'
    ? transaction.payment_category
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
    transferTotalAmount: Number(category.transfer_total_amount || transaction.display_amount || transaction.amount || 0),
    appliedSchoolFeeAmount: Number(category.applied_school_fee_amount || transaction.applied_amount || transaction.amount || 0),
    convenienceFeeAmount: Number(category.collected_convenience_fee_amount || category.convenience_fee_amount || 0),
    providerFeeAmount: Number(category.actual_provider_fee_amount || category.estimated_provider_fee_amount || 0),
    providerAccountNumber: category.provider_account_number || null,
    settlementMode: category.settlement_mode || null,
  };
}

export default function AuditReport() {
  return <AuditReportContent />;
}

function AuditReportContent() {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [verification, setVerification] = useState(null);
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [period, setPeriod] = useState('current_term');
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const getAuthHeaders = () => ({
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-School-ID': localStorage.getItem('school_id')
    }
  });

  const fetchSummary = async () => {
    setLoading(true);
    setErrors((previous) => ({ ...previous, summary: null }));
    try {
      const periodLabel = period === 'current_term' ? '1st Term 2026' : 'All Time';
      const res = await axios.get(`/api/finance/audit/summary?period_label=${periodLabel}`, getAuthHeaders());
      setSummary(res.data);
    } catch (err) {
      console.error('Failed to fetch audit summary:', err);
      setSummary(null);
      setErrors((previous) => ({ ...previous, summary: err.response?.data?.message || 'Please try again later.' }));
    } finally {
      setLoading(false);
    }
  };

  const fetchLedger = async () => {
    setLoading(true);
    setErrors((previous) => ({ ...previous, ledger: null }));
    try {
      const offset = page * pageSize;
      const res = await axios.get(`/api/finance/audit/ledger?limit=${pageSize}&offset=${offset}`, getAuthHeaders());
      setLedger(res.data.ledger || []);
    } catch (err) {
      console.error('Failed to fetch ledger:', err);
      setLedger([]);
      setErrors((previous) => ({ ...previous, ledger: err.response?.data?.message || 'Please try again later.' }));
    } finally {
      setLoading(false);
    }
  };

  const fetchTransactions = async () => {
    setErrors((previous) => ({ ...previous, transactions: null }));
    try {
      const res = await axios.get('/api/finance/transactions', getAuthHeaders());
      setTransactions(Array.isArray(res.data) ? res.data : []);
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
      setTransactions([]);
      setErrors((previous) => ({ ...previous, transactions: err.response?.data?.message || 'Please try again later.' }));
    }
  };

  const runVerification = async () => {
    setVerifying(true);
    setErrors((previous) => ({ ...previous, verification: null }));
    try {
      const res = await axios.post('/api/finance/audit/verify', {}, getAuthHeaders());
      setVerification(res.data);
    } catch (err) {
      console.error('Failed to verify ledger:', err);
      setVerification(null);
      setErrors((previous) => ({ ...previous, verification: err.response?.data?.message || 'Please try again later.' }));
    } finally {
      setVerifying(false);
    }
  };

  useEffect(() => {
    fetchSummary();
    fetchLedger();
    fetchTransactions();
  }, [period, page]);

  if (loading && !summary) {
    return <div className="p-8">Loading audit report...</div>;
  }

  return (
    <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
      {Object.entries(errors).filter(([, message]) => message).map(([slice, message]) => (
        <p key={slice} role="alert" className="mb-4 text-amber-900">
          {({ summary: 'Audit summary', ledger: 'Audit ledger', transactions: 'Recorded payment history', verification: 'Chain verification' })[slice]} unavailable: {message}
        </p>
      ))}
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-800 mb-2">📄 Financial Integrity Report</h1>
        <p className="text-slate-600">Cryptographic audit trail for all financial transactions</p>
      </div>

      {/* Security Protocol Badge */}
      <div className="mb-6 p-4 bg-linear-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-2xl">🔒</span>
          <span className="font-bold text-blue-900">Security Protocol: HMAC-SHA256 Cryptographic Chaining</span>
        </div>
        <p className="text-sm text-blue-700">
          Every transaction is linked with tamper-evident hash chains. Any unauthorized modification breaks the entire chain.
        </p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-linear-to-br from-green-50 to-emerald-50 border border-green-200 rounded-xl p-6">
            <div className="text-sm font-bold text-green-700 mb-1">Total Transactions</div>
            <div className="text-3xl font-black text-green-900">{summary.summary.total_transactions.toLocaleString()}</div>
          </div>
          
          <div className="bg-linear-to-br from-blue-50 to-cyan-50 border border-blue-200 rounded-xl p-6">
            <div className="text-sm font-bold text-blue-700 mb-1">Total Value</div>
            <div className="text-3xl font-black text-blue-900">
              {summary.currency} {summary.summary.total_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
            </div>
          </div>
          
          <div className="bg-linear-to-br from-purple-50 to-pink-50 border border-purple-200 rounded-xl p-6">
            <div className="text-sm font-bold text-purple-700 mb-1">Verified Entries</div>
            <div className="text-3xl font-black text-purple-900">{summary.summary.verified_count.toLocaleString()}</div>
          </div>
          
          <div className={`bg-linear-to-br ${summary.summary.is_chain_valid ? 'from-green-50 to-teal-50 border-green-200' : 'from-red-50 to-orange-50 border-red-200'} border rounded-xl p-6`}>
            <div className="text-sm font-bold mb-1" style={{color: summary.summary.is_chain_valid ? '#065f46' : '#991b1b'}}>Ledger Status</div>
            <div className="text-lg font-black" style={{color: summary.summary.is_chain_valid ? '#047857' : '#dc2626'}}>
              {summary.summary.integrity_status}
            </div>
          </div>
        </div>
      )}

      {/* Verification Controls */}
      <div className="mb-6 flex items-center justify-between">
        <button
          onClick={runVerification}
          disabled={verifying}
          className="px-6 py-3 bg-indigo-600 text-white rounded-lg font-bold hover:bg-indigo-700 disabled:bg-slate-300 flex items-center gap-2"
        >
          {verifying ? '🔄 Verifying...' : '🔍 Run Full Chain Verification'}
        </button>
        
        {verification && (
          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${verification.is_valid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
            <span className="text-xl">{verification.is_valid ? '✅' : '⚠️'}</span>
            <span className="font-bold">{verification.status}</span>
            <span className="text-sm">({verification.total_checked} entries checked)</span>
          </div>
        )}
      </div>

      {/* Recorded Payment History */}
      <div className="bg-slate-50 border rounded-xl overflow-hidden mb-4">
        <div className="bg-slate-100 px-4 py-3 border-b">
          <h2 className="text-lg font-bold text-slate-800">Recorded Payment History</h2>
          <p className="mt-1 text-xs text-slate-500">This list shows recorded payment rows, including payments that are still pending approval. The immutable ledger below only includes confirmed entries that were hashed into the audit chain.</p>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-200 text-slate-700 text-xs uppercase">
              <tr>
                <th className="p-3 text-left">Date & Time</th>
                <th className="p-3 text-left">Student</th>
                <th className="p-3 text-right">Amount</th>
                <th className="p-3 text-left">Type</th>
                <th className="p-3 text-left">Method</th>
                <th className="p-3 text-left">Reference</th>
                <th className="p-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading && transactions.length === 0 && (
                <tr><td className="p-3 text-center" colSpan="7">Loading transactions...</td></tr>
              )}
              {!loading && !errors.transactions && transactions.length === 0 && (
                <tr><td className="p-3 text-center" colSpan="7">No recorded payments were found. If a real transfer does not appear here, the system does not currently have a stored payment row for it.</td></tr>
              )}
              {transactions.map((entry, idx) => (
                <tr key={entry.id} className={`bg-white hover:bg-slate-50 ${idx % 2 === 0 ? 'bg-slate-25' : ''}`}>
                  {(() => {
                    const trackedTransfer = getTrackedTransferDetails(entry);
                    return (
                      <>
                  <td className="p-3 font-mono text-xs">{entry.date || 'N/A'}</td>
                  <td className="p-3">
                    <div className="font-semibold">{entry.student_name}</div>
                    <div className="text-xs text-slate-500">{entry.student_code || 'N/A'}</div>
                  </td>
                  <td className="p-3 text-right font-bold">
                    {formatMoney(entry.display_amount ?? entry.amount ?? 0)}
                    {entry.display_amount !== undefined && entry.applied_amount !== undefined && Number(entry.display_amount) !== Number(entry.applied_amount) ? (
                      <div className="mt-1 text-[11px] font-medium text-slate-500">Applied to {entry.type}: {formatMoney(entry.applied_amount)}</div>
                    ) : null}
                    {trackedTransfer ? (
                      <div className="mt-2 space-y-1 text-left text-[11px] font-medium text-slate-500">
                        <div>Gross paid: {formatMoney(trackedTransfer.transferTotalAmount)}</div>
                        <div>Convenience deducted: {formatMoney(trackedTransfer.convenienceFeeAmount)}</div>
                        <div>Paystack fee deducted: {formatMoney(trackedTransfer.providerFeeAmount)}</div>
                        <div className="font-semibold text-slate-700">Applied to school fee: {formatMoney(trackedTransfer.appliedSchoolFeeAmount)}</div>
                      </div>
                    ) : null}
                  </td>
                  <td className="p-3 capitalize">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-bold">
                      {entry.type}
                    </span>
                  </td>
                  <td className="p-3 capitalize text-sm">{entry.method || 'N/A'}</td>
                  <td className="p-3 font-mono text-xs text-slate-600">
                    <div>{entry.reference_id || entry.payment_category?.reference_code || 'N/A'}</div>
                    {trackedTransfer?.providerAccountNumber ? <div className="mt-1 text-[11px] text-slate-500">Acct: {trackedTransfer.providerAccountNumber}</div> : null}
                    {trackedTransfer?.settlementMode ? <div className="text-[11px] text-slate-500">Mode: {trackedTransfer.settlementMode}</div> : null}
                  </td>
                  <td className="p-3 text-center">
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-bold ${entry.status === 'Confirmed' ? 'bg-green-100 text-green-700' : entry.status === 'Rejected' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'}`}>
                      {entry.status || 'Pending'}
                    </span>
                  </td>
                      </>
                    );
                  })()}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Immutable Confirmed Ledger */}
      <div className="bg-slate-50 border rounded-xl overflow-hidden mb-4">
        <div className="bg-slate-100 px-4 py-3 border-b">
          <h2 className="text-lg font-bold text-slate-800">Immutable Confirmed Ledger</h2>
          <p className="mt-1 text-xs text-slate-500">Only confirmed payments appear here because this table is backed by the tamper-evident ledger chain.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-200 text-slate-700 text-xs uppercase">
              <tr>
                <th className="p-3 text-left">Date & Time</th>
                <th className="p-3 text-left">Student</th>
                <th className="p-3 text-right">Amount</th>
                <th className="p-3 text-left">Type</th>
                <th className="p-3 text-left">Source</th>
                <th className="p-3 text-left">Verification Hash</th>
                <th className="p-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading && ledger.length === 0 && (
                <tr><td className="p-3 text-center" colSpan="7">Loading ledger entries...</td></tr>
              )}
              {!loading && !errors.ledger && ledger.length === 0 && (
                <tr><td className="p-3 text-center" colSpan="7">No confirmed ledger entries found.</td></tr>
              )}
              {ledger.map((entry, idx) => (
                <tr key={entry.id} className={`bg-white hover:bg-slate-50 ${idx % 2 === 0 ? 'bg-slate-25' : ''}`}>
                  <td className="p-3 font-mono text-xs">{entry.date}</td>
                  <td className="p-3">
                    <div className="font-semibold">{entry.student_name}</div>
                    <div className="text-xs text-slate-500">{entry.student_code}</div>
                  </td>
                  <td className="p-3 text-right font-bold">{entry.currency} {entry.amount.toFixed(2)}</td>
                  <td className="p-3 capitalize">
                    <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-bold">
                      {entry.tx_type}
                    </span>
                  </td>
                  <td className="p-3 capitalize text-sm">{entry.source}</td>
                  <td className="p-3 font-mono text-xs text-slate-600" title={entry.full_hash}>
                    {entry.hash}
                  </td>
                  <td className="p-3 text-center">
                    {entry.is_verified ? (
                      <span className="text-xl" title="Hash chain verified">🟢</span>
                    ) : (
                      <span className="text-xl" title="Hash chain broken">🔴</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setPage(Math.max(0, page - 1))}
          disabled={page === 0}
          className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-bold disabled:bg-slate-100 disabled:text-slate-400"
        >
          ← Previous
        </button>
        <span className="text-sm text-slate-600">Page {page + 1}</span>
        <button
          onClick={() => setPage(page + 1)}
          disabled={ledger.length < pageSize}
          className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-bold disabled:bg-slate-100 disabled:text-slate-400"
        >
          Next →
        </button>
      </div>

      {/* Educational Notice */}
      <div className="mt-8 p-4 bg-amber-50 border border-amber-200 rounded-xl">
        <div className="flex items-start gap-3">
          <span className="text-2xl">💡</span>
          <div>
            <h3 className="font-bold text-amber-900 mb-1">How This Protects Your School</h3>
            <p className="text-sm text-amber-800">
              Each transaction is cryptographically linked to the previous one. If anyone attempts to alter a past transaction 
              (e.g., changing GH₵ 500 to GH₵ 50), all subsequent hashes will break, immediately flagging the tampering. 
              This creates an immutable financial record that can be audited at any time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
