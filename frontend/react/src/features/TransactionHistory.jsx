import React, { useState, useEffect } from 'react';
import axios from 'axios';

function formatMoney(value) {
  return `GH₵ ${Number(value || 0).toFixed(2)}`;
}

function getPaymentFrequency(transaction) {
  if (transaction.type !== 'Feeding') return '-';
  return transaction.feeding_frequency || transaction.payment_category?.frequency || 'Inferred on approval';
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
    intentId: category.payment_collection_intent_id || null,
    splitCode: category.split_code || null,
    settlementMode: category.settlement_mode || null,
    referenceCode: category.reference_code || null,
    transferTotalAmount: Number(category.transfer_total_amount || transaction.display_amount || 0),
    appliedSchoolFeeAmount: Number(category.applied_school_fee_amount || transaction.applied_amount || transaction.amount || 0),
    convenienceFeeAmount: Number(category.collected_convenience_fee_amount || category.convenience_fee_amount || 0),
    providerFeeAmount: Number(category.actual_provider_fee_amount || category.estimated_provider_fee_amount || 0),
    schoolSettlementAmount: Number(category.school_settlement_amount || 0),
    platformSettlementAmount: Number(category.platform_settlement_amount || 0),
    providerAccountNumber: category.provider_account_number || null,
  };
}

export default function TransactionHistory() {
  const [transactions, setTransactions] = useState([]);

  useEffect(() => {
    const fetchTransactions = async () => {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.get('/api/finance/transactions', { headers });
      setTransactions(res.data);
    };
    fetchTransactions();
  }, []);

  const downloadCSV = () => {
    if (!transactions.length) return alert("No transactions to export.");

    const headers = [
      "Date",
      "Student Name",
      "Type",
      "Frequency",
      "Method",
      "Amount",
      "Applied Amount",
      "Status",
      "Tracked Transfer Ref",
      "Split Code",
      "Settlement Mode",
      "Gross Paid",
      "Convenience Deducted",
      "Paystack Fee Deducted",
      "Applied School Fee",
      "School Settlement",
      "Platform Settlement",
      "Convenience Fee",
      "Intent ID",
    ];
    const rows = transactions.map(t => {
      const trackedTransfer = getTrackedTransferDetails(t);
      return [
        t.date,
        `"${t.student_name}"`,
        t.type,
        `"${getPaymentFrequency(t)}"`,
        t.method,
        t.display_amount ?? t.amount,
        t.applied_amount ?? t.amount,
        t.status,
        trackedTransfer?.referenceCode || '',
        trackedTransfer?.splitCode || '',
        trackedTransfer?.settlementMode || '',
        trackedTransfer?.transferTotalAmount ?? '',
        trackedTransfer?.convenienceFeeAmount ?? '',
        trackedTransfer?.providerFeeAmount ?? '',
        trackedTransfer?.appliedSchoolFeeAmount ?? '',
        trackedTransfer?.schoolSettlementAmount ?? '',
        trackedTransfer?.platformSettlementAmount ?? '',
        trackedTransfer?.convenienceFeeAmount ?? '',
        trackedTransfer?.intentId ?? '',
      ];
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(r => r.join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `financial_ledger_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Financial Ledger</h2>
          <p className="mt-1 text-xs text-slate-500">
            Receipt printing is available in the Payment Tracker after selecting a student and the specific payment record.
          </p>
        </div>
        <button onClick={downloadCSV} className="bg-green-600 text-white px-4 py-2 rounded-xl font-bold hover:bg-green-700 shadow-lg shadow-green-200 flex items-center gap-2">
          📥 Export CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-slate-50 border-b">
            <tr className="text-slate-500 text-xs font-bold uppercase">
              <th className="p-4">Date</th>
              <th className="p-4">Student</th>
              <th className="p-4">Type</th>
              <th className="p-4">Frequency</th>
              <th className="p-4">Method</th>
              <th className="p-4">Amount</th>
              <th className="p-4">Audit</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {transactions.map(t => {
              const trackedTransfer = getTrackedTransferDetails(t);
              return (
              <tr key={t.id} className="hover:bg-slate-50 align-top">
                <td className="p-4 text-sm text-slate-600">{t.date}</td>
                <td className="p-4 font-bold text-slate-800">{t.student_name}</td>
                <td className="p-4 text-sm">{t.type}</td>
                <td className="p-4 text-sm text-slate-600">{getPaymentFrequency(t)}</td>
                <td className="p-4 text-sm">{t.method}</td>
                <td className="p-4 font-mono font-bold text-green-600">
                  {formatMoney(t.display_amount ?? t.amount)}
                  {t.display_amount !== undefined && t.applied_amount !== undefined && Number(t.display_amount) !== Number(t.applied_amount) ? (
                    <p className="mt-1 text-[11px] font-medium text-slate-500">Applied to {t.type}: {formatMoney(t.applied_amount)}</p>
                  ) : null}
                </td>
                <td className="p-4 text-xs text-slate-600">
                  {trackedTransfer ? (
                    <div className="space-y-1">
                      <p className="font-semibold uppercase tracking-[0.14em] text-emerald-700">Tracked transfer</p>
                      {trackedTransfer.referenceCode ? <p>Ref: <span className="font-semibold text-slate-800">{trackedTransfer.referenceCode}</span></p> : null}
                      {trackedTransfer.splitCode ? <p>Split: <span className="font-semibold text-slate-800">{trackedTransfer.splitCode}</span></p> : null}
                      {trackedTransfer.providerAccountNumber ? <p>Account: <span className="font-semibold text-slate-800">{trackedTransfer.providerAccountNumber}</span></p> : null}
                      {trackedTransfer.settlementMode ? <p>Mode: <span className="font-semibold text-slate-800">{trackedTransfer.settlementMode}</span></p> : null}
                      <p>Gross paid: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.transferTotalAmount)}</span></p>
                      <p>Convenience deducted: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.convenienceFeeAmount)}</span></p>
                      <p>Paystack fee deducted: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.providerFeeAmount)}</span></p>
                      <p>Applied to school fee: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.appliedSchoolFeeAmount)}</span></p>
                      <p>School settle target: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.schoolSettlementAmount || trackedTransfer.appliedSchoolFeeAmount || 0)}</span></p>
                      <p>Platform settle target: <span className="font-semibold text-slate-800">{formatMoney(trackedTransfer.platformSettlementAmount || trackedTransfer.convenienceFeeAmount || 0)}</span></p>
                      {trackedTransfer.intentId ? <p>Intent: <span className="font-semibold text-slate-800">#{trackedTransfer.intentId}</span></p> : null}
                    </div>
                  ) : (
                    <span className="text-slate-400">-</span>
                  )}
                </td>
                <td className="p-4"><span className={`px-2 py-1 rounded text-xs font-bold ${t.status === 'Confirmed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>{t.status}</span></td>
              </tr>
            )})}
          </tbody>
        </table>
      </div>
    </div>
  );
}