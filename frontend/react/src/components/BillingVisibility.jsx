import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { AlertTriangle, TrendingUp, Calendar, DollarSign, Zap, CheckCircle, XCircle, Mail } from 'lucide-react';

export default function BillingVisibility() {
  const [billingData, setBillingData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [sendingReport, setSendingReport] = useState(false);

  const fetchBillingVisibility = async () => {
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      const res = await axios.get('/api/school/subscription/billing-visibility', { headers });
      setBillingData(res.data);
    } catch (err) {
      console.error("Failed to fetch billing visibility:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncMeter = async () => {
    setSyncing(true);
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      await axios.post('/api/school/subscription/meter/sync', {}, { headers });
      // Refresh data after sync
      await fetchBillingVisibility();
      alert('✅ Student meter synced successfully!');
    } catch (err) {
      console.error("Failed to sync meter:", err);
      alert('❌ Failed to sync meter. Please try again.');
    } finally {
      setSyncing(false);
    }
  };

  const handleSendUsageReport = async () => {
    if (!window.confirm('📧 Send monthly usage report to your email?\n\nThis will include:\n• Value delivered this month\n• Student meter status\n• Billing preview\n• Next month forecast')) {
      return;
    }

    setSendingReport(true);
    try {
      const headers = { 
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-School-ID': localStorage.getItem('school_id') 
      };
      await axios.post('/api/school/subscription/usage-report/send', {}, { headers });
      alert('✅ Usage report sent successfully! Check your email inbox.');
    } catch (err) {
      console.error("Failed to send usage report:", err);
      alert('❌ Failed to send usage report. Please try again.');
    } finally {
      setSendingReport(false);
    }
  };

  useEffect(() => {
    fetchBillingVisibility();
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

  if (!billingData) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-2xl">
        <p className="text-yellow-800 text-sm">⚠️ Unable to load billing data</p>
      </div>
    );
  }

  const { meter, trial, cost_breakdown, pricing } = billingData;
  const alert = meter?.alert || {};
  const alertLevel = alert.level || 'ok';
  const usagePercent = meter?.usage_percent || 0;

  // Calculate days remaining for trial
  const trialDaysRemaining = trial?.is_active && trial?.end_date 
    ? Math.max(0, Math.floor((new Date(trial.end_date) - new Date()) / (1000 * 60 * 60 * 24)))
    : 0;

  // Alert banner colors
  const alertColors = {
    ok: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-800', icon: 'text-green-600' },
    warning: { bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-900', icon: 'text-amber-600' },
    critical: { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-900', icon: 'text-red-600' }
  };
  const currentAlertColor = alertColors[alertLevel] || alertColors.ok;

  // Progress bar color
  const progressBarColor = alertLevel === 'critical' ? 'bg-red-500' 
    : alertLevel === 'warning' ? 'bg-amber-500' 
    : 'bg-green-500';

  return (
    <div className="space-y-6">
      {/* Trial Status Banner (if active) */}
      {trial?.is_active && (
        <div className="bg-linear-to-r from-purple-500 to-indigo-600 p-6 rounded-2xl text-white shadow-lg">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Zap size={24} className="text-yellow-300" />
                <h3 className="text-xl font-bold">Premium Trial Active!</h3>
              </div>
              <p className="text-purple-100 mb-3">
                You're currently enjoying all Premium features at no cost.
              </p>
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <Calendar size={16} className="text-purple-200" />
                  <span className="font-semibold">{trialDaysRemaining} days remaining</span>
                </div>
                <div className="text-purple-200">
                  Expires: {new Date(trial.end_date).toLocaleDateString('en-GB', { 
                    day: 'numeric', month: 'short', year: 'numeric' 
                  })}
                </div>
              </div>
            </div>
            {trialDaysRemaining <= 3 && (
              <div className="bg-white/20 backdrop-blur-sm px-4 py-2 rounded-lg">
                <p className="text-sm font-bold">⏰ Expiring Soon!</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Student Meter Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-slate-800 mb-1">Active Student Meter</h3>
            <p className="text-sm text-slate-500">
              Real-time count of enrolled students
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSendUsageReport}
              disabled={sendingReport}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2"
            >
              {sendingReport ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                  Sending...
                </>
              ) : (
                <>
                  <Mail size={16} />
                  Email Report
                </>
              )}
            </button>
            <button
              onClick={handleSyncMeter}
              disabled={syncing}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2"
            >
              {syncing ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                  Syncing...
                </>
              ) : (
                <>
                  <TrendingUp size={16} />
                  Sync Now
                </>
              )}
            </button>
          </div>
        </div>

        {/* Usage Display */}
        <div className="mb-4">
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-4xl font-black text-slate-800">
              {meter?.current_count || 0}
            </span>
            <span className="text-xl text-slate-400">/</span>
            <span className="text-2xl font-bold text-slate-500">
              {meter?.plan_limit ? meter.plan_limit : '∞'}
            </span>
            <span className="text-sm text-slate-500 ml-2">
              {meter?.plan_limit ? 'student limit' : 'unlimited students'}
            </span>
          </div>
          
          {/* Progress Bar - Only show if not unlimited */}
          {meter?.plan_limit && (
            <>
              <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden mb-2">
                <div 
                  className={`${progressBarColor} h-full transition-all duration-500 ease-out rounded-full`}
                  style={{ width: `${Math.min(usagePercent, 100)}%` }}
                />
              </div>
              
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600 font-medium">{usagePercent.toFixed(1)}% capacity used</span>
                {meter?.last_synced && (
                  <span className="text-slate-400 text-xs">
                    Last synced: {new Date(meter.last_synced).toLocaleTimeString('en-GB', { 
                      hour: '2-digit', minute: '2-digit' 
                    })}
                  </span>
                )}
              </div>
            </>
          )}
          
          {!meter?.plan_limit && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600 font-medium">Unlimited capacity - grow without limits</span>
              {meter?.last_synced && (
                <span className="text-slate-400 text-xs">
                  Last synced: {new Date(meter.last_synced).toLocaleTimeString('en-GB', { 
                    hour: '2-digit', minute: '2-digit' 
                  })}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Alert Banner */}
        <div className={`${currentAlertColor.bg} ${currentAlertColor.border} border-2 p-4 rounded-lg`}>
          <div className="flex items-start gap-3">
            {alertLevel === 'critical' ? (
              <XCircle className={currentAlertColor.icon} size={24} />
            ) : alertLevel === 'warning' ? (
              <AlertTriangle className={currentAlertColor.icon} size={24} />
            ) : (
              <CheckCircle className={currentAlertColor.icon} size={24} />
            )}
            <div className="flex-1">
              <p className={`${currentAlertColor.text} font-bold text-sm mb-1`}>
                {alert.title || 'All systems normal'}
              </p>
              <p className={`${currentAlertColor.text} text-sm`}>
                {alert.message || 'You have capacity for more students.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Cost Breakdown Card */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <DollarSign className="text-green-600" size={20} />
          <h3 className="text-lg font-bold text-slate-800">Current Term Billing</h3>
        </div>

        <div className="space-y-3">
          {/* Base Fee */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <div>
              <p className="text-sm font-semibold text-slate-700">Base Fee</p>
              <p className="text-xs text-slate-500">{billingData.plan} plan</p>
            </div>
            <p className="text-lg font-bold text-slate-800">
              GH₵ {(cost_breakdown?.base_fee || 0).toFixed(2)}
            </p>
          </div>

          {/* Included Students */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <div>
              <p className="text-sm font-semibold text-slate-700">Included Students</p>
              <p className="text-xs text-slate-500">{meter?.included_students || 0} students at no extra charge</p>
            </div>
            <p className="text-lg font-bold text-green-600">Included</p>
          </div>

          {/* Overage */}
          {(cost_breakdown?.overage_students || 0) > 0 ? (
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div>
                <p className="text-sm font-semibold text-slate-700">Additional Students</p>
                <p className="text-xs text-slate-500">
                  {cost_breakdown.overage_students} × GH₵ {(pricing?.overage_rate || 0).toFixed(2)}/student
                </p>
              </div>
              <p className="text-lg font-bold text-amber-600">
                + GH₵ {(cost_breakdown?.overage_cost || 0).toFixed(2)}
              </p>
            </div>
          ) : (
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div>
                <p className="text-sm font-semibold text-slate-700">Additional Students</p>
                <p className="text-xs text-slate-500">No overage charges</p>
              </div>
              <p className="text-lg font-bold text-green-600">GH₵ 0.00</p>
            </div>
          )}

          {/* Total */}
          <div className="flex items-center justify-between pt-2">
            <div>
              <p className="text-base font-bold text-slate-800">Total This Term</p>
              <p className="text-xs text-slate-500">Billed at end of term</p>
            </div>
            <p className="text-2xl font-black text-blue-600">
              GH₵ {(cost_breakdown?.total_due || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
            </p>
          </div>
        </div>

        {/* Pricing Locked Message */}
        {pricing?.version && (
          <div className="mt-4 bg-blue-50 border border-blue-200 p-3 rounded-lg">
            <p className="text-xs text-blue-800">
              🔒 <strong>Grandfathered Pricing:</strong> Your rates are locked at version {pricing.version}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
