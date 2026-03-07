import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function InventoryManager() {
  const [items, setItems] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [students, setStudents] = useState([]);
  const [saleForm, setSaleForm] = useState({
    student_id: '',
    inventory_item_id: '',
    quantity: 1,
    method: 'Cash'
  });
  const [form, setForm] = useState({
    item_name: '',
    category: 'Uniform',
    item_type: '',
    size: '',
    class_group: '',
    gender: 'Unisex',
    sku: '',
    unit: 'piece',
    quantity: '',
    price: ''
  });

  const categoryOptions = ['Uniform', 'Books', 'Stationery', 'General'];
  const uniformTypeOptions = [
    'Full Uniform Pack',
    'Top Only',
    'Shorts Only',
    'Friday Wear',
    'PE Attire'
  ];
  const uniformSizeOptions = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];
  const classGroupOptions = ['Class 1-6', 'JHS', 'All'];
  const genderOptions = ['Unisex', 'Male', 'Female'];

  const headers = { 
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id') 
  };

  const fetchInventory = async () => {
    const res = await axios.get('/api/inventory', { headers });
    setItems(res.data);
  };

  const fetchTransactions = async () => {
    const res = await axios.get('/api/inventory/transactions', { headers });
    setTransactions(Array.isArray(res.data) ? res.data : []);
  };

  const fetchStudents = async () => {
    const res = await axios.get('/api/students', { headers });
    const list = Array.isArray(res.data) ? res.data : res.data?.students || [];
    setStudents(list);
  };

  useEffect(() => {
    fetchInventory();
    fetchTransactions();
    fetchStudents();
  }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    await axios.post('/api/inventory/item', form, { headers });
    fetchInventory();
    setForm({
      item_name: '',
      category: 'Uniform',
      item_type: '',
      size: '',
      class_group: '',
      gender: 'Unisex',
      sku: '',
      unit: 'piece',
      quantity: '',
      price: ''
    });
  };

  const handleExportCsv = async () => {
    try {
      const res = await axios.get('/api/inventory/export', {
        headers,
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'inventory_price_list.csv');
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert('Failed to export inventory.');
    }
  };

  const handlePrintPriceList = () => {
    const printWindow = window.open('', '', 'width=900,height=1200');
    const rows = items.map(item => `
      <tr>
        <td>${item.sku || ''}</td>
        <td>${item.item_name}</td>
        <td>${item.category || ''}</td>
        <td>${item.item_type || ''}</td>
        <td>${item.size || ''}</td>
        <td>${item.class_group || ''}</td>
        <td>${item.gender || ''}</td>
        <td>${item.quantity ?? ''}</td>
        <td>GH₵ ${Number(item.price || 0).toFixed(2)}</td>
      </tr>
    `).join('');

    const html = `
      <html>
        <head>
          <title>Inventory Price List</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 24px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #ddd; padding: 8px; font-size: 12px; }
            th { background: #f3f4f6; text-align: left; }
            h2 { margin-bottom: 16px; }
          </style>
        </head>
        <body>
          <h2>Inventory Price List</h2>
          <p>Use SKU as reference for MoMo or bank transfer narration.</p>
          <table>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th>Category</th>
                <th>Type</th>
                <th>Size</th>
                <th>Class Group</th>
                <th>Gender</th>
                <th>Qty</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </body>
      </html>
    `;
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => printWindow.print(), 500);
  };

  const selectedSaleItem = items.find(i => String(i.id) === String(saleForm.inventory_item_id));

  const handleRecordSale = async (e) => {
    e.preventDefault();
    if (!saleForm.student_id || !selectedSaleItem) {
      alert('Select student and inventory item.');
      return;
    }

    const amount = Number(selectedSaleItem.price || 0) * Number(saleForm.quantity || 1);
    const payment_category = {
      item_id: selectedSaleItem.id,
      item_name: selectedSaleItem.item_name,
      item_type: selectedSaleItem.item_type,
      size: selectedSaleItem.size,
      sku: selectedSaleItem.sku,
      quantity: Number(saleForm.quantity || 1)
    };

    await axios.post('/api/finance/receive-payment', {
      student_id: saleForm.student_id,
      amount,
      type: 'Inventory',
      method: saleForm.method,
      payment_category
    }, { headers });

    alert('Inventory payment recorded.');
    setSaleForm({ student_id: '', inventory_item_id: '', quantity: 1, method: 'Cash' });
    fetchInventory();
    fetchTransactions();
  };

  return (
    <div className="space-y-8">
      <div className="bg-white p-8 rounded-3xl shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-slate-800">School Store Inventory</h2>
          <div className="flex gap-2">
            <button onClick={handleExportCsv} className="bg-slate-700 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-slate-800">Export CSV</button>
            <button onClick={handlePrintPriceList} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700">Print Price List (PDF)</button>
          </div>
        </div>

        <form onSubmit={handleAdd} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <input placeholder="Item Name" className="p-3 border rounded-xl" value={form.item_name} onChange={e => setForm({...form, item_name: e.target.value})} required />
          <select className="p-3 border rounded-xl" value={form.category} onChange={e => setForm({...form, category: e.target.value})}>
            {categoryOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
          <select className="p-3 border rounded-xl" value={form.item_type} onChange={e => setForm({...form, item_type: e.target.value})}>
            <option value="">Item Type</option>
            {(form.category === 'Uniform' ? uniformTypeOptions : []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
          <select className="p-3 border rounded-xl" value={form.size} onChange={e => setForm({...form, size: e.target.value})}>
            <option value="">Size</option>
            {(form.category === 'Uniform' ? uniformSizeOptions : []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
          <select className="p-3 border rounded-xl" value={form.class_group} onChange={e => setForm({...form, class_group: e.target.value})}>
            <option value="">Class Group</option>
            {classGroupOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
          <select className="p-3 border rounded-xl" value={form.gender} onChange={e => setForm({...form, gender: e.target.value})}>
            {genderOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
          <input placeholder="SKU (optional)" className="p-3 border rounded-xl" value={form.sku} onChange={e => setForm({...form, sku: e.target.value})} />
          <input placeholder="Unit (piece/set)" className="p-3 border rounded-xl" value={form.unit} onChange={e => setForm({...form, unit: e.target.value})} />
          <input type="number" placeholder="Qty" className="p-3 border rounded-xl" value={form.quantity} onChange={e => setForm({...form, quantity: e.target.value})} required />
          <input type="number" placeholder="Price" className="p-3 border rounded-xl" value={form.price} onChange={e => setForm({...form, price: e.target.value})} required />
          <button className="bg-green-600 text-white px-6 rounded-xl font-bold hover:bg-green-700 col-span-1 md:col-span-4">Add Item</button>
        </form>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {items.map(item => (
          <div key={item.id} className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex justify-between items-center">
            <div>
              <h3 className="font-bold text-slate-800">{item.item_name}</h3>
              <p className="text-xs text-slate-500">{item.item_type || 'General'} {item.size ? `• ${item.size}` : ''} {item.class_group ? `• ${item.class_group}` : ''}</p>
              <p className="text-sm text-slate-500">Stock: {item.quantity} • SKU: {item.sku || 'N/A'}</p>
            </div>
            <span className="text-xl font-black text-green-600">GH₵{Number(item.price || 0).toFixed(2)}</span>
          </div>
        ))}
      </div>

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
        <h3 className="text-lg font-bold text-slate-800 mb-4">Record Inventory Payment</h3>
        <form onSubmit={handleRecordSale} className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <select
            className="p-3 border rounded-xl"
            value={saleForm.student_id}
            onChange={e => setSaleForm({ ...saleForm, student_id: e.target.value })}
            required
          >
            <option value="">Select Student</option>
            {students.map(s => (
              <option key={s.id} value={s.id}>{s.name} ({s.student_code || s.current_class || 'N/A'})</option>
            ))}
          </select>
          <select
            className="p-3 border rounded-xl"
            value={saleForm.inventory_item_id}
            onChange={e => setSaleForm({ ...saleForm, inventory_item_id: e.target.value })}
            required
          >
            <option value="">Select Item</option>
            {items.map(item => (
              <option key={item.id} value={item.id}>{item.item_name} {item.item_type ? `- ${item.item_type}` : ''} {item.size ? `(${item.size})` : ''}</option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            className="p-3 border rounded-xl"
            value={saleForm.quantity}
            onChange={e => setSaleForm({ ...saleForm, quantity: e.target.value })}
            placeholder="Qty"
            required
          />
          <select
            className="p-3 border rounded-xl"
            value={saleForm.method}
            onChange={e => setSaleForm({ ...saleForm, method: e.target.value })}
          >
            <option value="Cash">Cash</option>

            <option value="Bank">Bank</option>
          </select>
          {selectedSaleItem && (
            <div className="md:col-span-4 text-xs text-slate-600">
              Amount: GH₵ {(Number(selectedSaleItem.price || 0) * Number(saleForm.quantity || 1)).toFixed(2)}
            </div>
          )}
          <button className="bg-green-600 text-white px-6 py-2 rounded-xl font-bold hover:bg-green-700 md:col-span-4">Record Payment</button>
        </form>
      </div>

      <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
        <h3 className="text-lg font-bold text-slate-800 mb-4">Recent Inventory Payments</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2">Student</th>
                <th>Item</th>
                <th>Size/Type</th>
                <th>Qty</th>
                <th>Method</th>
                <th>Amount</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map(tx => (
                <tr key={tx.id} className="border-b">
                  <td className="py-2">{tx.student_name || 'N/A'} ({tx.student_code || '-'})</td>
                  <td>{tx.item_name || tx.payment_type}</td>
                  <td>{tx.item_type || ''} {tx.size ? `(${tx.size})` : ''}</td>
                  <td>{tx.quantity || 1}</td>
                  <td>{tx.method}</td>
                  <td>GH₵ {Number(tx.amount || 0).toFixed(2)}</td>
                  <td>{tx.date_paid}</td>
                </tr>
              ))}
              {transactions.length === 0 && (
                <tr>
                  <td colSpan="7" className="py-4 text-center text-slate-500">No inventory payments yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}