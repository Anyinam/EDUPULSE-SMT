import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, TrendingUp, Users, Calendar, DollarSign, Tag, Info } from 'lucide-react';
import BillingVisibility from '../components/BillingVisibility';
import TrialManager from '../components/TrialManager';
import BillingControlPanel from '../components/BillingControlPanel';

export default function SubscriptionManager() {
  const [sub, setSub] = useState(null);
  const [planCatalog, setPlanCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [billingPeriod, setBillingPeriod] = useState('term');
  const [prorateInfo, setProrateInfo] = useState(null);
  const [billingRestriction, setBillingRestriction] = useState(null);

  const PLAN_ORDER = {
    'Free Tier': 0,
    'Basic': 1,
    'Premium': 2,
  };

  useEffect(() => {
    const fetchSub = async () => {
      setLoading(true);
      setLoadError('');
      try {
        const headers = getSubscriptionHeaders();
        if (!headers) {
          setLoadError('Your session expired. Please log in again.');
          setLoading(false);
          return;
        }
        const [res, plansRes] = await Promise.all([
          axios.get('/api/school/subscription', { headers }),
          axios.get('/api/subscription/plans'),
        ]);
        setSub({
          ...res.data,
          next_billing_date: res.data?.next_billing_date || res.data?.next_billing || null,
        });
        setPlanCatalog(plansRes.data?.plans || []);
      } catch (err) {
        console.error('Failed to fetch subscription', err);
        setSub(null);
        setLoadError(err.response?.data?.message || 'Failed to load subscription details.');
      } finally {
        setLoading(false);
      }
    };
    fetchSub();
  }, []);

  const redirectToLogin = (message = 'Your session expired. Please log in again to manage your subscription.') => {
    alert(message);
    window.location.href = '/login';
  };

  const getSubscriptionHeaders = () => {
    const token = localStorage.getItem('token');
    const schoolId = localStorage.getItem('school_id');

    if (!token || !schoolId) {
      return null;
    }

    return {
      'Authorization': `Bearer ${token}`,
      'X-School-ID': schoolId,
    };
  };

  const handleSubscriptionError = (err, fallbackMessage) => {
    if (err?.response?.status === 401) {
      redirectToLogin();
      return;
    }

    if (err?.response?.status === 403) {
      alert(err.response?.data?.message || 'Only the proprietor account can change subscription plans.');
      return;
    }

    alert(err?.response?.data?.message || fallbackMessage);
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('billing') !== 'blocked') {
      return;
    }

    try {
      const raw = sessionStorage.getItem('billing_restriction');
      if (raw) {
        const parsed = JSON.parse(raw);
        setBillingRestriction(parsed);
      }
    } catch (_err) {
      setBillingRestriction(null);
    }
  }, []);

  // Calculate proration info on mount/plan change
  useEffect(() => {
    if (sub) {
      calculateProration();
    }
  }, [sub, billingPeriod]);

  const calculateProration = () => {
    const now = new Date();
    if (sub.next_billing_date) {
      const nextBilling = new Date(sub.next_billing_date);
      const daysRemaining = Math.floor((nextBilling - now) / (1000 * 60 * 60 * 24));
      const daysInTerm = 120;

      if (daysRemaining > 0 && daysRemaining < daysInTerm) {
        const prorateRatio = daysRemaining / daysInTerm;
        setProrateInfo({
          daysRemaining,
          daysInTerm,
          prorateRatio: parseFloat(prorateRatio.toFixed(2)),
          sourceLabel: 'current billing cycle',
        });
        return;
      }
    }

    const termProration = sub.term_proration || {};
    const daysRemaining = Number(termProration.days_remaining || 0);
    const daysInTerm = Number(termProration.days_in_term || 0);
    const prorateRatio = Number(termProration.proration_ratio || 0);

    if (daysRemaining > 0 && daysInTerm > 0 && daysRemaining < daysInTerm && sub.plan === 'Free Tier') {
      setProrateInfo({
        daysRemaining,
        daysInTerm,
        prorateRatio: parseFloat(prorateRatio.toFixed(2)),
        sourceLabel: 'remaining current-term days',
      });
      return;
    }

    setProrateInfo(null);
  };

  const handleUpgrade = async (plan, cost) => {
    const currentRank = PLAN_ORDER[sub?.plan] ?? 0;
    const nextRank = PLAN_ORDER[plan] ?? 0;
    const isDowngrade = nextRank < currentRank;

    if (isDowngrade) {
      const confirmLabel = plan === 'Free Tier' ? 'Downgrade to Free Tier' : `Switch to ${plan}`;
      if (!window.confirm(`${confirmLabel}? Your paid features will be reduced immediately.`)) return;
      const headers = getSubscriptionHeaders();
      if (!headers) {
        redirectToLogin();
        return;
      }
      try {
        await axios.post('/api/school/subscription/upgrade', { plan }, { headers });
        
        // Refresh subscription data from backend
        const schoolRes = await axios.get('/api/school/subscription', { headers });
        if (schoolRes.data) {
          // Update localStorage with new plan
          const newPlan = schoolRes.data.subscription_plan || schoolRes.data.plan || 'Free Tier';
          localStorage.setItem('subscription_plan', newPlan);
          
          // Update enabled modules
          if (schoolRes.data.enabled_modules) {
            localStorage.setItem('enabled_modules', JSON.stringify(schoolRes.data.enabled_modules));
          }
        }
        
        alert(`Plan changed to ${plan} successfully.`);
        window.location.reload();  // Full reload to update all components
      } catch (err) {
        handleSubscriptionError(err, 'Plan change failed.');
      }
      return;
    }

    // Calculate prorated cost if applicable
    let finalCost = cost;
    let proratedMsg = '';
    if (prorateInfo) {
      finalCost = cost * prorateInfo.prorateRatio;
      proratedMsg = `\n\n💰 PRORATED INITIAL CHARGE:\n${prorateInfo.daysRemaining} days remaining in ${prorateInfo.sourceLabel}\nInitial charge: GH₵ ${finalCost.toFixed(2)}`;
    }

    // Paid plans: Initialize Paystack payment
    const confirmMsg = `Upgrade to ${plan}?${proratedMsg}\n\nCost: GH₵ ${finalCost.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} for ${billingPeriod === 'term' ? '1 term' : '3 terms (annual)'}\nBased on ${currentStudents} students`;
    if (!window.confirm(confirmMsg)) return;

    const headers = getSubscriptionHeaders();
    if (!headers) {
      redirectToLogin();
      return;
    }

    try {
      // Initialize payment with Paystack
      const res = await axios.post('/api/paystack/initialize', {
        plan_name: plan,
        billing_period: billingPeriod,
        student_count: currentStudents,
        amount_cedis: finalCost  // Send prorated cost
      }, { headers });

      if (res.data.status === 'success' && res.data.data.authorization_url) {
        // Redirect to Paystack payment page
        window.location.href = res.data.data.authorization_url;
      } else {
        alert('Failed to initialize payment. Please try again.');
      }
    } catch (err) {
      console.error('Payment initialization error:', err);
      handleSubscriptionError(err, 'Failed to initialize payment. Please try again.');
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-slate-600">Loading subscription details...</p>
      </div>
    </div>
  );

  if (!sub) return (
    <div className="flex items-center justify-center h-96">
      <div className="max-w-md rounded-2xl border border-red-200 bg-red-50 p-6 text-center shadow-sm">
        <p className="text-lg font-bold text-red-900 mb-2">Subscription details unavailable</p>
        <p className="text-sm text-red-700 mb-4">{loadError || 'The subscription page could not be loaded.'}</p>
        <button
          onClick={() => window.location.reload()}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    </div>
  );

  // Auto-detect current student enrollment
  const currentStudents = sub.current_enrollment || 0;
  
  const plans = (planCatalog || []).map((plan) => {
    const baseFee = Number(plan.base_fee_per_term || 0);
    const included = Number(plan.included_students || 0);
    const price = Number(plan.price_per_student_per_term || 0);
    const overage = Math.max(0, currentStudents - included);
    const termCost = plan.name === 'Free Tier' ? 0 : baseFee + (overage * price);

    return {
      name: plan.name,
      price,
      baseFee,
      included,
      overage,
      termCost,
      annualCost: termCost * 3,
      description: plan.description,
      color: plan.ui_color || 'gray',
      popular: Boolean(plan.popular),
      recommended: false,
      features: plan.marketing_features || [],
      addonOptions: plan.addon_options || [],
      packagingSummary: plan.packaging_summary || '',
    };
  });

  const basicPlan = plans.find((plan) => plan.name === 'Basic');
  const premiumPlan = plans.find((plan) => plan.name === 'Premium');

  return (
    <div className="bg-linear-to-br from-slate-50 to-blue-50 min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-black text-slate-800 mb-2">Subscription & Billing</h1>
          <p className="text-slate-600">
            💡 <strong>Pay-as-you-go recurring billing:</strong> Paid plans charge base fee first, then termly overage from active students using your saved recurring card (or manual link fallback).
          </p>
        </div>

        {billingRestriction && (
          <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3">
            <p className="text-sm font-semibold text-amber-900">
              Billing action required: your account is currently {billingRestriction.status || 'restricted'}.
            </p>
            <p className="mt-1 text-xs text-amber-800">
              Settle outstanding subscription fees below to unlock full platform access.
            </p>
          </div>
        )}

        {sub?.pending_plan === 'Free Tier' && sub?.next_billing_date && (
          <div className="mb-6 rounded-xl border border-blue-300 bg-blue-50 px-4 py-4">
            <p className="text-sm font-semibold text-blue-900">
              Pending downgrade to Free Tier on {new Date(sub.next_billing_date).toLocaleDateString()}.
            </p>
            <p className="mt-1 text-xs text-blue-800">
              Your current paid plan remains active until the next billing date. After that, the system will switch the school to Free Tier and paid features will stop unless you renew or change plan again.
            </p>
          </div>
        )}

        {/* Current Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="text-blue-600" size={20} />
              <p className="text-xs font-bold text-slate-500 uppercase">Current Plan</p>
            </div>
            <p className="text-2xl font-black text-blue-900">{sub.plan}</p>
            <span className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-bold ${
              sub.status === 'Active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>
              {sub.status}
            </span>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Users className="text-purple-600" size={20} />
              <p className="text-xs font-bold text-slate-500 uppercase">Current Enrollment</p>
            </div>
            <p className="text-2xl font-black text-slate-800">{currentStudents}</p>
            <p className="text-xs text-slate-500 mt-1">Students</p>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="text-green-600" size={20} />
              <p className="text-xs font-bold text-slate-500 uppercase">This Term</p>
            </div>
            <p className="text-2xl font-black text-slate-700">
              GH₵ {(sub.term_cost || 0).toLocaleString()}
            </p>
            <p className="text-xs text-slate-500 mt-1">N/A</p>
          </div>

          <div className="bg-linear-to-br from-blue-500 to-blue-600 text-white p-6 rounded-2xl shadow-lg">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="text-blue-100" size={20} />
              <p className="text-xs font-bold text-blue-100 uppercase">Annual Cost</p>
            </div>
            <p className="text-2xl font-black">
              GH₵ {((sub.term_cost || 0) * 3).toLocaleString()}
            </p>
            <p className="text-xs text-blue-100 mt-1">3 terms per year</p>
          </div>
        </div>

        {/* Billing Visibility Widget */}
        <div className="mb-8">
          <BillingVisibility />
        </div>

        {/* Trial Management Widget */}
        <div className="mb-8">
          <TrialManager />
        </div>

        {/* Billing Control Panel (Price Cap, etc.) */}
        <div className="mb-8">
          <BillingControlPanel />
        </div>

        {/* Billing Period Toggle */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex bg-white rounded-xl p-1 shadow-sm border border-slate-200">
            <button
              onClick={() => setBillingPeriod('term')}
              className={`px-6 py-2 rounded-lg font-bold text-sm transition-all ${
                billingPeriod === 'term'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              Per Term
            </button>
            <button
              onClick={() => setBillingPeriod('annual')}
              className={`px-6 py-2 rounded-lg font-bold text-sm transition-all ${
                billingPeriod === 'annual'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              Annual (3 Terms)
            </button>
          </div>
        </div>

        {/* Plans Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {plans.map((plan) => {
            const isCurrentPlan = sub.plan === plan.name;
            const displayCost = billingPeriod === 'term' ? plan.termCost : plan.annualCost;
            const currentRank = PLAN_ORDER[sub.plan] ?? 0;
            const targetRank = PLAN_ORDER[plan.name] ?? 0;
            const isUpgrade = targetRank > currentRank;
            const isDowngrade = targetRank < currentRank;
            const shouldShowProration = !isCurrentPlan && isUpgrade && prorateInfo && plan.name !== 'Free Tier';
            const actionAmount = shouldShowProration ? displayCost * prorateInfo.prorateRatio : displayCost;
            const displayBaseFee = billingPeriod === 'term' ? plan.baseFee : plan.baseFee * 3;
            const displayPerStudentPrice = billingPeriod === 'term' ? plan.price : plan.price * 3;
            
            return (
              <div
                key={plan.name}
                className={`relative bg-white rounded-2xl border-2 p-6 transition-all ${
                  isCurrentPlan
                    ? 'border-blue-500 shadow-xl ring-4 ring-blue-100'
                    : 'border-slate-200 hover:border-blue-300 hover:shadow-lg'
                }`}
              >
                {plan.popular && !isCurrentPlan && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-blue-600 text-white text-xs font-bold px-4 py-1 rounded-full shadow-lg">
                    MOST POPULAR
                  </div>
                )}
                {isCurrentPlan && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-green-600 text-white text-xs font-bold px-4 py-1 rounded-full shadow-lg flex items-center gap-1">
                    <CheckCircle size={14} /> CURRENT PLAN
                  </div>
                )}

                <h3 className="text-xl font-bold text-slate-800 mb-2 mt-2">{plan.name}</h3>
                <p className="text-sm text-slate-600 mb-4">{plan.description}</p>

                <div className="mb-6">
                  {plan.name === 'Free Tier' ? (
                    <>
                      <div className="text-4xl font-black text-slate-800">GH₵ 0</div>
                      <div className="text-sm text-slate-500">Forever</div>
                    </>
                  ) : (
                    <>
                      <div className="text-4xl font-black text-slate-800">
                        GH₵ {displayCost.toLocaleString()}
                      </div>
                      <div className="text-sm text-slate-600">
                        Base GH₵ {displayBaseFee.toLocaleString()} covers {plan.included} students; overage is GH₵ {displayPerStudentPrice.toLocaleString()}/student/{billingPeriod === 'term' ? 'term' : 'year (3 terms)'}
                      </div>
                      {plan.baseFee !== undefined && billingPeriod === 'term' && (
                        <div className="text-xs text-slate-500 mt-2 space-y-0.5">
                          <div>Base: ₵{plan.baseFee} + {plan.included} included</div>
                          {plan.overage > 0 && (
                            <div>Overage: {plan.overage} × ₵{plan.price} = ₵{(plan.overage * plan.price).toLocaleString()}</div>
                          )}
                        </div>
                      )}
                      {billingPeriod === 'term' && (
                        <div className="text-xs text-slate-500 mt-1">
                          GH₵ {plan.annualCost.toLocaleString()}/year (3 terms)
                        </div>
                      )}
                    </>
                  )}
                </div>

                <ul className="space-y-3 mb-6">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm">
                      {feature.included ? (
                        <CheckCircle className="text-green-600 shrink-0 mt-0.5" size={18} />
                      ) : (
                        <XCircle className="text-slate-300 shrink-0 mt-0.5" size={18} />
                      )}
                      <span className={feature.included ? 'text-slate-700' : 'text-slate-400'}>
                        {feature.name} {feature.note && <span className="text-xs italic">{feature.note}</span>}
                      </span>
                    </li>
                  ))}
                </ul>

                {plan.packagingSummary && (
                  <p className="mb-6 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    {plan.packagingSummary}
                  </p>
                )}

                {plan.addonOptions.length > 0 && (
                  <div className="mb-6 border-t border-slate-100 pt-4">
                    <p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Future Add-Ons</p>
                    <p className="mb-2 text-xs text-slate-500">These are future optional products. They are not included in this subscription price.</p>
                    <div className="flex flex-wrap gap-2">
                      {plan.addonOptions.map((addon) => (
                        <span key={addon} className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">
                          {addon}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Proration Banner - Only show if applicable */}
                {shouldShowProration && (
                  <div className="mb-6 bg-amber-50 border border-amber-300 rounded-lg p-3">
                    <div className="flex items-start gap-2">
                      <Tag className="text-amber-600 shrink-0 mt-0.5" size={16} />
                      <div className="text-sm">
                        <p className="font-bold text-amber-900">Prorated Initial Charge</p>
                        <p className="text-amber-800 text-xs mt-1">
                          {prorateInfo.daysRemaining} days remaining in {prorateInfo.sourceLabel}
                        </p>
                        <p className="text-amber-900 font-bold text-xs mt-1">
                          Initial charge: GH₵ {(displayCost * prorateInfo.prorateRatio).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {!isCurrentPlan && (
                  <button
                    onClick={() => handleUpgrade(plan.name, displayCost)}
                    className={`w-full py-3 rounded-xl font-bold transition-all ${
                      plan.name === 'Premium'
                        ? 'bg-linear-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700 shadow-lg'
                        : plan.name === 'Basic'
                        ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-md'
                        : 'border-2 border-slate-300 text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    {isDowngrade
                      ? plan.name === 'Free Tier'
                        ? 'Switch to Free'
                        : `Switch to ${plan.name}`
                      : `Pay GH₵ ${actionAmount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Billing Explanation */}
        <div className="bg-linear-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-2xl p-6 mb-6">
          <h4 className="font-bold text-blue-900 mb-3 flex items-center gap-2">
            <Info className="text-blue-600" size={20} />
            💰 How Billing is Calculated
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800 mb-4">
            <div className="bg-white rounded-lg p-3 border border-blue-100">
              <p className="font-bold text-blue-900 mb-2">📊 Full Cost Formula</p>
              <p className="font-mono text-xs text-slate-700 mb-2">
                <strong>Base Fee + (Students Above Included × Price/Student)</strong>
              </p>
              <p className="text-xs">
                Example: <strong>GH₵ {basicPlan?.baseFee || 0} + (70 × GH₵ {basicPlan?.price || 0}) = GH₵ {basicPlan ? (basicPlan.baseFee + (70 * basicPlan.price)).toLocaleString() : '0'}/term</strong>
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 border border-blue-100">
              <p className="font-bold text-blue-900 mb-2">⏱️ Prorated (Mid-Term)</p>
              <p className="font-mono text-xs text-slate-700 mb-2">
                <strong>Full Cost × (Days Remaining / 120)</strong>
              </p>
              <p className="text-xs">
                Example: Upgrade late in the term? <strong>Your first charge only covers the remaining current-term days</strong>
              </p>
            </div>
          </div>
          <div className="bg-blue-100 border border-blue-300 rounded-lg p-3">
            <p className="text-xs font-bold text-blue-900 mb-2">🎯 Your Current Billing:</p>
            <div className="text-xs text-blue-800 space-y-1">
              <p>• <strong>Current Plan:</strong> {sub?.plan}</p>
              <p>• <strong>Active Students:</strong> {currentStudents}</p>
              <p>• <strong>Next Billing:</strong> {sub?.next_billing_date ? new Date(sub.next_billing_date).toLocaleDateString() : 'N/A'}</p>
              {prorateInfo && (
                <p className="font-bold text-amber-600 mt-2">• <strong>Prorated initial charge:</strong> based on {prorateInfo.daysRemaining} remaining day(s) in the {prorateInfo.sourceLabel}</p>
              )}
            </div>
          </div>
        </div>

        {/* Termly Billing Info */}
        <div className="bg-linear-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-2xl p-6">
          <h4 className="font-bold text-blue-900 mb-3 flex items-center gap-2">
            <Calendar className="text-blue-600" size={20} />
            How Termly Billing Works
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-blue-800">
            <ul className="space-y-2">
              <li className="flex items-start gap-2">
                <CheckCircle className="text-blue-600 shrink-0 mt-0.5" size={16} />
                <span>Schools operate on <strong>3 terms per academic year</strong></span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="text-blue-600 shrink-0 mt-0.5" size={16} />
                <span>Pay at the <strong>start of each term</strong> based on enrollment</span>
              </li>
            </ul>
            <ul className="space-y-2">
              <li className="flex items-start gap-2">
                <CheckCircle className="text-blue-600 shrink-0 mt-0.5" size={16} />
                <span>No monthly surprises - aligns with when parents pay fees</span>
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="text-blue-600 shrink-0 mt-0.5" size={16} />
                <span>Example: 100 students on Premium = <strong>GH₵ {premiumPlan ? (premiumPlan.baseFee + (Math.max(0, 100 - premiumPlan.included) * premiumPlan.price)).toLocaleString() : '0'}/term</strong></span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
