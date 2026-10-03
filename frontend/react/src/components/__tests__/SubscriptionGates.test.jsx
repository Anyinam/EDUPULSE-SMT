import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import axios from 'axios';
import StudentPaymentTracker from '../StudentPaymentTracker';
import AuditReport from '../AuditReport';
import RemoteOversight from '../RemoteOversight';
import FinanceDashboard from '../../features/FinanceDashboard';
import TransactionHistory from '../../features/TransactionHistory';
import PaymentEntry from '../../features/PaymentEntry';
import InventoryManager from '../../features/InventoryManager';
import BulkStatusUpdate from '../BulkStatusUpdate';
import PerformanceAnalytics from '../PerformanceAnalytics';

vi.mock('axios');

describe('restricted components', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
    axios.get.mockResolvedValue({ data: { plan: 'Free Tier', features: { payment_tracking: false } } });
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it.each([
    ['tracker', StudentPaymentTracker], ['audit', AuditReport], ['oversight', RemoteOversight],
    ['finance', FinanceDashboard], ['transactions', TransactionHistory], ['payment entry', PaymentEntry],
  ])('does not mount or fetch %s on Free Tier', async (_name, Component) => {
    render(<MemoryRouter><Component students={[]} /></MemoryRouter>);
    await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Payment Tracking Locked')).toBeInTheDocument();
    expect(axios.get.mock.calls[0][0]).toBe('/api/school/subscription/effective-plan');
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('does not fetch inventory on Free Tier', async () => {
    render(<InventoryManager />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Plan Upgrade Required')).toBeInTheDocument();
  });

  it('does not mount shared bulk status controls on Free Tier', async () => {
    render(<BulkStatusUpdate />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Bulk Operations Locked')).toBeInTheDocument();
    expect(axios.get.mock.calls[0][0]).toBe('/api/school/subscription/effective-plan');
  });

  it('keeps the tracker unmounted when entitlement loading fails', async () => {
    axios.get.mockRejectedValue(new Error('offline'));
    render(<StudentPaymentTracker />);
    await waitFor(() => expect(screen.getByText("You're currently on", { exact: false })).toBeInTheDocument());
    expect(axios.get.mock.calls.every(([url]) => url === '/api/school/subscription/effective-plan')).toBe(true);
    expect(axios.post).not.toHaveBeenCalled();
  });

  it('opens the tracker for paid and active-trial effective plans', async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url === '/api/school/subscription/effective-plan'
      ? { plan: 'Premium', base_plan: 'Free Tier', trial: { active: true }, features: { payment_tracking: true } }
      : [] }));
    render(<StudentPaymentTracker />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/students', expect.any(Object)));
    expect(screen.queryByText('Payment Tracking Locked')).not.toBeInTheDocument();
  });

  it('does not fetch analytics on a locked plan', async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url === '/api/school/subscription/effective-plan'
      ? { plan: 'Basic', features: { advanced_analytics: false } }
      : [] }));
    render(<PerformanceAnalytics />);
    await waitFor(() => expect(axios.get).toHaveBeenCalledWith('/api/school/subscription/effective-plan', expect.any(Object)));
    expect(axios.get.mock.calls.some(([url]) => url.startsWith('/api/analytics/'))).toBe(false);
  });

  it('disables quick feeding when payment access exists but feeding is read-only', async () => {
    axios.get.mockResolvedValue({ data: { plan: 'Basic', features: { payment_tracking: true, feeding: 'view_only' } } });
    render(<PaymentEntry students={[]} />);
    const quickFeeding = await screen.findByRole('button', { name: 'Daily Feeding' });
    expect(quickFeeding).toBeDisabled();
    fireEvent.click(quickFeeding);
    expect(screen.queryByRole('button', { name: 'Record Feeding' })).not.toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();
  });
});