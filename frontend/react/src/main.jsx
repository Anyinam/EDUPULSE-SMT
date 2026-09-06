import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import axios from 'axios'
import './index.css'
import App from './App.jsx'
import { clearAuth, getAuthToken, validateTokenExpiry } from './utils/authUtils'

const AUTH_EXEMPT_PATH_PREFIXES = [
  '/api/login',
  '/api/register',
  '/api/2fa/',
  '/api/forgot-password',
  '/api/reset-password',
  '/api/public/',
];

const isPublicRoute = (pathname = window.location.pathname) => (
  pathname === '/login'
  || pathname === '/admin/login'
  || pathname === '/register'
  || pathname === '/pricing'
  || pathname === '/pricing-comparison'
  || pathname.startsWith('/apply/')
);

const isAuthExemptRequest = (url) => AUTH_EXEMPT_PATH_PREFIXES.some((prefix) => String(url || '').startsWith(prefix));

const redirectToLogin = (message) => {
  clearAuth();
  if (message) {
    sessionStorage.setItem('session_expired_message', message);
  }
  if (!isPublicRoute()) {
    window.location.replace('/login');
  }
};

const enforceActiveSession = () => {
  if (isPublicRoute()) {
    return;
  }

  const token = getAuthToken();
  const schoolId = localStorage.getItem('school_id');
  if (!token || !schoolId || !validateTokenExpiry()) {
    redirectToLogin('Your session expired. Please log in again.');
  }
};

axios.interceptors.request.use(
  (config) => {
    if (!isAuthExemptRequest(config?.url) && getAuthToken() && !validateTokenExpiry()) {
      redirectToLogin('Your session expired. Please log in again.');
      return Promise.reject(new Error('Session expired'));
    }
    return config;
  },
  (error) => Promise.reject(error),
)

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const response = error?.response;
    const data = response?.data || {};

    if (response?.status === 401 && !isAuthExemptRequest(response?.config?.url)) {
      redirectToLogin(data?.message || 'Your session expired. Please log in again.');
      return Promise.reject(new Error(data?.message || 'Authentication failed. Please login again.'));
    }

    if (response?.status === 402 && data?.error === 'billing_restriction') {
      if (data?.billing_status) {
        sessionStorage.setItem('billing_restriction', JSON.stringify(data.billing_status));
      }

      const roles = JSON.parse(localStorage.getItem('roles') || '[]');
      const role = localStorage.getItem('role');
      const isProprietor = role === 'proprietor' || roles.includes('proprietor');

      window.location.href = isProprietor
        ? '/proprietor?tab=subscription&billing=blocked'
        : '/subscription?billing=blocked';

      return Promise.reject(new Error(data?.message || 'Payment required to continue.'));
    }

    return Promise.reject(error);
  }
)

window.addEventListener('focus', enforceActiveSession)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    enforceActiveSession()
  }
})

enforceActiveSession()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
