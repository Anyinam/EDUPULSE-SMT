import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

export default function useEffectiveSubscriptionPlan() {
  const fallbackPlan = localStorage.getItem('subscription_plan') || 'Free Tier';
  const [plan, setPlan] = useState(fallbackPlan);
  const [loading, setLoading] = useState(true);
  const [trial, setTrial] = useState(null);
  const [planDisplayName, setPlanDisplayName] = useState(fallbackPlan);
  const [basePlan, setBasePlan] = useState(fallbackPlan);
  const [basePlanDisplayName, setBasePlanDisplayName] = useState(fallbackPlan);

  const headers = useMemo(() => ({
    Authorization: `Bearer ${localStorage.getItem('token')}`,
    'X-School-ID': localStorage.getItem('school_id'),
  }), []);

  useEffect(() => {
    let cancelled = false;

    const fetchEffectivePlan = async () => {
      try {
        const response = await axios.get('/api/school/subscription/effective-plan', { headers });
        if (cancelled) {
          return;
        }
        const effectivePlan = response.data?.effective_plan || response.data?.plan || fallbackPlan;
        setPlan(effectivePlan);
        setTrial(response.data?.trial || null);
        setPlanDisplayName(response.data?.plan_display_name || effectivePlan);
        setBasePlan(response.data?.base_plan || effectivePlan);
        setBasePlanDisplayName(response.data?.base_plan_display_name || response.data?.base_plan || effectivePlan);
        localStorage.setItem('subscription_plan', effectivePlan);
      } catch (error) {
        if (!cancelled) {
          setPlan(fallbackPlan);
          setPlanDisplayName(fallbackPlan);
          setBasePlan(fallbackPlan);
          setBasePlanDisplayName(fallbackPlan);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchEffectivePlan();

    return () => {
      cancelled = true;
    };
  }, [fallbackPlan, headers]);

  return {
    plan,
    planDisplayName,
    basePlan,
    basePlanDisplayName,
    isPremium: plan === 'Premium',
    loading,
    trial,
  };
}