import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import SubscriptionManager from '../SubscriptionManager';

vi.mock('axios');
vi.mock('../../components/BillingVisibility', () => ({ default: () => <div>BillingVisibility</div> }));
vi.mock('../../components/TrialManager', () => ({ default: () => <div>TrialManager</div> }));
vi.mock('../../components/BillingControlPanel', () => ({ default: () => <div>BillingControlPanel</div> }));

describe('SubscriptionManager', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    axios.get.mockResolvedValue({
      data: {
        plan: 'Premium',
        status: 'Pending Downgrade',
        pending_plan: 'Free Tier',
        next_billing_date: '2026-04-15T00:00:00Z',
        current_enrollment: 54,
        term_cost: 918,
      },
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it('shows the pending downgrade banner when a free-tier switch is scheduled', async () => {
    render(<SubscriptionManager />);

    await waitFor(() => {
      expect(screen.getByText(/Pending downgrade to Free Tier on/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/current paid plan remains active until the next billing date/i)).toBeInTheDocument();
  });

  it('shows prorated post-trial billing guidance for free-tier conversions', async () => {
    axios.get
      .mockResolvedValueOnce({
        data: {
          plan: 'Free Tier',
          subscription_plan: 'Free Tier',
          status: 'Active',
          current_enrollment: 54,
          term_cost: 0,
          term_proration: {
            days_remaining: 18,
            days_in_term: 120,
            proration_ratio: 0.15,
          },
        },
      })
      .mockResolvedValueOnce({
        data: {
          plans: [],
        },
      });

    render(<SubscriptionManager />);

    await waitFor(() => {
      expect(screen.getByText(/prorated initial charge:/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/18 remaining day\(s\) in the remaining current-term days/i)).toBeInTheDocument();
  });
});
