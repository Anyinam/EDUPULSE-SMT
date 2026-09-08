import React, { useState, useEffect } from 'react';
import axios from 'axios';

function getPaymentFrequency(transaction) {
  if (transaction.type !== 'Feeding') return '-';
  return transaction.feeding_frequency || transaction.payment_category?.frequency || 'Inferred on approval';
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

    const headers = ["Date", "Student Name", "Type", "Frequency", "Method", "Amount", "Status"];
    const rows = transactions.map(t => [
      t.date,
      `"${t.student_name}"`,
      t.type,
      `"${getPaymentFrequency(t)}"`,
      t.method,
      t.display_amount ?? t.amount,
      t.status
    ]);

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
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {transactions.map(t => (
              <tr key={t.id} className="hover:bg-slate-50">
                <td className="p-4 text-sm text-slate-600">{t.date}</td>
                <td className="p-4 font-bold text-slate-800">{t.student_name}</td>
                <td className="p-4 text-sm">{t.type}</td>
                <td className="p-4 text-sm text-slate-600">{getPaymentFrequency(t)}</td>
                <td className="p-4 text-sm">{t.method}</td>
                <td className="p-4 font-mono font-bold text-green-600">
                  GH₵ {(t.display_amount ?? t.amount)?.toFixed ? (t.display_amount ?? t.amount).toFixed(2) : t.display_amount ?? t.amount}
                  {t.display_amount !== undefined && t.applied_amount !== undefined && Number(t.display_amount) !== Number(t.applied_amount) ? (
                    <p className="mt-1 text-[11px] font-medium text-slate-500">Applied to {t.type}: GH₵ {Number(t.applied_amount).toFixed(2)}</p>
                  ) : null}
                </td>
                <td className="p-4"><span className={`px-2 py-1 rounded text-xs font-bold ${t.status === 'Confirmed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>{t.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}