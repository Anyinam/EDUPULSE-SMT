/**
 * FeatureLock Component
 * Displays a lock/upgrade prompt when a feature is not available
 * Usage: <FeatureLock feature="lesson_notes" plan="Premium" />
 */

import React from 'react';
import useSubscription from '../hooks/useSubscription';

export function FeatureLock({ feature, requiredPlan = 'Premium', children }) {
  const { hasFeature, plan } = useSubscription();

  if (hasFeature(feature)) {
    return children;
  }

  const featureNames = {
    lesson_notes: 'Lesson Notes',
    grade_entry: 'Grade Entry',
    ai_analysis: 'AI Analysis',
    ai_narratives: 'AI-Generated Narratives',
    html_templates: 'Custom HTML Templates',
    advanced_analytics: 'Advanced Analytics',
    payment_tracking: 'Payment Tracking',
    attendance: 'Attendance Management',
    feeding: 'Feeding Records',
  };

  const planColors = {
    'Free Tier': 'text-slate-600',
    'Basic': 'text-blue-600',
    'Premium': 'text-purple-600',
  };

  return (
    <div className={`p-6 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-center ${planColors[requiredPlan]}`}>
      <div className="text-4xl mb-4">🔒</div>
      <h3 className="font-bold text-lg mb-2">{featureNames[feature] || feature} Locked</h3>
      <p className="text-sm text-slate-600 mb-4">
        This feature is available in <strong>{requiredPlan}</strong> plan.
        <br />
        You're currently on <strong>{plan}</strong>.
      </p>
      <button
        onClick={() => window.location.href = '/proprietor?tab=subscription'}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition-colors"
      >
        Upgrade Now
      </button>
    </div>
  );
}

export function FeatureAlert({ feature, children }) {
  const { hasFeature } = useSubscription();

  if (hasFeature(feature)) {
    return children;
  }

  return null;
}

/**
 * Conditional render based on subscription
 * Usage: <SubscriptionGuard requires="Premium"><YourComponent /></SubscriptionGuard>
 */
export function SubscriptionGuard({ requires = 'Basic', children, fallback = null }) {
  const { plan } = useSubscription();
  const tiers = { 'Free Tier': 0, 'Basic': 1, 'Premium': 2 };

  if ((tiers[plan] || 0) >= (tiers[requires] || 0)) {
    return children;
  }

  return fallback || (
    <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700">
      <p className="font-semibold">Plan Upgrade Required</p>
      <p className="text-sm">This feature requires {requires} plan or higher.</p>
    </div>
  );
}

export default FeatureLock;
