import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import useSubscription, { PLAN_FEATURES } from '../useSubscription';

vi.mock('axios');

describe('subscription entitlements', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('fails closed while loading and for unknown or malformed features', async () => {
    axios.get.mockResolvedValue({ data: { plan: 'Premium', features: { malformed: 'enabled', payment_tracking: false } } });
    const { result } = renderHook(() => useSubscription());
    expect(result.current.hasFeature('payment_tracking')).toBe(false);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasFeature('unknown')).toBe(false);
    expect(result.current.hasFeature('malformed')).toBe(false);
    expect(result.current.hasFeature('payment_tracking')).toBe(false);
  });

  it.each(['Free Tier', 'Basic', 'Premium'])('uses resolved features for %s', async (plan) => {
    axios.get.mockResolvedValue({ data: { effective_plan: plan, features: PLAN_FEATURES[plan].features } });
    const { result } = renderHook(() => useSubscription());
    await waitFor(() => expect(result.current.loading).toBe(false));
    for (const feature of ['payment_tracking', 'bulk_operations']) {
      expect(result.current.hasFeature(feature)).toBe(plan !== 'Free Tier');
    }
    expect(result.current.hasFeature('advanced_analytics')).toBe(plan === 'Premium');
    expect(result.current.hasFeature('report_generation')).toBe(plan !== 'Free Tier');
    expect(result.current.hasFeature('attendance')).toBe(true);
    expect(result.current.canAccess('attendance')).toBe(plan !== 'Free Tier');
    expect(axios.get).toHaveBeenCalledWith('/api/school/subscription/effective-plan', expect.any(Object));
  });

  it('reuses the confirmed plan on remount without a locked loading flash', async () => {
    axios.get.mockResolvedValue({ data: { effective_plan: 'Premium', features: { payment_tracking: true } } });
    const first = renderHook(() => useSubscription());
    await waitFor(() => expect(first.result.current.hasFeature('payment_tracking')).toBe(true));
    first.unmount();
    const second = renderHook(() => useSubscription());
    expect(second.result.current.loading).toBe(false);
    expect(second.result.current.hasFeature('payment_tracking')).toBe(true);
    expect(axios.get).toHaveBeenCalledTimes(1);
  });

  it('shares one request across simultaneously mounted consumers', async () => {
    axios.get.mockResolvedValue({ data: { effective_plan: 'Basic', features: { bulk_operations: true } } });
    const hooks = [renderHook(() => useSubscription()), renderHook(() => useSubscription())];
    for (const { result } of hooks) {
      await waitFor(() => expect(result.current.hasFeature('bulk_operations')).toBe(true));
    }
    expect(axios.get).toHaveBeenCalledTimes(1);
  });

  it('fails closed after a subscription request fails', async () => {
    axios.get.mockRejectedValue(new Error('unavailable'));
    const { result } = renderHook(() => useSubscription());
    for (const feature of ['attendance', 'report_generation', 'unknown']) {
      expect(result.current.hasFeature(feature)).toBe(false);
      expect(result.current.getFeatureLevel(feature)).toBe(false);
      expect(result.current.canAccess(feature, 'view_only')).toBe(false);
    }
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasFeature('payment_tracking')).toBe(false);
    expect(result.current.hasFeature('bulk_operations')).toBe(false);
    for (const feature of ['attendance', 'report_generation', 'unknown']) {
      expect(result.current.hasFeature(feature)).toBe(false);
      expect(result.current.getFeatureLevel(feature)).toBe(false);
      expect(result.current.canAccess(feature, 'view_only')).toBe(false);
    }
  });

  it('does not infer permissions from a plan without resolved features', async () => {
    axios.get.mockResolvedValue({ data: { effective_plan: 'Premium' } });
    const { result } = renderHook(() => useSubscription());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.hasFeature('report_generation')).toBe(false);
    expect(result.current.canAccess('attendance', 'view_only')).toBe(false);
  });
});