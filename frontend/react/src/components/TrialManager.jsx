import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Zap, Calendar, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

const getTrialFeatureList = (plan) => {
  if (plan === 'Basic') {
    return [
      'Full attendance, feeding, and grade operations',
      'Lesson notes, finance, inventory, and reporting workflows',
      'Up to 200 students with school operations unlocked',
      'Standard support during the trial period',
    ];
  }

  return [
    'Unlimited students and classes',
    'AI Pack and Automation Pack features',
    'Advanced analytics and custom templates',
    'Priority support during the trial period',
  ];
};

export default function TrialManager({ onTrialChange }) {
  const [trialStatus, setTrialStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [selectedTrialPlan, setSelectedTrialPlan] = useState('Premium');

  const fetchTrialStatus = async () => {
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.get('/api/school/subscription/trial/status', { headers });
      setTrialStatus(res.data);
      const firstOption = res.data?.available_trial_plans?.[0]?.plan;
      setSelectedTrialPlan(firstOption || 'Premium');
    } catch (err) {
      console.error("Failed to fetch trial status:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleActivateTrial = async () => {
    const chosenPlan = selectedTrialPlan || trialStatus?.available_trial_plans?.[0]?.plan || 'Premium';
    const chosenPlanLabel = trialStatus?.available_trial_plans?.find((plan) => plan.plan === chosenPlan)?.display_name || chosenPlan;
    const benefitLines = getTrialFeatureList(chosenPlan).map((line) => `• ${line}`).join('\n');
    if (!window.confirm(`Activate a 30-day ${chosenPlanLabel} trial?\n\nYou will gain access to:\n${benefitLines}\n\nThis is a one-time offer and lasts 30 days from activation.`)) {
      return;
    }

    setProcessing(true);
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      await axios.post('/api/school/subscription/trial/activate', { trial_plan: chosenPlan }, { headers });
      
      // Update localStorage
      localStorage.setItem('subscription_plan', chosenPlan);
      
      const activationNotice = chosenPlan === 'Premium'
        ? 'You now have full access to School OS Plus and all trial add-on features.'
        : 'You now have full access to School OS for the next 30 days.';
      alert(`🎉 ${chosenPlanLabel} trial activated successfully!\n\n${activationNotice}`);
      await fetchTrialStatus();
      if (onTrialChange) {
        await onTrialChange();
      }
      window.location.reload(); // Refresh to update all components
    } catch (err) {
      console.error("Failed to activate trial:", err);
      alert(err.response?.data?.message || err.response?.data?.error || '❌ Failed to activate trial. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  const handleEndTrial = async () => {
    if (!window.confirm('End School OS Plus trial early?\n\nYou will immediately lose access to School OS Plus and trial add-on features, then revert to your base plan.\n\nThis action cannot be undone.')) {
      return;
    }

    setProcessing(true);
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.post('/api/school/subscription/trial/end', {}, { headers });
      
      // Update localStorage with the base plan returned
      if (res.data.base_plan) {
        localStorage.setItem('subscription_plan', res.data.base_plan);
      }
      
      alert(`Trial ended. Reverted to ${res.data.base_plan || 'base'} plan.`);
      await fetchTrialStatus();
      if (onTrialChange) {
        await onTrialChange();
      }
      window.location.reload();
    } catch (err) {
      console.error("Failed to end trial:", err);
      alert(err.response?.data?.message || err.response?.data?.error || '❌ Failed to end trial. Please try again.');
    } finally {
      setProcessing(false);
    }
  };

  useEffect(() => {
    fetchTrialStatus();
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

  if (!trialStatus) {
    return null;
  }

  const daysRemaining = trialStatus.is_active && trialStatus.end_date
    ? Math.max(0, Math.floor((new Date(trialStatus.end_date) - new Date()) / (1000 * 60 * 60 * 24)))
    : 0;

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="text-purple-600" size={24} />
        <h3 className="text-lg font-bold text-slate-800">Subscription Trial Management</h3>
      </div>

      {trialStatus.is_active ? (
        // Active Trial View
        <div className="space-y-4">
          <div className="bg-linear-to-br from-purple-50 to-indigo-50 border-2 border-purple-300 p-4 rounded-xl">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <CheckCircle className="text-green-600" size={20} />
                <span className="font-bold text-purple-900">Trial Active</span>
              </div>
              <span className="px-3 py-1 bg-purple-600 text-white text-xs font-bold rounded-full">
                {trialStatus.plan_display_name || trialStatus.plan || 'TRIAL'}
              </span>
            </div>
            
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-600">Trial access ends:</span>
                <span className="font-semibold text-slate-800">
                  {new Date(trialStatus.end_date).toLocaleDateString('en-GB', { 
                    day: 'numeric', month: 'short', year: 'numeric' 
                  })}
                </span>
              </div>
              {(trialStatus.term_name || trialStatus.academic_year) && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Proration term:</span>
                  <span className="font-semibold text-slate-800">
                    {[trialStatus.term_name, trialStatus.academic_year].filter(Boolean).join(' • ')}
                  </span>
                </div>
              )}
              {trialStatus.reference_source && (
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Calendar source:</span>
                  <span className="font-semibold text-slate-800">
                    {trialStatus.reference_source === 'school_active_term' ? 'School active term' : 'EduPulse national basic-school calendar'}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between border-t border-purple-200 pt-2 mt-2">
                <span className="text-slate-700 font-semibold">Days Remaining:</span>
                <span className="text-2xl font-black text-purple-600">
                  {daysRemaining}
                </span>
              </div>
            </div>

            {daysRemaining <= 3 && (
              <div className="mt-3 bg-amber-100 border border-amber-300 p-3 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertCircle className="text-amber-600 shrink-0 mt-0.5" size={16} />
                  <div className="text-xs">
                    <p className="font-bold text-amber-900">⏰ Trial Expiring Soon!</p>
                    <p className="text-amber-800 mt-1">
                      Your trial ends in {daysRemaining} day{daysRemaining !== 1 ? 's' : ''}. 
                      Upgrade now to keep School OS Plus access. Your first paid charge after trial is based on the remaining days in the current term.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="bg-slate-50 p-4 rounded-xl">
            <p className="text-sm font-bold text-slate-800 mb-2">Trial Features You're Enjoying:</p>
            <ul className="space-y-1.5 text-sm text-slate-600">
              {getTrialFeatureList(trialStatus.plan).map((feature) => (
                <li key={feature} className="flex items-center gap-2">
                  <CheckCircle className="text-green-500" size={14} />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </div>

          <button
            onClick={handleEndTrial}
            disabled={processing}
            className="w-full py-2.5 bg-slate-600 hover:bg-slate-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-semibold transition-colors"
          >
            {processing ? 'Processing...' : 'End Trial Early'}
          </button>
        </div>
      ) : trialStatus.has_used_trial ? (
        // Trial Already Used
        <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl">
          <div className="flex items-start gap-3 mb-3">
            <XCircle className="text-slate-400 shrink-0 mt-0.5" size={20} />
            <div>
              <p className="font-bold text-slate-700 mb-1">Trial Previously Used</p>
              <p className="text-sm text-slate-600">
                You've already used your one-time subscription trial. 
                Upgrade to a paid plan and any needed add-ons to continue enjoying those features.
              </p>
            </div>
          </div>
          {trialStatus.trial_ended_at && (
            <p className="text-xs text-slate-500">
              Trial ended: {new Date(trialStatus.trial_ended_at).toLocaleDateString('en-GB', { 
                day: 'numeric', month: 'short', year: 'numeric' 
              })}
            </p>
          )}
        </div>
      ) : (
        // Trial Available
        <div className="space-y-4">
          <div className="bg-linear-to-br from-purple-50 to-indigo-50 border-2 border-purple-200 p-4 rounded-xl">
            <div className="flex items-start gap-3">
              <Zap className="text-purple-600 shrink-0" size={24} />
              <div>
                <p className="font-bold text-purple-900 mb-2">🎁 Activate Your Free Subscription Trial!</p>
                <p className="text-sm text-slate-700 mb-3">
                  Choose the next paid plan you want to test for 30 days at no cost. No credit card is required to start the trial.
                </p>
                <p className="text-xs text-slate-500 mb-3">
                  After the trial ends, your first paid subscription charge is prorated to the remaining days in the current school term.
                </p>
                <div className="mb-3 grid gap-3 md:grid-cols-2">
                  {(trialStatus.available_trial_plans || []).map((plan) => (
                    <button
                      key={plan.plan}
                      type="button"
                      onClick={() => setSelectedTrialPlan(plan.plan)}
                      className={`rounded-xl border p-3 text-left transition-all ${selectedTrialPlan === plan.plan ? 'border-purple-500 bg-white shadow-sm' : 'border-purple-200 bg-purple-50/60 hover:bg-white'}`}
                    >
                      <p className="font-bold text-slate-800">{plan.display_name}</p>
                      <p className="mt-1 text-xs text-slate-600">{plan.description}</p>
                      <p className="mt-2 text-xs font-semibold text-purple-700">
                        {plan.includes_addons ? 'Includes trial access to AI Pack and Automation Pack' : 'Core paid-plan features only during trial'}
                      </p>
                    </button>
                  ))}
                </div>
                <ul className="space-y-1.5 text-sm text-slate-600 mb-3">
                  {getTrialFeatureList(selectedTrialPlan).map((feature) => (
                    <li key={feature} className="flex items-center gap-2">
                      <CheckCircle className="text-green-500 shrink-0" size={14} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
                <p className="text-xs text-purple-700 font-semibold">
                  ⏰ This is a one-time offer. Trial lasts 30 days from activation.
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={handleActivateTrial}
            disabled={processing}
            className="w-full py-3 bg-linear-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 disabled:from-slate-300 disabled:to-slate-400 text-white rounded-xl text-base font-bold transition-all shadow-lg hover:shadow-xl"
          >
            {processing ? (
              <div className="flex items-center justify-center gap-2">
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                Activating...
              </div>
            ) : (
              <>
                <Zap className="inline-block mr-2" size={18} />
                Activate 30-Day {(trialStatus.available_trial_plans || []).find((plan) => plan.plan === selectedTrialPlan)?.display_name || 'Subscription'} Trial
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
