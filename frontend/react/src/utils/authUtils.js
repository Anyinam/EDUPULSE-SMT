/**
 * Secure authentication utilities for EduPulse Frontend
 * Implements secure token storage and session management
 */

const TOKEN_KEY = 'edupulse_token';
const LEGACY_TOKEN_KEY = 'token';
const SCHOOL_ID_KEY = 'school_id';
const USER_ROLE_KEY = 'role';
const BRANDING_KEY = 'branding';
const ASSIGNED_CLASS_KEY = 'assigned_class';

const decodeJwtPayload = (token) => {
  const parts = String(token || '').split('.');
  if (parts.length !== 3) {
    return null;
  }

  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    return JSON.parse(window.atob(padded));
  } catch (error) {
    console.error('Error decoding auth token payload:', error);
    return null;
  }
};

/**
 * Store authentication token securely
 * Note: In production, consider using httpOnly cookies via a backend endpoint
 */
export const setAuthToken = (token) => {
  try {
    if (!token) {
      console.error('Invalid token provided to setAuthToken');
      return false;
    }
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(LEGACY_TOKEN_KEY, token);
    return true;
  } catch (error) {
    console.error('Error storing auth token:', error);
    return false;
  }
};

/**
 * Retrieve authentication token
 */
export const getAuthToken = () => {
  try {
    const token = localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY) || null;
    if (token && !localStorage.getItem(TOKEN_KEY)) {
      localStorage.setItem(TOKEN_KEY, token);
    }
    return token;
  } catch (error) {
    console.error('Error retrieving auth token:', error);
    return null;
  }
};

/**
 * Store school context
 */
export const setSchoolContext = (schoolId, role, branding, assignedClass, subscriptionPlan) => {
  try {
    localStorage.setItem(SCHOOL_ID_KEY, schoolId);
    localStorage.setItem(USER_ROLE_KEY, role);
    localStorage.setItem(BRANDING_KEY, JSON.stringify(branding));
    if (assignedClass) {
      localStorage.setItem(ASSIGNED_CLASS_KEY, assignedClass);
    }
    localStorage.setItem('subscription_plan', subscriptionPlan);
  } catch (error) {
    console.error('Error storing school context:', error);
  }
};

/**
 * Get authentication headers with CSRF protection
 */
export const getAuthHeaders = () => {
  const token = getAuthToken();
  const schoolId = localStorage.getItem(SCHOOL_ID_KEY);

  if (!token || !schoolId) {
    console.warn('Missing authentication context');
    return null;
  }

  return {
    'Authorization': `Bearer ${token}`,
    'X-School-ID': schoolId,
    'Content-Type': 'application/json',
    // CSRF Protection: Send Origin header
    'X-Requested-With': 'XMLHttpRequest'
  };
};

/**
 * Clear all authentication data on logout
 */
export const clearAuth = () => {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(LEGACY_TOKEN_KEY);
    localStorage.removeItem(SCHOOL_ID_KEY);
    localStorage.removeItem(USER_ROLE_KEY);
    localStorage.removeItem(BRANDING_KEY);
    localStorage.removeItem(ASSIGNED_CLASS_KEY);
    localStorage.removeItem('roles');
    localStorage.removeItem('enabled_modules');
    localStorage.removeItem('branding_school_id');
    localStorage.removeItem('post_login_target');
    localStorage.removeItem('requires_password_reset');
    localStorage.removeItem('subscription_plan');
  } catch (error) {
    console.error('Error clearing authentication:', error);
  }
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = () => {
  const token = getAuthToken();
  const schoolId = localStorage.getItem(SCHOOL_ID_KEY);
  return !!(token && schoolId);
};

/**
 * Get current user role
 */
export const getUserRole = () => {
  return localStorage.getItem(USER_ROLE_KEY);
};

/**
 * Check if user has required role
 */
export const hasRole = (requiredRole) => {
  const userRole = getUserRole();
  if (!userRole) return false;

  // Proprietor has access to all
  if (userRole === 'proprietor') return true;

  return userRole === requiredRole;
};

/**
 * Get school branding configuration
 */
export const getBranding = () => {
  try {
    const branding = localStorage.getItem(BRANDING_KEY);
    return branding ? JSON.parse(branding) : null;
  } catch (error) {
    console.error('Error parsing branding:', error);
    return null;
  }
};

/**
 * Apply school branding to UI
 */
export const applyBranding = () => {
  const branding = getBranding();
  if (branding && branding.theme_color) {
    document.documentElement.style.setProperty('--school-primary', branding.theme_color);
  }
};

/**
 * Validate token expiry and refresh if needed
 * Note: Implement token refresh logic based on your backend
 */
export const validateTokenExpiry = () => {
  const token = getAuthToken();
  if (!token) return false;

  try {
    const payload = decodeJwtPayload(token);
    if (!payload?.exp) {
      clearAuth();
      return false;
    }
    const expiresAt = payload.exp * 1000; // Convert to milliseconds

    if (Date.now() >= expiresAt) {
      clearAuth();
      return false;
    }
    return true;
  } catch (error) {
    console.error('Error validating token:', error);
    clearAuth();
    return false;
  }
};

export default {
  setAuthToken,
  getAuthToken,
  setSchoolContext,
  getAuthHeaders,
  clearAuth,
  isAuthenticated,
  getUserRole,
  hasRole,
  getBranding,
  applyBranding,
  validateTokenExpiry
};
