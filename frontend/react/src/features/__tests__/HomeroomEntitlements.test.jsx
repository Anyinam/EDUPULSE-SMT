import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import Homeroom from '../HomeroomDashboard';

vi.mock('axios');
vi.mock('../../hooks/useBranding', () => ({ useBranding: () => ({ branding: {} }) }));
vi.mock('../../components/TimetableManager', () => ({ default: () => null }));
vi.mock('../../components/AcademicGuidancePanel', () => ({ default: () => null }));

describe('homeroom read-only entitlements', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token');
    localStorage.setItem('assigned_class', 'JHS 1');
    axios.get.mockImplementation((url) => Promise.resolve({ data: url === '/api/school/subscription/effective-plan'
      ? { plan: 'Free Tier', features: { attendance: 'view_only', feeding: 'view_only', payment_tracking: false } }
      : [{ id: 1, name: 'Ama Mensah', is_present: true, feeding_paid: false }] }));
  });
  afterEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('preserves the roster but disables attendance and feeding writes', async () => {
    render(<Homeroom />);
    await waitFor(() => expect(screen.getByText('Ama Mensah')).toBeInTheDocument());
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Select All Present' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Clear Draft' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /Save Attendance/ })).toBeDisabled();
    const feedingButton = screen.getByRole('button', { name: 'Unpaid' });
    expect(feedingButton).toBeDisabled();
    fireEvent.click(feedingButton);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(axios.post).not.toHaveBeenCalled();
  });
});