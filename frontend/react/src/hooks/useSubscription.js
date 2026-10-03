/**
 * useSubscription Hook
 * Provides subscription and feature access checking for React components
 * Usage: const { plan, hasFeature, canAccess } = useSubscription();
 */

import { useState, useEffect } from 'react';
import axios from 'axios';

// Feature matrix (mirrors backend)
export const PLAN_FEATURES = {
  'Free Tier': {
    maxClasses: 1,
    maxStudents: 50,
    features: {
      attendance: 'view_only',
      feeding: 'view_only',
      payment_tracking: false,
      bulk_operations: false,
      advanced_analytics: false,
      lesson_notes: false,
      grade_entry: false,
      report_generation: true,
      ai_analysis: false,
      ai_registrar: false,
      student_rescue_agent: false,
      webhook_payment_automation: false,
      ai_bursar_addon_available: false,
      communications_automation_addon_available: false,
      html_templates: false,
    },
  },
  'Basic': {
    maxClasses: 5,
    maxStudents: 200,
    features: {
      attendance: 'full_access',
      feeding: 'full_access',
      payment_tracking: true,
      bulk_operations: true,
      advanced_analytics: false,
      lesson_notes: true,
      grade_entry: true,
      report_generation: true,
      ai_analysis: false,
      ai_registrar: true,
      student_rescue_agent: false,
      webhook_payment_automation: false,
      ai_bursar_addon_available: true,
      communications_automation_addon_available: true,
      html_templates: false,
    },
  },
  'Premium': {
    maxClasses: Infinity,
    maxStudents: Infinity,
    features: {
      attendance: 'full_access',
      feeding: 'full_access',
      payment_tracking: true,
      bulk_operations: true,
      advanced_analytics: true,
      lesson_notes: true,
      grade_entry: true,
      report_generation: true,
      ai_analysis: false,
      ai_narratives: false,
      ai_registrar: true,
      student_rescue_agent: false,
      webhook_payment_automation: false,
      ai_bursar_addon_available: true,
      communications_automation_addon_available: true,
      html_templates: true,
    },
  },
};

export function useSubscription() {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const storedToken = localStorage.getItem('token') || localStorage.getItem('access_token');
        const headers = {
          'X-School-ID': localStorage.getItem('school_id'),
          'Authorization': `Bearer ${storedToken}`,
        };

        const response = await axios.get('/api/school/subscription/effective-plan', { headers });
        setSubscription({ ...response.data, plan: response.data.effective_plan || response.data.plan });
        setError(null);
      } catch (err) {
        console.error('Failed to fetch subscription:', err);
        setError(err.response?.data?.message || 'Failed to fetch subscription');
        setSubscription(null);
      } finally {
        setLoading(false);
      }
    };

    if (localStorage.getItem('token') || localStorage.getItem('access_token')) {
      fetchSubscription();
    } else {
      setLoading(false);
    }
  }, []);

  const hasAddon = (addonName) => !loading && !error && Boolean(subscription?.active_addons?.[addonName]);

  /**
   * Check if a feature is available at any level
   * @param {string} featureName - Name of the feature to check
   * @returns {boolean} - True if feature is available
   */
  const hasFeature = (featureName) => {
    if (loading || error || !subscription) return false;
    const features = subscription.features || {};
    const featureValue = features[featureName];
    return featureValue === true || ['view_only', 'basic', 'full_access', 'full'].includes(featureValue);
  };

  /**
   * Get the access level for a feature
   * @param {string} featureName - Name of the feature
   * @returns {string|boolean} - Access level ('view_only', 'basic', 'full_access', 'full', true, or false)
   */
  const getFeatureLevel = (featureName) => {
    if (loading || error || !subscription) return false;
    const features = subscription.features || {};
    return features[featureName] ?? false;
  };

  /**
   * Check if user can access a feature at a specific level
   * @param {string} featureName - Name of the feature
   * @param {string} minLevel - Minimum access level ('view_only', 'basic', 'full_access')
   * @returns {boolean} - True if user has at least minLevel access
   */
  const canAccess = (featureName, minLevel = 'full_access') => {
    const currentLevel = getFeatureLevel(featureName);

    if (!currentLevel) return false;

    const levels = {
      'view_only': 1,
      'basic': 2,
      'full_access': 3,
      'full': 3,
      true: 3,
    };

    const currentValue = levels[currentLevel] || 0;
    const requiredValue = levels[minLevel] || 3;

    return currentValue >= requiredValue;
  };

  /**
   * Check if plan has enough quota for a resource
   * @param {string} resource - 'students' or 'classes'
   * @param {number} currentCount - Current number of resources
   * @returns {boolean} - True if within quota
   */
  const withinQuota = (resource, currentCount = 0) => {
    if (!subscription) return false;
    const planData = PLAN_FEATURES[subscription.plan];
    if (resource === 'students') {
      return currentCount < planData.maxStudents;
    } else if (resource === 'classes') {
      return currentCount < planData.maxClasses;
    }
    return false;
  };

  /**
   * Check if template is accessible in current plan
   * @param {string} templateId - ID of the template
   * @returns {boolean} - True if accessible
   */
  const canAccessTemplate = (templateId) => {
    if (loading || error || !subscription) return false;
    const templates = subscription.report_templates || [];
    return templates.includes(templateId);
  };

  return {
    subscription,
    loading,
    error,
    plan: subscription?.plan || 'Free Tier',
    hasFeature,
    getFeatureLevel,
    canAccess,
    withinQuota,
    canAccessTemplate,
    hasAddon,
    activeAddons: subscription?.active_addons || {},
    planDisplayName: subscription?.plan_display_name || subscription?.plan || 'Free Tier',
    isFreeTier: subscription?.plan === 'Free Tier',
    isBasic: subscription?.plan === 'Basic',
    isPremium: subscription?.plan === 'Premium',
  };
}

export default useSubscription;
