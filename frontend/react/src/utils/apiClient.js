/**
 * Secure API client for EduPulse
 * Handles authentication, error handling, and request interceptors
 */

import axios from 'axios';
import * as auth from './authUtils';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  }
});

/**
 * Request interceptor: Add auth headers and validate token
 */
apiClient.interceptors.request.use(
  (config) => {
    // Validate token before each request
    if (!auth.validateTokenExpiry()) {
      auth.clearAuth();
      window.location.href = '/login';
      return Promise.reject(new Error('Session expired'));
    }

    // Add auth headers
    const headers = auth.getAuthHeaders();
    if (headers) {
      config.headers = { ...config.headers, ...headers };
    }

    // CSRF Protection: Add origin header
    config.headers['X-Requested-With'] = 'XMLHttpRequest';

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor: Handle errors and token expiry
 */
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid
      auth.clearAuth();
      window.location.href = '/login';
      return Promise.reject(new Error('Authentication failed. Please login again.'));
    }

    if (error.response?.status === 403) {
      // Access denied
      return Promise.reject(new Error('You do not have permission to access this resource.'));
    }

    if (error.response?.status === 429) {
      // Rate limited
      return Promise.reject(new Error('Too many requests. Please try again later.'));
    }

    if (error.response?.status === 500) {
      // Server error
      console.error('Server error:', error.response.data);
      return Promise.reject(new Error('Server error. Please try again later.'));
    }

    return Promise.reject(error);
  }
);

/**
 * GET request
 */
export const apiGet = (endpoint, config = {}) => {
  return apiClient.get(endpoint, config);
};

/**
 * POST request
 */
export const apiPost = (endpoint, data = {}, config = {}) => {
  return apiClient.post(endpoint, data, config);
};

/**
 * PUT request
 */
export const apiPut = (endpoint, data = {}, config = {}) => {
  return apiClient.put(endpoint, data, config);
};

/**
 * DELETE request
 */
export const apiDelete = (endpoint, config = {}) => {
  return apiClient.delete(endpoint, config);
};

/**
 * Login request
 */
export const login = (schoolCode, username, password) => {
  return apiClient.post('/login', {
    schoolCode,
    username,
    password
  }, {
    headers: {
      // Override to exclude auth headers for login
      'X-School-ID': schoolCode,
      'Content-Type': 'application/json'
    }
  });
};

/**
 * Register request
 */
export const register = (schoolCode, schoolName, username, password, termsAccepted, termsVersion) => {
  return apiClient.post('/register', {
    schoolCode,
    schoolName,
    username,
    password,
    termsAccepted,
    termsVersion
  }, {
    headers: {
      'X-School-ID': schoolCode,
      'Content-Type': 'application/json'
    }
  });
};

/**
 * Forgot password request
 */
export const forgotPassword = (schoolCode, email) => {
  return apiClient.post('/forgot-password', {
    schoolCode,
    email
  }).catch(error => {
    // Always return success message for security (user enumeration prevention)
    return Promise.resolve('If an account exists, a reset link has been sent.');
  });
};

/**
 * Reset password request
 */
export const resetPassword = (token, password) => {
  return apiClient.post('/reset-password', {
    token,
    password
  }, {
    headers: {
      // Remove auth headers for password reset
      'Content-Type': 'application/json'
    }
  });
};

export default {
  apiGet,
  apiPost,
  apiPut,
  apiDelete,
  login,
  register,
  forgotPassword,
  resetPassword
};
