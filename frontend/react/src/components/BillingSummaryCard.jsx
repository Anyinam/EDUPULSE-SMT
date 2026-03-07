import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { TrendingUp, AlertTriangle, CheckCircle, DollarSign } from 'lucide-react';

/**
 * Compact billing summary card for dashboard overview
 * Shows: meter status, alert level, and current term cost
 */
export default function BillingSummaryCard() {
  const [billingData, setBillingData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
    fetchBillingVisibility();
  }, []);

  if (loading) {
    return (
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div className="animate-pulse">
          <div className="h-3 bg-slate-200 rounded w-1/2 mb-3"></div>
          <div className="h-8 bg-slate-200 rounded w-3/4"></div>
        </div>
      </div>
    );
  }

  if (!billingData) return null;

  const { meter, cost_breakdown } = billingData;
  const alert = meter?.alert || {};
  const alertLevel = alert.level || 'ok';
  const usagePercent = meter?.usage_percent || 0;

  // Alert styling
  const alertConfig = {
    ok: { 
      icon: CheckCircle, 
      color: 'text-green-600', 
      bg: 'bg-green-50', 
      border: 'border-green-200',
      barColor: 'bg-green-500'
    },
    warning: { 
      icon: AlertTriangle, 
      color: 'text-amber-600', 
      bg: 'bg-amber-50', 
      border: 'border-amber-300',
      barColor: 'bg-amber-500'
    },
    critical: { 
      icon: AlertTriangle, 
      color: 'text-red-600', 
      bg: 'bg-red-50', 
      border: 'border-red-300',
      barColor: 'bg-red-500'
    }
  };

  const config = alertConfig[alertLevel] || alertConfig.ok;
  const AlertIcon = config.icon;

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="text-blue-600" size={20} />
          <h3 className="font-bold text-slate-800 text-sm">Billing Summary</h3>
        </div>
        <div className={`${config.bg} ${config.border} border px-2 py-1 rounded-full flex items-center gap-1.5`}>
          <AlertIcon className={config.color} size={14} />
          <span className={`${config.color} text-xs font-bold uppercase`}>
            {alertLevel}
          </span>
        </div>
      </div>

      {/* Student Meter */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-black text-slate-800">
            {meter?.current_count || 0}
          </span>
          <span className="text-lg text-slate-400">/</span>
          <span className="text-xl font-bold text-slate-500">
            {meter?.included_students || 0}
          </span>
        </div>
        
        {/* Mini Progress Bar */}
        <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden mb-1">
          <div 
            className={`${config.barColor} h-full transition-all duration-500 ease-out`}
            style={{ width: `${Math.min(usagePercent, 100)}%` }}
          />
        </div>
        
        <p className="text-xs text-slate-500">{usagePercent.toFixed(0)}% capacity</p>
      </div>

      {/* Alert Message (compact) */}
      {alertLevel !== 'ok' && (
        <div className={`${config.bg} ${config.border} border p-3 rounded-lg mb-4`}>
          <p className={`${config.color} font-bold text-xs`}>
            {alert.title}
          </p>
        </div>
      )}

      {/* Cost Summary */}
      <div className="border-t border-slate-200 pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign className="text-green-600" size={16} />
            <span className="text-sm font-semibold text-slate-700">This Term</span>
          </div>
          <span className="text-xl font-black text-blue-600">
            GH₵ {(cost_breakdown?.total_due || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}
          </span>
        </div>
        {(cost_breakdown?.overage_students || 0) > 0 && (
          <p className="text-xs text-amber-600 mt-1">
            +{cost_breakdown.overage_students} overage student{cost_breakdown.overage_students !== 1 ? 's' : ''}
          </p>
        )}
      </div>
    </div>
  );
}
