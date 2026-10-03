import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import FinanceDashboard from '../FinanceDashboard';

vi.mock('axios');
vi.mock('../../hooks/useSubscription', () => ({ default: () => ({ plan: 'Basic', hasFeature: () => true }) }));
vi.mock('react-router-dom', () => ({
  useSearchParams: () => [new URLSearchParams(''), vi.fn()],
}));
vi.mock('../PaymentEntry', () => ({
  default: () => <div>PaymentEntry</div>,
}));
vi.mock('../../components/StudentPaymentTracker', () => ({
  default: () => <div>StudentPaymentTracker</div>,
}));
vi.mock('../../hooks/useBranding', () => ({
  useBranding: () => ({ branding: {} }),
}));

describe('FinanceDashboard', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');

    axios.get.mockImplementation((url) => {
      if (url === '/api/finance/dashboard') {
        return Promise.resolve({
          data: {
            daily_revenue: 20.19,
            monthly_revenue: 20.19,
            yearly_revenue: 20.19,
            total_collected: 20.19,
            outstanding_balance: 40.0,
            recent_transactions: [
              {
                id: 1,
                date: '2026-09-19',
                student_name: 'Ama Mensah',
                amount: 20.19,
                display_amount: 21.0,
                applied_amount: 20.19,
                type: 'Tuition',
                method: 'Paystack_Payment',
                status: 'Confirmed',
                payment_category: {
                  collection_channel: 'dedicated_virtual_account',
                  reference_code: 'S001-TUIT-I1',
                  transfer_total_amount: 21.0,
                  applied_school_fee_amount: 20.19,
                  collected_convenience_fee_amount: 0.4,
                  actual_provider_fee_amount: 0.41,
                },
              },
            ],
            pending_payments: [],
            pending_payments_by_class: [],
          },
        });
      }

      if (url === '/api/students') {
        return Promise.resolve({ data: [] });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('shows tracked-transfer breakdown in recent transactions', async () => {
    render(<FinanceDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/finance dashboard/i)).toBeInTheDocument();
    });

    expect(screen.getByText('Gross paid:')).toBeInTheDocument();
    expect(screen.getByText('Convenience deducted:')).toBeInTheDocument();
    expect(screen.getByText('Paystack fee deducted:')).toBeInTheDocument();
    expect(screen.getByText('Applied to school fee:')).toBeInTheDocument();
    expect(screen.getByText('Ref:')).toBeInTheDocument();
    expect(screen.getAllByText('GH₵ 20.19').length).toBeGreaterThan(0);
  });
});