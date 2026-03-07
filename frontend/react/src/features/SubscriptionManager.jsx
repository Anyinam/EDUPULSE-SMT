import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, TrendingUp, Users, Calendar, DollarSign, Tag, Info } from 'lucide-react';
import BillingVisibility from '../components/BillingVisibility';
import TrialManager from '../components/TrialManager';
import BillingControlPanel from '../components/BillingControlPanel';

export default function SubscriptionManager() {
  const [sub, setSub] = useState(null);
  const [billingPeriod, setBillingPeriod] = useState('term');
  const [prorateInfo, setProrateInfo] = useState(null);

  useEffect(() => {
    const fetchSub = async () => {
      try {
        const headers = { 
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id') 
        };
        const res = await axios.get('/api/school/subscription', { headers });
        setSub(res.data);
      } catch (err) {
        console.error("Failed to fetch subscription");
      }
    };
    fetchSub();
  }, []);

  // Calculate proration info on mount/plan change
  useEffect(() => {
    if (sub) {
      calculateProration();
    }
  }, [sub, billingPeriod]);

  const calculateProration = () => {
    if (!sub.next_billing_date) return;

    const now = new Date();
    const nextBilling = new Date(sub.next_billing_date);
    const daysRemaining = Math.floor((nextBilling - now) / (1000 * 60 * 60 * 24));
    const daysInTerm = 120; // ~4 months

    if (daysRemaining > 0 && daysRemaining < daysInTerm) {
      const prorateRatio = daysRemaining / daysInTerm;
      setProrateInfo({
        daysRemaining,
        daysInTerm,
        prorateRatio: parseFloat(prorateRatio.toFixed(2)),
        discount: parseFloat(((1 - prorateRatio) * 100).toFixed(0))
      });
    } else {
      setProrateInfo(null);
    }
  };

  const handleUpgrade = async (plan, cost) => {
    // Free Tier: Direct downgrade (no payment required)
    if (plan === 'Free Tier') {
      if (!window.confirm('Downgrade to Free Tier? You will lose premium features.')) return;
      try {
        const headers = { 
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'X-School-ID': localStorage.getItem('school_id') 
        };
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
        
        alert("Plan downgraded successfully!");
        window.location.reload();  // Full reload to update all components
      } catch (err) {
        alert("Downgrade failed.");
      }
      return;
    }

    // Calculate prorated cost if applicable
    let finalCost = cost;
    let proratedMsg = '';
    if (prorateInfo) {
      finalCost = cost * prorateInfo.prorateRatio;
      proratedMsg = `\n\n💰 PRORATED OFFER:\n${prorateInfo.daysRemaining} days remaining in billing period\nYou save ${prorateInfo.discount}% (GH₵${(cost - finalCost).toFixed(2)})!`;
    }

    // Paid plans: Initialize Paystack payment
    const confirmMsg = `Upgrade to ${plan}?${proratedMsg}\n\nCost: GH₵ ${finalCost.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} for ${billingPeriod === 'term' ? '1 term' : '3 terms (annual)'}\nBased on ${currentStudents} students`;
    if (!window.confirm(confirmMsg)) return;

    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };

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
      alert(err.response?.data?.message || 'Failed to initialize payment. Please try again.');
    }
  };

  if (!sub) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-slate-600">Loading subscription details...</p>
      </div>
    </div>
  );

  // Auto-detect current student enrollment
  const currentStudents = sub.current_enrollment || 0;
  
  // Calculate costs using Model A (Base Fee + Included Students + Overage)
  // Basic: ₵360 base/term + 30 included + ₵12/extra student
  const basicBaseFee = 360;
  const basicIncluded = 30;
  const basicOverage = Math.max(0, currentStudents - basicIncluded);
  const basicTermCost = basicBaseFee + (basicOverage * 12);
  const basicAnnualCost = basicTermCost * 3;
  
  // Premium: ₵450 base/term + 30 included + ₵27/extra student
  // Premium: ₵510 base/term + 30 included + ₵17/extra student
  const premiumBaseFee = 510;
  const premiumIncluded = 30;
  const premiumOverage = Math.max(0, currentStudents - premiumIncluded);
  const premiumTermCost = premiumBaseFee + (premiumOverage * 17);
  const premiumAnnualCost = premiumTermCost * 3;

  const plans = [
    {
      name: 'Free Tier',
      price: 0,
      termCost: 0,
      annualCost: 0,
      description: 'Perfect for small schools getting started',
      color: 'gray',
      features: [
        { name: 'Up to 50 students', included: true },
        { name: '1 class only', included: true },
        { name: 'View attendance & feeding', included: true, note: '(Read-only)' },
        { name: 'Basic report generation', included: true },
        { name: 'Grade viewing', included: true },
        { name: 'Grade entry & editing', included: false },
        { name: 'Payment tracking', included: false },
        { name: 'AI insights', included: false },
      ],
    },
    {
      name: 'Basic',
      price: 12,
      baseFee: basicBaseFee,
      included: basicIncluded,
      overage: basicOverage,
      termCost: basicTermCost,
      annualCost: basicAnnualCost,
      description: 'Full school operations for growing institutions',
      color: 'blue',
      popular: true,
      features: [
        { name: 'Up to 200 students', included: true },
        { name: '5 classes', included: true },
        { name: 'Full attendance & feeding management', included: true },
        { name: 'Grade entry & editing', included: true },
        { name: 'Payment tracking & reconciliation', included: true },
        { name: 'Lesson notes creation', included: true },
        { name: 'Bulk operations', included: true },
        { name: '5 report templates', included: true },
        { name: 'Basic AI feedback', included: true },
      ],
    },
    {
      name: 'Premium',
      price: 27,
      baseFee: premiumBaseFee,
      included: premiumIncluded,
      overage: premiumOverage,
      termCost: premiumTermCost,
      annualCost: premiumAnnualCost,
      description: 'Unlimited access with AI-powered insights',
      color: 'purple',
      recommended: true,
      features: [
        { name: '∞ Unlimited students', included: true },
        { name: '∞ Unlimited classes', included: true },
        { name: 'Everything in Basic', included: true },
        { name: 'AI-powered grade narratives', included: true },
        { name: 'Advanced analytics dashboard', included: true },
        { name: 'Custom HTML templates', included: true },
        { name: 'Priority support', included: true },
        { name: 'Full AI analysis & scoring', included: true },
      ],
    },
  ];

  return (
    <div className="bg-linear-to-br from-slate-50 to-blue-50 min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-black text-slate-800 mb-2">Subscription & Billing</h1>
          <p className="text-slate-600">
            💡 <strong>Termly Billing:</strong> Schools operate on 3 terms per academic year. We bill per student per term to align with your cash flow.
          </p>
        </div>

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
                {plan.recommended && !isCurrentPlan && (
                  <div className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-linear-to-r from-purple-600 to-pink-600 text-white text-xs font-bold px-4 py-1 rounded-full shadow-lg">
                    RECOMMENDED
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
                        {currentStudents} students × GH₵ {plan.price} × {billingPeriod === 'term' ? '1 term' : '3 terms'}
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

                {/* Proration Banner - Only show if applicable */}
                {!isCurrentPlan && prorateInfo && plan.name !== 'Free Tier' && (
                  <div className="mb-6 bg-amber-50 border border-amber-300 rounded-lg p-3">
                    <div className="flex items-start gap-2">
                      <Tag className="text-amber-600 shrink-0 mt-0.5" size={16} />
                      <div className="text-sm">
                        <p className="font-bold text-amber-900">🎁 Mid-Term Discount!</p>
                        <p className="text-amber-800 text-xs mt-1">
                          {prorateInfo.daysRemaining} days remaining
                        </p>
                        <p className="text-amber-900 font-bold text-xs mt-1">
                          Save {prorateInfo.discount}% - Pay only GH₵ {(displayCost * prorateInfo.prorateRatio).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
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
                    {plan.name === 'Free Tier' ? 'Switch to Free' : `Pay GH₵ ${(displayCost * (prorateInfo ? prorateInfo.prorateRatio : 1)).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`}
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
                <strong>Students × Price/Student × Terms</strong>
              </p>
              <p className="text-xs">
                Example: <strong>50 students × GH₵12 × 1 term = GH₵600</strong>
              </p>
            </div>
            <div className="bg-white rounded-lg p-3 border border-blue-100">
              <p className="font-bold text-blue-900 mb-2">⏱️ Prorated (Mid-Term)</p>
              <p className="font-mono text-xs text-slate-700 mb-2">
                <strong>Full Cost × (Days Remaining / 120)</strong>
              </p>
              <p className="text-xs">
                Example: Upgrade on day 90? <strong>Pay only 25% = GH₵150</strong>
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
                <p className="font-bold text-amber-600 mt-2">• <strong>🎁 Proration Available:</strong> {prorateInfo.daysRemaining} days remaining ({prorateInfo.discount}% discount)</p>
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
                <span>Example: 100 students on Basic = <strong>GH₵ 1,200/term</strong></span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
