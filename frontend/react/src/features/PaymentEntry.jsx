import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

export default function PaymentEntry({ students, onSuccess }) {
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
    inventory_item_id: '',
    inventory_quantity: 1
  });
  const [inventoryItems, setInventoryItems] = useState([]);
  const [uniformType, setUniformType] = useState('');
  const [uniformSize, setUniformSize] = useState('');

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
    if (!selectedStudent) {
      alert('Student not found. Please check the student ID or code.');
      return;
    }
    try {
      const paymentCategory = {};
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
      setForm({
        student_id: '',
        amount: '',
        type: 'Tuition',
        method: 'Cash',
        inventory_item_id: '',
        inventory_quantity: 1
      });
      setUniformType('');
      setUniformSize('');
    } catch (err) {
      alert(err.response?.data?.message || "Error recording payment.");
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <h3 className="font-bold text-lg mb-4 text-slate-800">💰 Record Payment</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="text"
          className="w-full p-2 border rounded-lg bg-gray-50"
          placeholder="Student ID or Code (e.g., 1 or S001)"
          value={form.student_id}
          onChange={e => setForm({ ...form, student_id: e.target.value })}
          required
        />

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
            setForm({...form, type: e.target.value, inventory_item_id: ''});
            setUniformType('');
            setUniformSize('');
          }} value={form.type}>
            <option value="Tuition">Tuition</option>
            <option value="Feeding">Feeding Fee</option>
            <option value="Transport">Transport</option>
            <option value="Terminal Report">Terminal Report</option>
            {canUseInventoryCatalog && <option value="Uniform">Uniform</option>}
            {canUseInventoryCatalog && <option value="Inventory">Inventory Item</option>}
          </select>
        </div>

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

        <button className="w-full bg-green-600 text-white py-2 rounded-lg font-bold hover:bg-green-700">
          Record Transaction
        </button>
      </form>
    </div>
  );
}