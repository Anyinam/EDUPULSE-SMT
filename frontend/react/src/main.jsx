import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import axios from 'axios'
import './index.css'
import App from './App.jsx'

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const response = error?.response;
    const data = response?.data || {};

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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
