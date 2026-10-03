import React, { useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Search, ScanLine, Utensils } from 'lucide-react';
import FeatureLock from '../components/FeatureLock';
import useSubscription from '../hooks/useSubscription';

export default function PaymentEntry(props) {
  return <FeatureLock feature="payment_tracking" requiredPlan="Basic"><PaymentEntryContent {...props} /></FeatureLock>;
}

function PaymentEntryContent({ students, onSuccess }) {
  const { canAccess } = useSubscription();
  const canRecordFeeding = canAccess('feeding');
  const role = localStorage.getItem('role');
  const roles = (() => {
    try {
      return JSON.parse(localStorage.getItem('roles') || '[]');
    } catch (err) {
      return [];
    }
  })();
  const canUseInventoryCatalog = role === 'proprietor' || role === 'inventory_manager' || roles.includes('proprietor') || roles.includes('inventory_manager');
  const [form, setForm] = useState({
    student_id: '',
    amount: '',
    type: 'Tuition',
    method: 'Cash',
    feeding_frequency: 'Auto',
    inventory_item_id: '',
    inventory_quantity: 1
  });
  const [inventoryItems, setInventoryItems] = useState([]);
  const [uniformType, setUniformType] = useState('');
  const [uniformSize, setUniformSize] = useState('');
  const [studentQuery, setStudentQuery] = useState('');
  const [studentClass, setStudentClass] = useState('all');
  const studentSearchRef = useRef(null);

  const normalizeIdentifier = (value) =>
    String(value || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '');

  const parseCodeParts = (value) => {
    const normalized = normalizeIdentifier(value);
    const match = normalized.match(/^([a-z]+)(\d+)$/);
    if (!match) {
      return { normalized, prefix: null, number: null };
    }
    return {
      normalized,
      prefix: match[1],
      number: Number(match[2])
    };
  };

  const isCodeMatch = (inputValue, codeValue) => {
    const inputParts = parseCodeParts(inputValue);
    const codeParts = parseCodeParts(codeValue);

    if (!inputParts.normalized || !codeParts.normalized) return false;
    if (inputParts.normalized === codeParts.normalized) return true;

    return (
      inputParts.prefix &&
      codeParts.prefix &&
      inputParts.prefix === codeParts.prefix &&
      inputParts.number !== null &&
      codeParts.number !== null &&
      inputParts.number === codeParts.number
    );
  };

  const selectedStudent = useMemo(() => {
    const id = String(form.student_id).trim();
    if (!id) return null;

    return students.find(s => (
      String(s.id) === id ||
      String(s.student_id) === id ||
      isCodeMatch(id, s.student_code)
    )) || null;
  }, [form.student_id, students]);

  const studentClasses = useMemo(
    () => [...new Set(students.map(student => student.current_class).filter(Boolean))].sort(),
    [students]
  );

  const studentSuggestions = useMemo(() => {
    const query = studentQuery.trim().toLowerCase();
    if (!query || selectedStudent) return [];

    return students.filter((student) => {
      if (studentClass !== 'all' && student.current_class !== studentClass) return false;
      const name = String(student.name || '').toLowerCase();
      const initials = name.split(/\s+/).filter(Boolean).map(part => part[0]).join('');
      return name.includes(query)
        || initials.startsWith(query)
        || normalizeIdentifier(student.student_code).includes(normalizeIdentifier(query));
    }).slice(0, 8);
  }, [selectedStudent, studentClass, studentQuery, students]);

  const getFeedingAmount = (student, frequency) => {
    if (!student) return '';
    const feeByFrequency = {
      Daily: student.feeding_daily_fee,
      Weekly: student.feeding_weekly_fee,
      Monthly: student.feeding_monthly_fee,
    };
    const amount = Number(feeByFrequency[frequency] || 0);
    return amount > 0 ? String(amount) : '';
  };

  const selectStudent = (student) => {
    setStudentQuery(`${student.name}${student.student_code ? ` · ${student.student_code}` : ''}`);
    setForm((current) => ({
      ...current,
      student_id: String(student.id),
      amount: current.type === 'Feeding'
        ? (getFeedingAmount(student, current.feeding_frequency) || current.amount)
        : current.amount,
    }));
  };

  const enableDailyFeeding = () => {
    if (!canRecordFeeding) return;
    setForm((current) => ({
      ...current,
      type: 'Feeding',
      method: 'Cash',
      feeding_frequency: 'Daily',
      amount: getFeedingAmount(selectedStudent, 'Daily') || current.amount,
    }));
    studentSearchRef.current?.focus();
  };

  const headers = useMemo(() => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  }), []);

  useEffect(() => {
    if (!canUseInventoryCatalog) {
      setInventoryItems([]);
      return;
    }
    if (form.type !== 'Inventory' && form.type !== 'Uniform') {
      return;
    }
    if (inventoryItems.length > 0) {
      return;
    }

    const fetchInventory = async () => {
      try {
        const res = await axios.get('/api/inventory', { headers });
        setInventoryItems(Array.isArray(res.data) ? res.data : []);
      } catch (err) {
        setInventoryItems([]);
      }
    };
    fetchInventory();
  }, [canUseInventoryCatalog, form.type, headers, inventoryItems.length]);

  const uniformItems = useMemo(
    () => inventoryItems.filter(i => (i.category || '').toLowerCase() === 'uniform'),
    [inventoryItems]
  );

  const uniformCandidates = useMemo(() => {
    return uniformItems.filter(i =>
      (!uniformType || i.item_type === uniformType) &&
      (!uniformSize || i.size === uniformSize)
    );
  }, [uniformItems, uniformType, uniformSize]);

  const uniformTypes = useMemo(
    () => [...new Set(uniformItems.map(i => i.item_type).filter(Boolean))],
    [uniformItems]
  );

  const uniformSizes = useMemo(
    () => [...new Set(uniformItems.map(i => i.size).filter(Boolean))],
    [uniformItems]
  );

  const selectedInventoryItem = useMemo(() => {
    if (form.type === 'Uniform') {
      return uniformItems.find(i => i.item_type === uniformType && i.size === uniformSize) || null;
    }
    if (form.type === 'Inventory') {
      const id = String(form.inventory_item_id).trim();
      if (!id) return null;
      return inventoryItems.find(i => String(i.id) === id) || null;
    }
    return null;
  }, [form.type, form.inventory_item_id, uniformType, uniformSize, uniformItems, inventoryItems]);

  useEffect(() => {
    if (form.type !== 'Uniform') return;
    if (!uniformType || !uniformSize) return;
    if (uniformCandidates.length === 1) {
      setForm((prev) => ({ ...prev, inventory_item_id: String(uniformCandidates[0].id) }));
    }
  }, [form.type, uniformType, uniformSize, uniformCandidates]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (form.type === 'Feeding' && !canRecordFeeding) return;
    if (!selectedStudent) {
      alert('Student not found. Please check the student ID or code.');
      return;
    }
    try {
      const paymentCategory = {};
      if (form.type === 'Feeding' && form.feeding_frequency && form.feeding_frequency !== 'Auto') {
        paymentCategory.frequency = form.feeding_frequency;
      }
      if (form.type === 'Inventory' || form.type === 'Uniform') {
        if (!selectedInventoryItem) {
          alert('Please select a valid inventory item.');
          return;
        }
        paymentCategory.item_id = selectedInventoryItem.id;
        paymentCategory.item_name = selectedInventoryItem.item_name;
        paymentCategory.item_type = selectedInventoryItem.item_type;
        paymentCategory.size = selectedInventoryItem.size;
        paymentCategory.sku = selectedInventoryItem.sku;
        paymentCategory.quantity = Number(form.inventory_quantity || 1);
      }

      await axios.post('/api/finance/receive-payment', {
        ...form,
        student_id: selectedStudent.id,
        amount: form.amount || (selectedInventoryItem ? selectedInventoryItem.price : ''),
        payment_category: paymentCategory
      }, { headers });
      alert("Payment Recorded Successfully!");
      if (onSuccess) onSuccess();
      const keepFeedingMode = form.type === 'Feeding';
      setForm({
        student_id: '',
        amount: keepFeedingMode ? form.amount : '',
        type: keepFeedingMode ? 'Feeding' : 'Tuition',
        method: keepFeedingMode ? form.method : 'Cash',
        feeding_frequency: keepFeedingMode ? form.feeding_frequency : 'Auto',
        inventory_item_id: '',
        inventory_quantity: 1
      });
      setStudentQuery('');
      setUniformType('');
      setUniformSize('');
      window.setTimeout(() => studentSearchRef.current?.focus(), 0);
    } catch (err) {
      alert(err.response?.data?.message || "Error recording payment.");
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-bold text-lg text-slate-800">Record Payment</h3>
        <button
          type="button"
          onClick={enableDailyFeeding}
          disabled={!canRecordFeeding}
          className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-bold ${form.type === 'Feeding' && form.feeding_frequency === 'Daily' ? 'bg-emerald-700 text-white' : 'border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100'}`}
        >
          <Utensils size={17} />
          Daily Feeding
        </button>
      </div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
          <div className="relative">
            <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              ref={studentSearchRef}
              type="text"
              className="w-full rounded-lg border bg-gray-50 py-2 pl-9 pr-10"
              placeholder="Search name, initials, code, or scan"
              value={studentQuery}
              onChange={(event) => {
                setStudentQuery(event.target.value);
                setForm((current) => ({ ...current, student_id: event.target.value }));
              }}
              autoComplete="off"
              required
            />
            <ScanLine size={18} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" title="Barcode or QR scanner input" />
            {studentSuggestions.length > 0 && (
              <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
                {studentSuggestions.map((student) => (
                  <button key={student.id} type="button" onClick={() => selectStudent(student)} className="flex w-full items-center justify-between gap-3 border-b border-slate-100 px-3 py-3 text-left last:border-b-0 hover:bg-emerald-50">
                    <span>
                      <span className="block text-sm font-bold text-slate-800">{student.name}</span>
                      <span className="block text-xs text-slate-500">{student.student_code || 'No code'}</span>
                    </span>
                    <span className="text-xs font-semibold text-slate-500">{student.current_class || 'No class'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <select value={studentClass} onChange={(event) => setStudentClass(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="all">All classes</option>
            {studentClasses.map((className) => <option key={className} value={className}>{className}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            className="p-2 border rounded-lg bg-gray-50"
            placeholder="Student Name"
            value={selectedStudent ? selectedStudent.name : ''}
            readOnly
          />
          <input
            type="text"
            className="p-2 border rounded-lg bg-gray-50"
            placeholder="Class"
            value={selectedStudent ? selectedStudent.current_class : ''}
            readOnly
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <input type="number" placeholder="Amount (GH₵)" className="p-2 border rounded-lg" 
            value={form.amount} onChange={e => setForm({...form, amount: e.target.value})} required={form.type !== 'Inventory' && form.type !== 'Uniform'} />
          <select className="p-2 border rounded-lg" onChange={e => {
            setForm({...form, type: e.target.value, inventory_item_id: '', feeding_frequency: 'Auto'});
            setUniformType('');
            setUniformSize('');
          }} value={form.type}>
            <option value="Tuition">Tuition</option>
            <option value="Feeding" disabled={!canRecordFeeding}>Feeding Fee</option>
            <option value="Transport">Transport</option>
            <option value="Terminal Report">Terminal Report</option>
            {canUseInventoryCatalog && <option value="Uniform">Uniform</option>}
            {canUseInventoryCatalog && <option value="Inventory">Inventory Item</option>}
          </select>
        </div>

        {form.type === 'Feeding' && (
          <div className="space-y-2 rounded-lg border border-emerald-100 bg-emerald-50 p-3">
            <div className="grid grid-cols-2 gap-2">
              <select
                className="p-2 border rounded-lg bg-white"
                value={form.feeding_frequency}
                onChange={(event) => setForm({
                  ...form,
                  feeding_frequency: event.target.value,
                  amount: getFeedingAmount(selectedStudent, event.target.value) || form.amount,
                })}
              >
                <option value="Auto">Feeding Plan: Auto Detect</option>
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
                <option value="Monthly">Monthly</option>
              </select>
              <input
                type="text"
                className="p-2 border rounded-lg bg-gray-50"
                value={selectedStudent ? [
                  selectedStudent.feeding_daily_fee ? `Daily GH₵${Number(selectedStudent.feeding_daily_fee).toFixed(2)}` : null,
                  selectedStudent.feeding_weekly_fee ? `Weekly GH₵${Number(selectedStudent.feeding_weekly_fee).toFixed(2)}` : null,
                  selectedStudent.feeding_monthly_fee ? `Monthly GH₵${Number(selectedStudent.feeding_monthly_fee).toFixed(2)}` : null,
                ].filter(Boolean).join(' • ') : ''}
                placeholder="Configured feeding plans"
                readOnly
              />
            </div>
            <p className="text-xs text-emerald-800">
              Leave this on Auto Detect and EduPulse will infer the correct feeding coverage from the approved amount.
            </p>
          </div>
        )}

        {form.type === 'Uniform' && (
          <div className="grid grid-cols-2 gap-2">
            <select
              className="p-2 border rounded-lg"
              value={uniformType}
              onChange={e => setUniformType(e.target.value)}
              required
            >
              <option value="">Uniform Type</option>
              {uniformTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            <select
              className="p-2 border rounded-lg"
              value={uniformSize}
              onChange={e => setUniformSize(e.target.value)}
              required
            >
              <option value="">Size</option>
              {uniformSizes.map(size => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </div>
        )}

        {(form.type === 'Inventory' || form.type === 'Uniform') && (
          <div className="grid grid-cols-2 gap-2">
            <select
              className="p-2 border rounded-lg"
              value={form.inventory_item_id}
              onChange={e => setForm({ ...form, inventory_item_id: e.target.value })}
              required
            >
              <option value="">Select Item</option>
              {(form.type === 'Uniform' ? uniformCandidates : inventoryItems).map(item => (
                <option key={item.id} value={item.id}>
                  {item.item_name} {item.item_type ? `- ${item.item_type}` : ''} {item.size ? `(${item.size})` : ''}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              className="p-2 border rounded-lg"
              value={form.inventory_quantity}
              onChange={e => setForm({ ...form, inventory_quantity: e.target.value })}
              placeholder="Qty"
              required
            />
          </div>
        )}

        {selectedInventoryItem && (form.type === 'Inventory' || form.type === 'Uniform') && (
          <div className="text-xs text-slate-600">
            Selected: {selectedInventoryItem.item_name} {selectedInventoryItem.item_type ? `- ${selectedInventoryItem.item_type}` : ''} {selectedInventoryItem.size ? `(${selectedInventoryItem.size})` : ''} • GH₵ {Number(selectedInventoryItem.price || 0).toFixed(2)}
          </div>
        )}

        <button disabled={form.type === 'Feeding' && !canRecordFeeding} className="w-full bg-green-600 text-white py-2 rounded-lg font-bold hover:bg-green-700">
          {form.type === 'Feeding' ? 'Record Feeding' : 'Record Transaction'}
        </button>
      </form>
    </div>
  );
}