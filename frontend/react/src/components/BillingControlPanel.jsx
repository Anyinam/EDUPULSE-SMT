import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Shield, DollarSign, Settings, AlertCircle, CheckCircle, Repeat, CreditCard, Trash2, Plus, Star } from 'lucide-react';

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
  const [cardActionLoading, setCardActionLoading] = useState(false);
  const [autoBillingEnabled, setAutoBillingEnabled] = useState(false);
  const [hasAuthorization, setHasAuthorization] = useState(false);
  const [cards, setCards] = useState([]);
  const [defaultCardId, setDefaultCardId] = useState('');
  const [authorizationMeta, setAuthorizationMeta] = useState({
    authorization_last4: '',
    authorization_brand: '',
    authorization_bank: '',
    authorization_email: ''
  });

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

  const fetchAutoBilling = async () => {
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      const res = await axios.get('/api/school/subscription/auto-billing', { headers });
      setAutoBillingEnabled(Boolean(res.data.enabled));
      setHasAuthorization(Boolean(res.data.has_authorization));
      setCards(res.data.cards || []);
      setDefaultCardId(res.data.default_card_id || '');
      setAuthorizationMeta({
        authorization_last4: res.data.authorization_last4 || '',
        authorization_brand: res.data.authorization_brand || '',
        authorization_bank: res.data.authorization_bank || '',
        authorization_email: res.data.authorization_email || ''
      });
    } catch (err) {
      console.error('Failed to fetch auto-billing settings:', err);
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

  const handleSaveAutoBilling = async () => {
    if (autoBillingEnabled && !hasAuthorization) {
      alert('⚠️ No reusable payment authorization found yet. Complete at least one successful card payment first, then enable auto-billing.');
      return;
    }

    setSaving(true);
    try {
      const headers = {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id')
      };
      await axios.post('/api/school/subscription/auto-billing', {
        enabled: autoBillingEnabled
      }, { headers });
      alert('✅ Auto-billing settings saved successfully!');
      await fetchAutoBilling();
    } catch (err) {
      console.error('Failed to save auto-billing settings:', err);
      alert('❌ Failed to save auto-billing settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const getHeaders = () => ({
    'Authorization': `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id')
  });

  const handleSetDefaultCard = async (cardId) => {
    setCardActionLoading(true);
    try {
      await axios.post('/api/school/subscription/cards/default', { card_id: cardId }, { headers: getHeaders() });
      await fetchAutoBilling();
      alert('✅ Default card updated successfully.');
    } catch (err) {
      console.error('Failed to set default card:', err);
      alert('❌ Failed to update default card. Please try again.');
    } finally {
      setCardActionLoading(false);
    }
  };

  const handleRemoveCard = async (cardId) => {
    const confirmDelete = window.confirm('Remove this saved card from recurring billing?');
    if (!confirmDelete) return;

    setCardActionLoading(true);
    try {
      await axios.delete(`/api/school/subscription/cards/${cardId}`, { headers: getHeaders() });
      await fetchAutoBilling();
      alert('✅ Card removed successfully.');
    } catch (err) {
      console.error('Failed to remove card:', err);
      alert('❌ Failed to remove card. Please try again.');
    } finally {
      setCardActionLoading(false);
    }
  };

  const handleAddCard = async () => {
    setCardActionLoading(true);
    try {
      const res = await axios.post('/api/school/subscription/cards/setup-link', {
        amount_cedis: 1
      }, { headers: getHeaders() });

      const checkoutUrl = res.data.authorization_url;
      if (!checkoutUrl) {
        alert('❌ Failed to get Paystack card setup link.');
        return;
      }
      window.location.href = checkoutUrl;
    } catch (err) {
      console.error('Failed to initialize card setup:', err);
      alert('❌ Failed to start card setup. Please try again.');
    } finally {
      setCardActionLoading(false);
    }
  };

  const handleUnsubscribeAutoBilling = async () => {
    const confirmUnsubscribe = window.confirm('Disable recurring auto-billing now? You can enable it again anytime.');
    if (!confirmUnsubscribe) return;

    setCardActionLoading(true);
    try {
      await axios.post('/api/school/subscription/auto-billing/unsubscribe', {}, { headers: getHeaders() });
      await fetchAutoBilling();
      alert('✅ Recurring auto-billing disabled.');
    } catch (err) {
      console.error('Failed to unsubscribe auto-billing:', err);
      alert('❌ Failed to disable recurring auto-billing.');
    } finally {
      setCardActionLoading(false);
    }
  };

  useEffect(() => {
    fetchPriceCap();
    fetchAutoBilling();
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
        Manage recurring card billing for your pay-as-you-go subscription and keep spending predictable.
      </p>

      {/* Price Cap Section */}
      <div className="space-y-4">
        <div className="bg-linear-to-br from-emerald-50 to-teal-50 border-2 border-emerald-200 p-5 rounded-xl">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Repeat className="text-emerald-700" size={20} />
                <h4 className="font-bold text-emerald-900">Automatic Term Billing</h4>
              </div>
              <p className="text-sm text-emerald-800">
                Automatically charge recurring term fees from your default saved card. If unavailable, we fall back to manual payment links.
              </p>
            </div>

            <button
              onClick={() => setAutoBillingEnabled(!autoBillingEnabled)}
              className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
                autoBillingEnabled ? 'bg-emerald-600' : 'bg-slate-300'
              }`}
            >
              <span
                className={`inline-block h-6 w-6 transform rounded-full bg-white transition-transform ${
                  autoBillingEnabled ? 'translate-x-7' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          <div className={`p-3 rounded-lg border ${hasAuthorization ? 'bg-white border-emerald-200' : 'bg-amber-50 border-amber-300'}`}>
            {hasAuthorization ? (
              <div className="text-sm text-emerald-900">
                <p className="font-semibold mb-1">Reusable authorization detected</p>
                <p className="text-xs text-emerald-800">
                  {authorizationMeta.authorization_brand || 'Card'} •••• {authorizationMeta.authorization_last4 || '----'}
                  {authorizationMeta.authorization_bank ? ` (${authorizationMeta.authorization_bank})` : ''}
                </p>
                {authorizationMeta.authorization_email && (
                  <p className="text-xs text-emerald-700 mt-1">Billing email: {authorizationMeta.authorization_email}</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-amber-900 font-semibold">
                No reusable authorization saved yet. Complete one successful card payment first.
              </p>
            )}
          </div>

          <div className="mt-3 bg-white border border-emerald-200 rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-emerald-900">Saved Billing Cards</p>
              <button
                onClick={handleAddCard}
                disabled={cardActionLoading}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-xs font-semibold"
              >
                <Plus size={14} />
                Add New Card
              </button>
            </div>

            {cards.length === 0 ? (
              <p className="text-xs text-slate-600">
                No saved cards yet. Add a card to enable recurring pay-as-you-go billing.
              </p>
            ) : (
              <div className="space-y-2">
                {cards.map((card) => {
                  const isDefault = card.card_id === defaultCardId || card.is_default;
                  return (
                    <div key={card.card_id} className="border border-slate-200 rounded-lg p-2.5 bg-slate-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <CreditCard size={14} className="text-slate-600" />
                          <p className="text-xs font-semibold text-slate-800">
                            {card.brand || 'Card'} •••• {card.last4 || '----'}
                            {card.bank ? ` (${card.bank})` : ''}
                          </p>
                        </div>
                        {isDefault && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold">
                            <Star size={10} />
                            Default
                          </span>
                        )}
                      </div>

                      <div className="mt-2 flex items-center gap-2">
                        {!isDefault && (
                          <button
                            onClick={() => handleSetDefaultCard(card.card_id)}
                            disabled={cardActionLoading}
                            className="px-2 py-1 rounded bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-[11px] font-semibold"
                          >
                            Set Default
                          </button>
                        )}
                        <button
                          onClick={() => handleRemoveCard(card.card_id)}
                          disabled={cardActionLoading}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-rose-600 hover:bg-rose-700 disabled:bg-slate-300 text-white text-[11px] font-semibold"
                        >
                          <Trash2 size={12} />
                          Remove
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <button
            onClick={handleSaveAutoBilling}
            disabled={saving}
            className="w-full mt-3 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-xl font-bold transition-colors"
          >
            Save Auto-Billing Settings
          </button>

          <button
            onClick={handleUnsubscribeAutoBilling}
            disabled={cardActionLoading}
            className="w-full mt-2 py-2.5 bg-white border border-rose-300 hover:bg-rose-50 disabled:bg-slate-100 disabled:text-slate-400 text-rose-700 rounded-xl font-bold transition-colors"
          >
            Unsubscribe Auto-Billing
          </button>

          <p className="mt-2 text-[11px] text-emerald-900">
            Add/replace card uses a secure Paystack checkout with a small verification amount (GH₵1) to store reusable authorization.
          </p>
        </div>

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
