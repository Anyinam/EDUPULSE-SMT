import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import TrialManager from '../TrialManager';

vi.mock('axios');

describe('TrialManager', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');
    window.confirm = vi.fn(() => true);
    window.alert = vi.fn();
    delete window.location;
    window.location = { reload: vi.fn() };
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('posts the selected trial plan when activating a trial', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        is_active: false,
        has_used_trial: false,
        base_plan: 'Free Tier',
        available_trial_plans: [
          { plan: 'Basic', display_name: 'School OS', description: 'Core operations', includes_addons: false },
          { plan: 'Premium', display_name: 'School OS Plus', description: 'Governance and scale', includes_addons: true },
        ],
      },
    });
    axios.get.mockResolvedValueOnce({
      data: {
        is_active: true,
        plan: 'Basic',
        plan_display_name: 'School OS',
        has_used_trial: true,
        available_trial_plans: [],
      },
    });
    axios.post.mockResolvedValueOnce({
      data: {
        trial_plan: 'Basic',
      },
    });

    render(<TrialManager />);

    await waitFor(() => {
      expect(screen.getByText(/Activate Your Free Subscription Trial/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /School OS Core operations Core paid-plan features only during trial/i }));
    fireEvent.click(screen.getByRole('button', { name: /Activate 30-Day School OS Trial/i }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        '/api/school/subscription/trial/activate',
        { trial_plan: 'Basic' },
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer token-1',
            'X-School-ID': 'TEST-001',
          }),
        })
      );
    });
  });
});