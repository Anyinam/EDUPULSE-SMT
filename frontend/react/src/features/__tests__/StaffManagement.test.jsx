import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import axios from 'axios';
import StaffManagement from '../StaffManagement';

vi.mock('axios');

describe('StaffManagement', () => {
  beforeEach(() => {
    vi.stubGlobal('alert', vi.fn());
    vi.stubGlobal('confirm', vi.fn(() => true));
    localStorage.setItem('token', 'token-1');
    localStorage.setItem('school_id', 'TEST-001');

    axios.get.mockImplementation((url) => {
      if (url === '/api/staff/list') {
        return Promise.resolve({
          data: [
            {
              id: 7,
              username: 'Testinghomeroom',
              email: 'teacher@example.com',
              role: 'homeroom',
              roles: ['homeroom'],
              assigned_class: 'JHS 2',
              assigned_classes: ['JHS 1', 'JHS 2'],
              assigned_subjects: ['Mathematics'],
            },
          ],
        });
      }

      if (url === '/api/timetable') {
        return Promise.resolve({ data: [] });
      }

      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('shows a tenant-safe resend invite message when email delivery fails', async () => {
    axios.post.mockResolvedValue({
      data: {
        message: 'Staff invite resent successfully. Invite created, but the welcome email could not be delivered right now.',
        email_sent: false,
        email_error: 'SMTPAuthenticationError: 535 Authentication failed',
      },
    });

    render(<StaffManagement />);

    await waitFor(() => {
      expect(screen.getByText('Testinghomeroom')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Resend Invite'));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/staff/7/resend-invite', {}, expect.any(Object));
    });

    expect(window.confirm).toHaveBeenCalled();
    expect(window.alert).toHaveBeenCalledWith(
      'Staff invite resent successfully. Invite created, but the welcome email could not be delivered right now.'
    );
  });
});