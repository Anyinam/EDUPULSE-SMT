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
});
