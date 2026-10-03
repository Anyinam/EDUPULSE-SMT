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
    for (const name of ['Payment Tracker', 'Transaction History', 'Audit Report', 'Inventory']) {
      expect(screen.queryByRole('link', { name: new RegExp(name) })).not.toBeInTheDocument();
    }
    for (const name of ['Payment Receipts', 'Subscription', 'Students', 'Admissions', 'Holiday Calendar', 'Terminal Reports', 'System Settings']) {
      expect(screen.getByRole('link', { name: new RegExp(name) })).toBeInTheDocument();
    }
  });

  it.each(['proprietor', 'finance', 'headmaster', 'homeroom', 'teacher'])('keeps receipts independent of modules and subscription for %s', async (role) => {
    localStorage.setItem('role', role);
    localStorage.setItem('enabled_modules', JSON.stringify({ finance: false }));
    render(<MemoryRouter initialEntries={['/payment-receipts']}><Layout /></MemoryRouter>);
    expect(screen.getByRole('link', { name: 'Payment Receipts' })).toHaveAttribute('href', '/payment-receipts');
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/staff/notifications', expect.any(Object)));
    expect(axios.get.mock.calls.every(([url]) => url === '/api/staff/notifications')).toBe(true);
    expect(screen.queryByRole('link', { name: /Payment Tracker/ })).not.toBeInTheDocument();
  });

  it('supports normalized secondary receipt roles but not kitchen-only users', async () => {
    localStorage.setItem('role', 'kitchen');
    localStorage.setItem('roles', JSON.stringify([' Teacher ']));
    const { unmount } = render(<MemoryRouter initialEntries={['/payment-receipts']}><Layout /></MemoryRouter>);
    expect(screen.getByRole('link', { name: 'Payment Receipts' })).toBeInTheDocument();
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/staff/notifications', expect.any(Object)));
    unmount();
    localStorage.setItem('roles', '[]');
    render(<MemoryRouter initialEntries={['/payment-receipts']}><Layout /></MemoryRouter>);
    expect(screen.queryByRole('link', { name: 'Payment Receipts' })).not.toBeInTheDocument();
    await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(2));
  });

  it.each(['finance', 'payment-tracker', 'audit', 'inventory'])('locks the direct proprietor %s URL despite a cached Premium plan', async (tab) => {
    render(<MemoryRouter initialEntries={[`/proprietor?tab=${tab}`]}><ProprietorPanel /></MemoryRouter>);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/school/subscription/effective-plan', expect.any(Object)));
    expect(screen.getByText(tab === 'inventory' ? 'Plan Upgrade Required' : 'Payment Tracking Locked')).toBeInTheDocument();
    expect(axios.get.mock.calls.every(([url]) => url === '/api/school/subscription/effective-plan')).toBe(true);
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

  it('opens a basic student profile without fetching payment history', async () => {
    render(<StudentsRegistry />);
    await waitFor(() => expect(screen.getByText('Ama Mensah')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'View' }));
    await waitFor(() => expect(screen.queryByText('Loading student profile...')).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Academic' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Documents' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Finance' })).not.toBeInTheDocument();
    expect(axios.get.mock.calls.some(([url]) => url === '/api/students/1/payments')).toBe(false);
  });
});