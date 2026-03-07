import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, DollarSign, Settings, AlertCircle, CheckCircle } from 'lucide-react';

/**
 * Billing Control Panel
 * Implements "Control" pillar from Metronome whitepaper
 * - Price Cap (Predictability)
 * - Overage Approval (Control)
 * - Budget Alerts (Visibility)
 */
export default function BillingControlPanel() {
  const [loading, setLoading] = useState(true);
  const [priceCapEnabled, setPriceCapEnabled] = useState(false);
  const [priceCapAmount, setPriceCapAmount] = useState(0);
  const [inputCapAmount, setInputCapAmount] = useState('');
  const [currentCost, setCurrentCost] = useState(0);
  const [saving, setSaving] = useState(false);

  const fetchPriceCap = async () => {
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.get('/api/school/subscription/price-cap', { headers });
      
      setPriceCapEnabled(res.data.price_cap_enabled || false);
      setPriceCapAmount(res.data.price_cap_amount || 0);
      setInputCapAmount(res.data.price_cap_amount || '');
      setCurrentCost(res.data.current_term_cost || 0);
    } catch (err) {
      console.error("Failed to fetch price cap:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSavePriceCap = async () => {
    const amount = parseFloat(inputCapAmount);
    
    if (priceCapEnabled && (!amount || amount <= 0)) {
      alert('⚠️ Please enter a valid price cap amount greater than 0');
      return;
    }
    
    if (priceCapEnabled && amount < currentCost) {
      const confirm = window.confirm(
        `⚠️ Warning: Your price cap (GH₵${amount}) is lower than your current term cost (GH₵${currentCost}).\n\n` +
        `This may prevent you from adding more students or upgrading.\n\n` +
        `Continue anyway?`
      );
      if (!confirm) return;
    }

    setSaving(true);
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      
      await axios.post('/api/school/subscription/price-cap', {
        enabled: priceCapEnabled,
        amount: priceCapEnabled ? amount : null
      }, { headers });
      
      alert('✅ Price cap settings saved successfully!');
      await fetchPriceCap(); // Refresh data
    } catch (err) {
      console.error("Failed to save price cap:", err);
      alert('❌ Failed to save price cap settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    fetchPriceCap();
  }, []);

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="animate-pulse">
          <div className="h-4 bg-slate-200 rounded w-1/3 mb-4"></div>
          <div className="h-20 bg-slate-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="text-blue-600" size={24} />
        <h3 className="text-lg font-bold text-slate-800">Billing Control & Protection</h3>
      </div>

      <p className="text-sm text-slate-600 mb-6">
        Set spending limits and manage your billing preferences to maintain budget predictability.
      </p>

      {/* Price Cap Section */}
      <div className="space-y-4">
        <div className="bg-linear-to-br from-blue-50 to-indigo-50 border-2 border-blue-200 p-5 rounded-xl">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="text-blue-600" size={20} />
                <h4 className="font-bold text-blue-900">Price Cap Protection</h4>
              </div>
              <p className="text-sm text-blue-700">
                Set a maximum spending limit to ensure your bill never exceeds a certain amount.
              </p>
            </div>
            
            {/* Toggle Switch */}
            <button
              onClick={() => setPriceCapEnabled(!priceCapEnabled)}
              className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
                priceCapEnabled ? 'bg-blue-600' : 'bg-slate-300'
              }`}
            >
              <span
                className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                  priceCapEnabled ? 'translate-x-7' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {priceCapEnabled && (
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">
                  Maximum Spending Per Term (GH₵)
                </label>
                <input
                  type="number"
                  value={inputCapAmount}
                  onChange={(e) => setInputCapAmount(e.target.value)}
                  placeholder="e.g., 1000"
                  min="0"
                  step="10"
                  className="w-full px-4 py-3 border-2 border-blue-300 rounded-lg text-lg font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div className="bg-white border border-blue-200 p-3 rounded-lg">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-slate-600">Current Term Cost:</span>
                  <span className="font-bold text-slate-800">GH₵ {currentCost.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">Your Price Cap:</span>
                  <span className="font-bold text-blue-600">
                    GH₵ {inputCapAmount || '0.00'}
                  </span>
                </div>
                
                {inputCapAmount && parseFloat(inputCapAmount) < currentCost && (
                  <div className="mt-2 bg-amber-50 border border-amber-300 p-2 rounded text-xs text-amber-800 flex items-start gap-2">
                    <AlertCircle className="shrink-0 mt-0.5" size={14} />
                    <span>
                      Your cap is lower than current cost. This will prevent additional charges.
                    </span>
                  </div>
                )}
                
                {inputCapAmount && parseFloat(inputCapAmount) >= currentCost && (
                  <div className="mt-2 bg-green-50 border border-green-300 p-2 rounded text-xs text-green-800 flex items-start gap-2">
                    <CheckCircle className="shrink-0 mt-0.5" size={14} />
                    <span>
                      You have GH₵ {(parseFloat(inputCapAmount) - currentCost).toFixed(2)} remaining budget.
                    </span>
                  </div>
                )}
              </div>

              <div className="bg-blue-100 border border-blue-300 p-3 rounded-lg">
                <p className="text-xs text-blue-800 font-semibold mb-2">
                  🛡️ How Price Cap Works:
                </p>
                <ul className="text-xs text-blue-700 space-y-1 list-disc list-inside">
                  <li>Your bill will never exceed the cap amount</li>
                  <li>When cap is reached, you won't be charged for additional students</li>
                  <li>You can still add students, but overage charges are waived</li>
                  <li>Update your cap anytime to adjust spending limits</li>
                </ul>
              </div>
            </div>
          )}

          {!priceCapEnabled && (
            <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
              <p className="text-sm text-slate-600">
                <strong>Price cap is disabled.</strong> You'll be charged based on actual usage with no spending limit.
              </p>
            </div>
          )}
        </div>

        {/* Save Button */}
        <button
          onClick={handleSavePriceCap}
          disabled={saving}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl font-bold transition-colors flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
              Saving...
            </>
          ) : (
            <>
              <Settings size={18} />
              Save Settings
            </>
          )}
        </button>

        {/* Info Box */}
        <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl">
          <div className="flex items-start gap-3">
            <Settings className="text-slate-500 shrink-0 mt-0.5" size={20} />
            <div className="text-sm text-slate-600">
              <p className="font-semibold text-slate-800 mb-2">💡 Billing Control Tips:</p>
              <ul className="space-y-1.5 list-disc list-inside">
                <li>Set a price cap to ensure predictable monthly billing</li>
                <li>Review your cap quarterly as your school grows</li>
                <li>Combine with student limit alerts for budget control</li>
                <li>Contact support for custom billing arrangements</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
