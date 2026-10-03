import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Printer, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { getAuthToken } from '../utils/authUtils';

const PAGE_SIZE = 50;
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));
const money = (value, currency) => `${currency} ${Number(value ?? 0).toFixed(2)}`;

export default function PaymentReceipts() {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState({ q: '', offset: 0 });
  const [archive, setArchive] = useState({ receipts: [], total: 0, school_name: '', currency: 'GHS' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [printError, setPrintError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    axios.get('/api/finance/receipts', {
      params: { q: page.q, offset: page.offset, limit: PAGE_SIZE },
      headers: {
        Authorization: `Bearer ${getAuthToken() || localStorage.getItem('access_token')}`,
        'X-School-ID': localStorage.getItem('school_id'),
      },
    }).then(({ data }) => {
      if (active) setArchive(data);
    }).catch((failure) => {
      if (active) setError(failure.response?.data?.message || 'Unable to load payment receipts. Please try again.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [page, retry]);

  const printReceipt = (receipt) => {
    setPrintError('');
    const popup = window.open('', '_blank', 'width=800,height=700');
    if (!popup) {
      setPrintError('The receipt window was blocked. Allow popups for this site, then try printing again.');
      return;
    }
    const rows = [
      ['Receipt number', receipt.receipt_number ?? receipt.id],
      ['Student', receipt.student_name],
      ['Student code', receipt.student_code],
      ['Class', receipt.class_name],
      ['Payment type', receipt.payment_type],
      ['Method', receipt.method],
      ['Status', receipt.status ?? 'Unknown'],
      ['Date paid', receipt.date_paid ?? 'Not recorded'],
      ['Reference', receipt.reference_id],
      ['Gross amount', money(receipt.display_amount, archive.currency ?? 'GHS')],
      ['Provider fee', money(receipt.provider_fee_amount, archive.currency ?? 'GHS')],
      ['Convenience fee', money(receipt.convenience_fee_amount, archive.currency ?? 'GHS')],
      ['Applied amount', money(receipt.applied_amount, archive.currency ?? 'GHS')],
    ];
    let printed = false;
    const onLoad = () => {
      if (printed) return;
      printed = true;
      popup.focus();
      popup.print();
    };
    popup.document.open();
    popup.addEventListener('load', onLoad, { once: true });
    popup.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Payment receipt ${escapeHtml(receipt.receipt_number ?? receipt.id)}</title><style>body{font-family: sans-serif;color:#111;margin:40px;max-width:700px}h1{font-size:24px}h2{font-size:18px;border-bottom:1px solid #ccc;padding-bottom:12px}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 0;border-bottom:1px solid #eee;overflow-wrap:anywhere}th{width:40%}@media print{body{margin:20px}}</style></head><body><h1>${escapeHtml(archive.school_name)}</h1><h2>Payment Receipt</h2><table>${rows.map(([label, value]) => `<tr><th>${escapeHtml(label)}</th><td>${escapeHtml(value)}</td></tr>`).join('')}</table></body></html>`);
    popup.document.close();
    if (popup.document.readyState === 'complete') onLoad();
  };

  return (
    <section className="mx-auto max-w-6xl p-4 sm:p-8">
      <header className="mb-6 border-b border-gray-200 pb-4">
        <h1 className="text-2xl font-bold text-gray-900">Payment Receipts</h1>
        <p className="mt-1 wrap-break-word text-sm text-gray-600">{archive.school_name}</p>
      </header>
      <form className="mb-6 flex flex-wrap gap-2" onSubmit={(event) => {
        event.preventDefault();
        setPage({ q: query.trim(), offset: 0 });
      }}>
        <label className="relative min-w-0 flex-1 basis-64">
          <span className="sr-only">Search receipts</span>
          <Search size={18} className="absolute left-3 top-3 text-gray-500" aria-hidden="true" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search receipts" className="w-full rounded-md border border-gray-300 py-2 pl-10 pr-3" />
        </label>
        <button type="submit" className="inline-flex items-center gap-2 rounded-md bg-blue-700 px-4 py-2 text-white"><Search size={18} aria-hidden="true" />Search</button>
      </form>
      {printError && <p role="alert" className="mb-4 border-l-4 border-amber-500 bg-amber-50 p-3 text-sm text-amber-900">{printError}</p>}
      {error ? <div role="alert" className="py-6 text-red-700">{error}<button type="button" onClick={() => setRetry((value) => value + 1)} className="ml-3 underline">Retry</button></div>
        : loading ? <p role="status" className="py-6 text-gray-600">Loading receipts...</p>
          : archive.receipts.length === 0 ? <p className="py-6 text-gray-600">No receipts found.</p>
            : <div className="overflow-x-auto border-y border-gray-200">
              <table className="w-full min-w-160 text-left text-sm">
                <thead className="bg-gray-100 text-gray-600"><tr>{['Receipt / Date', 'Student', 'Payment', 'Status', 'Gross amount', ''].map((label) => <th key={label} className="px-3 py-3 font-medium">{label}</th>)}</tr></thead>
                <tbody>{archive.receipts.map((receipt) => <tr key={receipt.id} className="border-t border-gray-200">
                  <td className="px-3 py-3"><div>{receipt.receipt_number ?? receipt.id}</div><div className="whitespace-nowrap text-xs text-gray-500">{receipt.date_paid ?? 'Not recorded'}</div></td>
                  <td className="max-w-xs wrap-break-word px-3 py-3"><div>{receipt.student_name}</div><div className="text-xs text-gray-500">{receipt.student_code} / {receipt.class_name}</div></td>
                  <td className="px-3 py-3"><div>{receipt.payment_type}</div><div className="text-xs text-gray-500">{receipt.method}</div></td>
                  <td className="px-3 py-3">{receipt.status ?? 'Unknown'}</td>
                  <td className="whitespace-nowrap px-3 py-3">{money(receipt.display_amount, archive.currency ?? 'GHS')}</td>
                  <td className="px-3 py-3"><button type="button" aria-label={`Print receipt ${receipt.receipt_number ?? receipt.id}`} title="Print receipt" onClick={() => printReceipt(receipt)} className="rounded-md p-2 text-blue-700 hover:bg-blue-50"><Printer size={20} aria-hidden="true" /></button></td>
                </tr>)}</tbody>
              </table>
            </div>}
      <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-gray-600">
        <p>{loading || error ? '' : `${archive.total === 0 ? 0 : page.offset + 1}-${Math.min(page.offset + archive.receipts.length, archive.total)} of ${archive.total} receipts`}</p>
        <div className="flex gap-2">
          <button type="button" aria-label="Previous page" title="Previous page" disabled={loading || Boolean(error) || page.offset === 0} onClick={() => setPage({ ...page, offset: Math.max(0, page.offset - PAGE_SIZE) })} className="rounded-md border border-gray-300 p-2 disabled:opacity-40"><ChevronLeft size={20} /></button>
          <button type="button" aria-label="Next page" title="Next page" disabled={loading || Boolean(error) || page.offset + PAGE_SIZE >= archive.total} onClick={() => setPage({ ...page, offset: page.offset + PAGE_SIZE })} className="rounded-md border border-gray-300 p-2 disabled:opacity-40"><ChevronRight size={20} /></button>
        </div>
      </footer>
    </section>
  );
}