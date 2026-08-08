import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

const BRANDING_REFRESH_TTL_MS = 30_000;
const BRANDING_REFRESH_AT_KEY = 'branding_refreshed_at';

const readStoredBrandingForCurrentSchool = () => {
  try {
    const schoolId = localStorage.getItem('school_id') || '';
    const storedSchoolId = localStorage.getItem('branding_school_id') || '';
    const raw = JSON.parse(localStorage.getItem('branding')) || {};
    if (schoolId && storedSchoolId && storedSchoolId !== schoolId) {
      return {};
    }
    return raw;
  } catch (err) {
    return {};
  }
};

const normalizeBranding = (data, fallback) => ({
  name: data?.school_name ?? fallback.name ?? '',
  school_name: data?.school_name ?? fallback.school_name ?? fallback.name ?? '',
  logo: data?.logo_url ?? fallback.logo ?? fallback.logo_url ?? '',
  logo_url: data?.logo_url ?? fallback.logo_url ?? fallback.logo ?? '',
  theme_color: data?.theme_color ?? fallback.theme_color ?? '',
  primary_color: data?.theme_color ?? fallback.primary_color ?? fallback.theme_color ?? '',
  motto: data?.motto ?? fallback.motto ?? fallback.school_motto ?? '',
  school_motto: data?.motto ?? fallback.school_motto ?? fallback.motto ?? '',
  email: data?.school_email ?? fallback.email ?? fallback.school_email ?? '',
  school_email: data?.school_email ?? fallback.school_email ?? fallback.email ?? '',
  phone: data?.school_phone ?? fallback.phone ?? fallback.school_phone ?? '',
  school_phone: data?.school_phone ?? fallback.school_phone ?? fallback.phone ?? '',
  address: data?.school_address ?? fallback.address ?? fallback.school_address ?? '',
  school_address: data?.school_address ?? fallback.school_address ?? fallback.address ?? '',
  website: data?.school_website ?? fallback.website ?? fallback.school_website ?? '',
  school_website: data?.school_website ?? fallback.school_website ?? fallback.website ?? '',
  verification_status: data?.verification_status ?? fallback.verification_status ?? '',
  is_verified: data?.is_verified ?? fallback.is_verified ?? false,
  bank_name: data?.bank_name ?? fallback.bank_name ?? '',
  bank_account: data?.bank_account ?? fallback.bank_account ?? '',
  bank_account_name: data?.bank_account_name ?? fallback.bank_account_name ?? '',
  bank_branch: data?.bank_branch ?? fallback.bank_branch ?? '',
  country_code: data?.country_code ?? fallback.country_code ?? 'GH'
});

export const useBranding = ({ refreshOnMount = false } = {}) => {
  const [branding, setBranding] = useState(() => readStoredBrandingForCurrentSchool());

  const refreshBranding = useCallback(async () => {
    const token = localStorage.getItem('token');
    const schoolId = localStorage.getItem('school_id');
    if (!token || !schoolId) return;

    const lastRefreshedAt = Number(localStorage.getItem(BRANDING_REFRESH_AT_KEY) || 0);
    const cachedBranding = readStoredBrandingForCurrentSchool();
    if (
      cachedBranding?.school_name &&
      lastRefreshedAt > 0 &&
      Date.now() - lastRefreshedAt < BRANDING_REFRESH_TTL_MS
    ) {
      return;
    }

    try {
      const res = await axios.get('/api/school/branding', {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-School-ID': schoolId
        }
      });
      const nextBranding = normalizeBranding(res.data, cachedBranding);
      localStorage.setItem('branding', JSON.stringify(nextBranding));
      localStorage.setItem('branding_school_id', schoolId);
      localStorage.setItem(BRANDING_REFRESH_AT_KEY, String(Date.now()));
      if (nextBranding.theme_color) {
        document.documentElement.style.setProperty('--school-primary', nextBranding.theme_color);
      }
      setBranding(nextBranding);
      window.dispatchEvent(new Event('branding-updated'));
    } catch (err) {
      // Silent fail to avoid breaking UI when branding endpoint is unavailable.
    }
  }, []);

  useEffect(() => {
    if (refreshOnMount) {
      refreshBranding();
    }
  }, [refreshOnMount, refreshBranding]);

  useEffect(() => {
    const handleBrandingUpdated = () => {
      setBranding(readStoredBrandingForCurrentSchool());
    };

    window.addEventListener('branding-updated', handleBrandingUpdated);
    return () => window.removeEventListener('branding-updated', handleBrandingUpdated);
  }, []);

  return { branding, refreshBranding };
};

export default useBranding;
