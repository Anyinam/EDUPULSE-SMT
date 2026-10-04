import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import axios from 'axios';
import Layout from '../Layout';
import ProprietorPanel from '../../features/ProprietorPanel';
import StudentsRegistry from '../../features/StudentsRegistry';

vi.mock('axios');
vi.mock('../../hooks/useBranding', () => ({ useBranding: () => ({ branding: {} }) }));
vi.mock('../../hooks/useEffectiveSubscriptionPlan', () => ({ default: () => ({ plan: 'Premium', loading: false }) }));
vi.mock('../../hooks/useSchoolClasses', () => ({ default: () => ({ classes: ['JHS 1'] }) }));
vi.mock('../Logo', () => ({ Logo: () => null }));
vi.mock('../Support', () => ({ default: () => null }));
vi.mock('../SchoolVerifiedBadge', () => ({ default: () => null }));
vi.mock('../AIInsights', () => ({ default: () => null }));
vi.mock('../BillingVisibility', () => ({ default: () => <div>Subscription billing</div> }));
vi.mock('../SettingsPanel', () => ({ default: () => <div>School settings</div> }));
vi.mock('../HolidayCalendar', () => ({ default: () => <div>School calendar</div> }));
vi.mock('../TerminalReportPrinter', () => ({ default: () => <div>Core reports</div> }));
vi.mock('../../features/SubscriptionManager', () => ({ default: () => <div>Subscription management</div> }));

describe('Free Tier navigation and proprietor routes', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('role', 'proprietor');
    localStorage.setItem('subscription_plan', 'Premium');
    axios.get.mockImplementation((url) => {
      if (url === '/api/school/subscription/effective-plan') {
        return Promise.resolve({ data: { plan: 'Free Tier', features: { payment_tracking: false, bulk_operations: false, advanced_analytics: false } } });
      }
      if (url === '/api/students?include_inactive=true') {
        return Promise.resolve({ data: [{ id: 1, name: 'Ama Mensah', current_class: 'JHS 1', status: 'Active' }] });
      }
      if (url.startsWith('/api/finance/audit/summary')) {
        return Promise.resolve({ data: { currency: 'GHS', summary: { total_transactions: 0, total_value: 0, verified_count: 0, is_chain_valid: true, integrity_status: 'Valid' } } });
      }
      if (url === '/api/finance/transactions' || url.endsWith('/payments') || url.endsWith('/reports')) {
        return Promise.resolve({ data: [] });
      }
      return Promise.resolve({ data: {} });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('hides restricted links without hiding subscription or core navigation', async () => {
    render(<MemoryRouter><Layout /></MemoryRouter>);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/school/subscription/effective-plan', expect.any(Object)));
    for (const name of ['Payment Tracker', 'Inventory']) {
      expect(screen.queryByRole('link', { name: new RegExp(name) })).not.toBeInTheDocument();
    }
    for (const name of ['Transaction History', 'Audit Report', 'Subscription', 'Students', 'Admissions', 'Holiday Calendar', 'Terminal Reports', 'System Settings']) {
      expect(screen.getByRole('link', { name: new RegExp(name) })).toBeInTheDocument();
    }
    expect(screen.queryByRole('link', { name: 'Payment Receipts' })).not.toBeInTheDocument();
  });

  it('does not show a Payment Receipts sidebar link (receipts live in the payment tracker)', async () => {
    render(<MemoryRouter initialEntries={['/payment-receipts']}><Layout /></MemoryRouter>);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/school/subscription/effective-plan', expect.any(Object)));
    expect(screen.queryByRole('link', { name: 'Payment Receipts' })).not.toBeInTheDocument();
  });

  it.each(['payment-tracker', 'inventory'])('locks the direct proprietor %s URL despite a cached Premium plan', async (tab) => {
    render(<MemoryRouter initialEntries={[`/proprietor?tab=${tab}`]}><ProprietorPanel /></MemoryRouter>);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/school/subscription/effective-plan', expect.any(Object)));
    expect(screen.getByText(tab === 'inventory' ? 'Plan Upgrade Required' : 'Payment Tracking Locked')).toBeInTheDocument();
    expect(axios.get.mock.calls.every(([url]) => url === '/api/school/subscription/effective-plan')).toBe(true);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it.each([
    ['finance', 'Financial Ledger'], ['audit', 'Financial Integrity Report'],
  ])('opens the direct historical %s URL on Free', async (tab, heading) => {
    render(<MemoryRouter initialEntries={[`/proprietor?tab=${tab}`]}><ProprietorPanel /></MemoryRouter>);
    expect(await screen.findByText(new RegExp(heading))).toBeInTheDocument();
    expect(axios.get).toHaveBeenCalledWith('/api/finance/transactions', expect.any(Object));
    expect(screen.queryByText('Payment Tracking Locked')).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('does not fetch live finance data or show payment approval controls on the dashboard', async () => {
    render(<MemoryRouter><ProprietorPanel /></MemoryRouter>);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/headmaster/attendance-summary', expect.any(Object)));
    expect(axios.get.mock.calls.some(([url]) => url === '/api/proprietor/live-feed' || url === '/api/proprietor/students')).toBe(false);
    expect(screen.queryByText(/Confirmed Revenue/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve.*Hash/ })).not.toBeInTheDocument();
    expect(screen.getByText('Subscription billing')).toBeInTheDocument();
  });

  it.each([
    ['subscription', 'Subscription management'], ['settings', 'School settings'],
    ['calendar', 'School calendar'], ['terminal-reports', 'Core reports'],
  ])('keeps the %s tab accessible', (tab, marker) => {
    render(<MemoryRouter initialEntries={[`/proprietor?tab=${tab}`]}><ProprietorPanel /></MemoryRouter>);
    expect(screen.getByText(marker)).toBeInTheDocument();
  });

  it('opens historical payments on Free without fetching collection balances', async () => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url, options) => url === '/api/students/1/payments'
      ? Promise.resolve({ data: [{ id: 10, date_paid: '2026-09-01', payment_type: 'Tuition', method: 'Historical transfer', amount: 120, status: 'Confirmed' }] })
      : defaultGet(url, options));
    render(<MemoryRouter><StudentsRegistry /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('Ama Mensah')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'View' }));
    await waitFor(() => expect(screen.queryByText('Loading student profile...')).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Academic' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Documents' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Finance' }));
    expect(screen.getByText('Payment Timeline')).toBeInTheDocument();
    expect(screen.getByText('Historical transfer')).toBeInTheDocument();
    expect(screen.getByText('GH₵ 120')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Payment Receipts' })).toHaveAttribute('href', '/payment-receipts');
    expect(axios.get.mock.calls.some(([url]) => url === '/api/students/1/payments')).toBe(true);
    expect(axios.get.mock.calls.some(([url]) => /balance|payment-codes|receive-payment/.test(url))).toBe(false);
    expect(screen.queryByText('Outstanding Tuition')).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('keeps paid core details and successful documents when payment collection access is denied', async () => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url, options) => {
      if (url === '/api/school/subscription/effective-plan') {
        return Promise.resolve({ data: { plan: 'Basic', features: { payment_tracking: true } } });
      }
      if (url === '/api/students/1/payments') {
        return Promise.reject({ response: { status: 403, data: { message: 'School verification required' } } });
      }
      if (url === '/api/students/1/documents') {
        return Promise.resolve({ data: { documents: [{ document_id: 'birth-1', original_filename: 'Birth certificate.pdf', download_path: '/api/students/1/documents/birth-1/download' }] } });
      }
      return defaultGet(url, options);
    });
    render(<MemoryRouter><StudentsRegistry /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'View' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Payment history unavailable: School verification required');
    expect(screen.getByText('Identity')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Documents' }));
    expect(screen.getByRole('button', { name: /Birth certificate.pdf/ })).toBeInTheDocument();
    expect(screen.queryByText('No student-owned or linked admissions documents are stored yet.')).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });

  it.each(['payments', 'reports', 'promotions', 'documents'])('retains the core profile when %s returns 403', async (slice) => {
    const defaultGet = axios.get.getMockImplementation();
    axios.get.mockImplementation((url, options) => url === `/api/students/1/${slice}`
      ? Promise.reject({ response: { status: 403, data: { message: 'Collection access denied' } } })
      : defaultGet(url, options));
    render(<MemoryRouter><StudentsRegistry /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'View' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('unavailable: Collection access denied');
    expect(screen.getByText('Identity')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Guardian' }));
    expect(screen.getByText('Guardian Contact')).toBeInTheDocument();
    if (slice === 'payments') {
      fireEvent.click(screen.getByRole('button', { name: 'Finance' }));
      expect(screen.getByText('Payment history unavailable.')).toBeInTheDocument();
      expect(screen.queryByText('No payment history recorded yet.')).not.toBeInTheDocument();
    }
    if (slice === 'reports' || slice === 'documents') {
      fireEvent.click(screen.getByRole('button', { name: 'Documents' }));
      expect(screen.getByText('Records unavailable. Please try again later.')).toBeInTheDocument();
    }
    expect(axios.post).not.toHaveBeenCalled();
  });
});